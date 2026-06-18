# 七個 Prefetch 策略 — 怎麼測出來的（測試流程詳解）

> 這是 [overall_strategies.md](overall_strategies.md) 的**測試流程伴讀版**。
> overall_strategies.md 講「每個策略是什麼」、[overall_results.md](overall_results.md) 講「結果數字」；
> 本檔講「**每個策略到底是怎麼被測出來的**」——從清空快取、插入 prefetch、到量第一筆延遲。

---

## 總綱：七個策略共用同一套引擎

七個策略的測試流程**幾乎一模一樣**，因為它們都跑同一支 C 程式
[benchmark_harness](benchmark_harness/benchmark_harness.c)。唯一會變的，是其中一個參數：

> **`--post-cold-script` 換成哪一支 prefetch 程式**，就決定了你在測哪個策略。

所以下面先把**共同的引擎**講透（這部分七個策略都一樣），再列**每個策略各自換上去的那支腳本**。

---

# 第一部分：共同的測試引擎

## 「測一格」的精確時間軸

一格 = 一個 workload × 一個策略（含參數）× 一次 rep。指揮一格的指令長這樣：

```sh
benchmark_harness --db test.db --workload workloadc.txt \
  --cold-advice dontneed \
  --drop-caches-script cold_orig.sh \
  --post-cold-script  <某支 prefetch 腳本>   ← 換這行 = 換策略
```

harness 拿到後，**嚴格按這個順序跑**（主流程 [benchmark_harness.c:1260-1294](benchmark_harness/benchmark_harness.c#L1260)）：

| 步驟 | 做什麼 | 在哪 |
|---|---|---|
| ① mmap + 盤點 | 把 DB 映射進來，數「現在記憶體裡有幾頁」（before）| [:1260](benchmark_harness/benchmark_harness.c#L1260) |
| ② sync | 把 dirty page 刷回磁碟，確保乾淨 | [:1266](benchmark_harness/benchmark_harness.c#L1266) |
| ③ 製造冷啟動 | 對整個 DB 下 `MADV_COLD → MADV_PAGEOUT → MADV_DONTNEED`，把 DB 趕出快取 | [:1267](benchmark_harness/benchmark_harness.c#L1267) |
| ④ 補一刀清快取 | 跑 `cold_orig.sh` → `evict` → `posix_fadvise(DONTNEED)`，保險再清一次 | [:1268](benchmark_harness/benchmark_harness.c#L1268) |
| ⑤ **跑 prefetch** | 跑 `--post-cold-script` 指定的腳本 → **這一步才是策略本體** | [:1270](benchmark_harness/benchmark_harness.c#L1270) |
| ⑥ 盤點 | 再數「現在記憶體裡有幾頁」（after）→ 驗證 prefetch 真的有載進來 | [:1287](benchmark_harness/benchmark_harness.c#L1287) |
| ⑦ 跑查詢 + 計時 | 照 workload 一筆一筆跑 SQL，每筆都計時 | [:1294](benchmark_harness/benchmark_harness.c#L1294) |

整個設計最巧妙的地方在 ③④⑤ 的順序：**先把快取清到全冷（③④），再在查詢前的最後一刻插入 prefetch（⑤）**。
這個「插隊時機」靠的就是 `--post-cold-script` 這個 hook——它在「冷啟動之後、查詢之前」
fork 一個子行程跑你指定的腳本（[:1270](benchmark_harness/benchmark_harness.c#L1270)、fork 在 [:777](benchmark_harness/benchmark_harness.c#L777)）。

## 冷啟動是怎麼「無 sudo」做到的

這點對本機很關鍵（u03 沒有 sudo/kvm 權限）。傳統做法 `echo 3 > /proc/sys/vm/drop_caches` **需要 root**。
這套 harness 改用兩個**不需權限**的招數疊起來：

1. `MADV_COLD → MADV_PAGEOUT → MADV_DONTNEED`（[:739-752](benchmark_harness/benchmark_harness.c#L739)）：對自己 mmap 的區域叫 kernel「這些頁回收掉」。
2. `posix_fadvise(fd, 0, 0, POSIX_FADV_DONTNEED)`（[evict.c:12](layout_rewriter/runs/evict.c#L12)）：對檔案本身叫 kernel 丟掉它的 page cache。

這也是為什麼報告一直提醒「絕對 µs 不能跨表比」——早期 prefetch_vacuum 用 `sudo drop_caches`，這套用 `posix_fadvise`，兩種冷啟動深度不同，只能比**同一張表內的相對 %**。

## 量的是什麼

跑查詢時，每一筆 SQL 都被夾在計時器中間（[:1106-1167](benchmark_harness/benchmark_harness.c#L1106)）：

```c
clock_gettime(BEFORE);  getrusage(BEFORE);
    ... 跑這筆 SQL ...
clock_gettime(AFTER);   getrusage(AFTER);
```

抓三個數字：
- **`first_query_us`** = **第 0 筆**的耗時（[:1171](benchmark_harness/benchmark_harness.c#L1171) `if (i==0)`）——這就是「冷啟動延遲」，是主指標。
- **`avg_us`** = 全部查詢平均。
- **`majflt`**（major fault）= 真的去磁碟讀了幾次 → **prefetch 有沒有效的直接證據**。

## 掃一輪 + 取中位數

外面用 shell 的兩層 for 迴圈把一格一格跑出來：

```sh
for 參數 in <要掃的值>; do        # 例如 layers_N 掃 N、2e 掃 K
  for REP in 1 2 3; do            # 每格重複 3 次（2e/RAM 矩陣用 6 次）
     跑一格（上面那整套 7 步）
     從輸出抓 first_query_us / avg_us / majflt → 印成一行 CSV
  done
done
```

**重複多次是為了打 noise**（冷啟動單筆抖動很大），事後對每個參數**取中位數**，才是報告表格裡那個數字。

## 怎麼驗證「prefetch 真的有效」（不是自欺）

光看延遲變快還不夠，harness 留了三道交叉驗證：
1. **第 ① vs ⑥ 步的 resident 盤點**：before 接近 0（冷啟動成功），after 多出該策略載入的頁數（prefetch 確實生效）。寫進 `bench_records/` 記錄檔。
2. **majflt 下降**：baseline 第一筆有一堆 major fault；掛上策略後變少 → 證明那些頁是 prefetch 提前載好的。
3. **prefetch 程式自己的 stderr**：每支 prefetch 程式都印 `n_prefetch=K syscalls=K time_us=…` → 這就是「下了幾道指令、花多久」（prefetch overhead 的來源）。

---

# 第二部分：兩種前置準備

## 先抓核心：prefetch 程式自己「不會思考」

回想第 ⑤ 步那支 prefetch 程式（`prefetch` / `prefetch_layers` / `prefetch_access` /
`prefetch_slru`），它其實很笨：

> **它不會自己判斷該載哪些頁。它只是打開一個 CSV 檔，照著裡面寫的清單一頁一頁 `madvise`。**

所以在正式測試（那 7 步）能跑之前，**一定要有人先把那個 CSV 檔做出來**。

> **「前置準備」= 製作第 ⑤ 步要讀的那個 CSV 清單。** 就這麼簡單。

而那個 CSV 有兩種，做法完全不同——這就是「兩派」的由來：

| 派別 | 策略 | 第 ⑤ 步讀的 CSV | 這個 CSV 怎麼來 | 要不要先跑 workload |
|---|---|---|---|---|
| **結構派** | 2a / 2b / 2c | `classify.csv` | 讀一次 DB 檔案結構就有 | ❌ 不用 |
| **歷史派** | 2d / 2e / 2f | `hotpages.csv` | 先跑一遍 workload 再觀察 | ✅ **要** |

## 第一種準備：classify.csv（結構派 2a/b/c 用）

這個檔回答的問題是：**「每一頁是 interior（目錄）還是 leaf（資料）？在檔案哪個位置？」**

**怎麼做**：跑一次 [classify_pages](classify_pages/classify_pages.c)，它直接讀 DB 檔案格式
（看每頁第一個 byte 的 b-tree flag）就分得出來。

**重點：這不需要跑任何查詢。** 就像拿到一棟大樓的設計圖，光看圖就知道哪間是倉庫、哪間是
辦公室——不用等任何人上班。所以結構派的前置準備**又快又一次搞定**。

## 第二種準備：hotpages.csv（歷史派 2d/e/f 用）

這個檔回答的問題是：**「跑這個 workload 時，哪些頁『真的被用到』？」**

問題來了：**你光看 DB 檔案，是看不出來「哪些頁會被用到」的**——那取決於 workload 會查哪些 key。
要知道答案，**唯一的辦法就是先實際跑一遍 workload，然後看結果**。
這個「先跑一遍來觀察」的動作，就叫 **warmup pass（暖機）**。

**warmup pass 的三步**（[prefetch_slru/runs/warmup.sh](prefetch_slru/runs/warmup.sh)），每步的「為什麼」：

```
1. evict                            → 先把快取清空
2. 跑一遍 workload（--cold-advice none） → 讓查詢自然把用到的頁拉進快取
3. residency_checker（mincore）     → 拍一張「現在快取裡有哪些頁」的快照 → hotpages.csv
```

1. **先 evict（清空）**：從乾淨狀態開始，這樣最後留在快取裡的頁，**純粹是這個 workload
   自己拉進來的**，不會混到別人的殘留。
2. **正常跑一遍 workload**：`--cold-advice none` 的意思是「**這次不冷啟動、不 prefetch，
   就老老實實跑查詢**」。跑完之後，快取裡剛好就躺著「這個 workload 碰過的所有頁」。
3. **residency_checker 拍快照**：用一個 `mincore()` 呼叫，把「現在哪些頁在快取裡」記下來，
   寫成 hotpages.csv。**這張快照，就是「哪些頁是熱的」的情報。**

做完這三步，hotpages.csv 才存在，2d/2e/2f 的正式測試（7 步）才有東西可讀。

> （2e 還要再多一步 [gen_hotleaves.py](prefetch_access/runs/gen_hotleaves.py)，從 workload
> 算出「最熱的前 K 個 leaf」疊上去——但骨架一樣，都是先跑、再觀察、產生清單。）

> ⚠️ **重要前提：同 workload 暖機 = 上界估計（best-case），不是「沒看過題目」的成績**
>
> 歷史派（2d / 2e / 2f / 3a / 3b）的暖機，用的是**跟待測完全相同的 query 序列**
> （`hotpages.csv` 就是跑那份 workload 後 dump 出來的；2d/2e/2f 甚至共用同一份檔）。
> 等於先偷看了考題 → 命中率接近完美。所以這幾組數字應讀作
> **「預測完美時的 best-case 上界」**，不是「production 第一次冷啟動、零歷史」的成績。
>
> - **算不算「作弊」要看宣稱什麼**：若宣稱「零歷史的第一次冷啟動」，那是太樂觀；
>   若宣稱「**會重複出現的 workload**（同一服務反覆冷啟動，warm process / cold data），
>   用上一次觀察預熱下一次」，那就**不算**——這正是 SLRU/LRU 的前提。
> - **結構派（2a/b/c）不受這個前提影響**：它們只讀 `classify.csv`（結構），沒偷看任何查詢。
> - **專案的實驗反駁**：churn 系列（[第十八維](overall_results.md#L1591)）證明**暖機只在 t=0 做一次、
>   之後 DB 漂移 5 萬筆寫入，那份過期的 hotpages 依然不 decay** → 熱頁集不是脆弱 oracle，
>   對資料漂移有泛化力。（但仍是同一個 key 分佈，只是 DB 狀態變了。）
> - **要更嚴格**：可改用 held-out——暖機用前半段、量測用後半段；或暖機/量測各取同分佈的不同抽樣。

## 把時間順序攤開（這通常是卡住的點）

很多人以為「測試」就只有那 7 步。其實前置準備是**更早、獨立、只做一次**的階段：

```
【階段一：一次性前置準備（做出 CSV 清單）】
  結構派:  classify_pages(DB)         ──►  classify.csv    （隨時可做，不用跑查詢）
  歷史派:  warmup pass(DB, workload)  ──►  hotpages.csv    （必須先跑一遍 workload）

        ↓  CSV 準備好之後，才進入

【階段二：正式測試 = 第一部分的 7 步引擎，跑很多格（掃 N/K × 多 reps）】
  ...
  ⑤ prefetch 程式讀上面那個 CSV → 照清單 madvise
  ...
```

## 為什麼要特別分這兩派

因為「**要不要 warmup pass**」是個**真實的成本差異**，不只是技術細節：

- **結構派（2a/b/c）**：開箱即用，不用任何查詢歷史就能 prefetch。
- **歷史派（2d/e/f）**：**必須先跑過一次** workload 才知道什麼是熱的。在現實系統裡，
  這代表「你得先有一段查詢歷史」才能用這招——這也是「免 warmup」會是個賣點的原因。

---

# 第三部分：七個策略各自的「測一格」配方

> 下面每個策略，跑的都是上面那套 **7 步引擎**，只有**第 ⑤ 步換成不同的 prefetch 程式**。
> 所以每格只列「第 ⑤ 步跑什麼、需不需要 warmup、掃什麼、哪支 driver」。

## 2a range（結構派）

- **第 ⑤ 步跑**（[prefetch_range_orig.sh](layout_rewriter/runs/prefetch_range_orig.sh)）：
  ```sh
  prefetch  test.db  classify_before.csv  range
  ```
  → 讀 classify、取全部 interior、排序後把連號的合併成區間，一段一個 `madvise`。
- **前置**：只要 classify.csv，免 warmup。
- **掃什麼**：不掃參數（單一 arm）。
- **driver**：[runmatrix.sh](layout_rewriter/runs/runmatrix.sh)（orig+ta layout × {baseline,range,perpage,layers5} × 3 reps）。
- **驗什麼**：看 ⑥ 的 resident——這策略會暴露「kernel readahead 有上限，一段 madvise 只載進 32/92 頁」。

## 2b perpage（結構派）

- **第 ⑤ 步跑**（[prefetch_perpage_orig.sh](layout_rewriter/runs/prefetch_perpage_orig.sh)）：
  ```sh
  prefetch  test.db  classify_before.csv  perpage
  ```
  → 同一支 `prefetch` 程式，換 `perpage`：全部 interior，每頁一個 `madvise`（92 道指令）。
- **前置**：classify.csv，免 warmup。
- **掃什麼**：不掃。
- **driver**：同 [runmatrix.sh](layout_rewriter/runs/runmatrix.sh)。
- **驗什麼**：對比 range——perpage 指令多、覆蓋齊，但 syscall overhead 大。

## 2c layers_N（結構派）★ 標準範例

- **第 ⑤ 步跑**（[prefetch_layers5_orig.sh](layout_rewriter/runs/prefetch_layers5_orig.sh)）：
  ```sh
  prefetch_layers  test.db  classify_before.csv  5  4096
                                                 ↑
                                             這個 5 就是 N
  ```
  → 讀 classify、取 interior、按 offset 排序、`madvise` 前 **N** 個。
- **「N」在哪決定**：就在這支腳本的那個數字。`layers_5`、`layers_10`、`layers_92`
  **不是不同程式**，是同一支 `prefetch_layers` 換一個 N——專案為每個 N 各放一支只差那數字的小腳本
  （`prefetch_layers1/5/10/20/46/92_orig.sh`）。
- **N=0（baseline）特例**：driver 直接**不掛 `--post-cold-script`** → 第 ⑤ 步跳過 → 純冷啟動。
- **前置**：classify.csv，免 warmup。
- **掃什麼**：**掃 N**。sparse 掃 `0,1,5,10,20,46,92`（[runmatrix_Nsweep_orig_a.sh:10-28](layout_rewriter/runs/runmatrix_Nsweep_orig_a.sh#L10)）；
  後來又補了 dense `N=0..92` 全掃（[runmatrix_Nsweep_FULL.sh](layout_rewriter/runs/runmatrix_Nsweep_FULL.sh)）。
- **驗什麼**：把不同 N 的 first_query_us 連起來 → 畫出那條 **U 型曲線**，找甜蜜點。

## 2d access（歷史派）

- **第 ⑤ 步跑**（[prefetch_2d_a_orig.sh](prefetch_access/runs/prefetch_2d_a_orig.sh)）：
  ```sh
  prefetch_access  test.db  classify.csv  hotpages_a.csv  0  0  4096
                                                          ↑  ↑
                                              cap_interior 0=全部 ; cap_leaf 0=不載 leaf
  ```
  → 把 classify 的 interior ∩ hotpages 的 resident 取交集，只載「被用過的 interior」；`cap_leaf=0` 代表 2d 模式（跳過 leaf）。
- **前置**：✅ **先跑 warmup pass 產生 `hotpages_a.csv`**（見第二部分）。
- **掃什麼**：不掃（2d 沒參數）。
- **driver**：[runmatrix_2d.sh](prefetch_access/runs/runmatrix_2d.sh)（A/B/C × 3 layout）。
- **驗什麼**：看 ⑥ 跟 syscall 數——2d 用極少的 madvise（4–26 道）就把對的 interior 全命中。

## 2e access + top-K（歷史派）

- **第 ⑤ 步跑**（[prefetch_2e_C_orig_K10.sh](prefetch_access/runs/prefetch_2e_C_orig_K10.sh)）：
  ```sh
  prefetch_access  test.db  classify.csv  hot2e_C_orig_K10.csv  0  10  4096
                                                                    ↑
                                                          cap_leaf=K=10（多載 10 個熱 leaf）
  ```
- **前置**：✅ warmup pass，**外加一步** [gen_hotleaves.py](prefetch_access/runs/gen_hotleaves.py)：
  它解析每個 leaf page 的 rowid 範圍、數 workload 裡每個 key 的查詢次數、把 key 映射到 leaf page、
  取**最熱的前 K 個 leaf**，再跟 resident interior 疊起來，輸出 `hot2e_*_K*.csv`。
  （所以 2e 的「熱葉」是**按 workload key 頻率算出來的**，不是亂挑。）
- **掃什麼**：**掃 K** ∈ `10,50,100,500`，× A/B/C × 3 layout × **6 reps**
  （[runmatrix_2e_abc.sh](prefetch_access/runs/runmatrix_2e_abc.sh)）。
- **驗什麼**：K 越大載越多熱葉、first_query 越低，但 syscall 越多——找「最少 syscall 抓最多熱葉」的點（C 上 K=10 就 −82%）。

## 3a / 3b ratio（歷史派）

- **第 ⑤ 步跑**：跟 2e **同一支程式、同一套前置**，只是把 **K 固定成 40（3a）或 92（3b）**
  （`prefetch_2e_*_K40.sh` / `prefetch_2e_*_K92.sh`），用來控制 interior : leaf 的比例（7:3 / 5:5）。
- **前置**：✅ 同 2e（warmup + gen_hotleaves，K=40/92）。
- **掃什麼**：固定 K=40 / 92（不算掃，是兩個指定點）。
- **driver**：[runmatrix_2e_ratio.sh](prefetch_access/runs/runmatrix_2e_ratio.sh)。
- **這一維是「對照實驗」不是新策略**：原 spec 想用「interior:leaf 比例」當旋鈕（3a=7:3、3b=5:5），
  換算成 K=40 / K=92。第十七維補跑來驗證「**比例是不是決定 first-q 的主軸**」——
  結論是**不是，K 才是；比例只是 K 的副產品**。而且因為 2e 只載 resident interior（4–32 個、
  不是全 92 個），實際比例嚴重偏離 spec（C×1a 的 K=40 實際是 4:40 ≈ 9:91，不是 7:3）。
  **沒有任何 (workload, layout) 把 3a/3b 選為單獨最佳**——它存在的價值就是否證「比例軸線」。
  細節見 [overall_results.md 第十七維](overall_results.md#L1351)。

## 2f SLRU（歷史派）

- **第 ⑤ 步跑**（[prefetch_slru_a.sh](prefetch_slru/runs/prefetch_slru_a.sh)）：
  ```sh
  prefetch_slru  test.db  hotpages_a.csv  4096
  ```
  → 讀 hotpages，**只要 `is_resident==1` 就 `madvise`，不分 interior/leaf，整個熱頁集全載**。
- **前置**：✅ warmup pass（這裡的 `hotpages.csv` 是**整份 residency dump**，不過濾種類）。
- **掃什麼**：不掃（全載就是全載）。
- **driver**：[prefetch_slru/runs/runmatrix.sh](prefetch_slru/runs/runmatrix.sh)（baseline / layers5 / slru × workload × 3 reps）。
- **驗什麼**：這支 driver **特別額外記 `prefetch_us` 跟 `n_prefetch`**（從 prefetch 程式 stderr 抓）——
  因為 2f 的重點就是「first_query 最快（−94%）**但** prefetch 自己花 1.2–1.8 ms」這個反差，
  非看 prefetch overhead 不可。

---

## 一張圖總結整條流程

```
外層 driver 迴圈（掃 N / K / 或單一 arm × 多 reps）
     │  每一格呼叫一次 ↓
     ▼
benchmark_harness（七個策略共用）:
  ① mmap + 數頁(before)
  ② sync
  ③ madvise(COLD/PAGEOUT/DONTNEED)  ┐
  ④ posix_fadvise(DONTNEED)          ┘ 製造全冷快取（無 sudo）
  ⑤ post-cold-script  ← 換這支腳本 = 換策略：
        2a/2b → prefetch ... range/perpage      （只讀 classify）
        2c    → prefetch_layers ... N 4096       （只讀 classify）
        2d    → prefetch_access ... 0 0 4096      ┐
        2e    → prefetch_access ... 0 K 4096      │ 需先跑 warmup pass
        3a/3b → prefetch_access ... 0 40/92 4096  │ 產生 hotpages.csv
        2f    → prefetch_slru ... hotpages.csv    ┘
  ⑥ 數頁(after) → 驗證載進來了
  ⑦ 逐筆跑 SQL 計時 → 記 first_query_us / avg_us / majflt
     │
     ▼
取多 reps 中位數 → 填進 overall_results.md 的結果表 / 畫成曲線
```

**一句話：七個策略用的是同一台引擎，差別只在第 ⑤ 步插哪支 prefetch 程式；結構派（2a/b/c）直接讀 classify，歷史派（2d/e/f）要先跑一遍 warmup pass 拿到 hotpages 才能測。**
