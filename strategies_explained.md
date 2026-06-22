# 七個 Prefetch 策略 — 怎麼測出來的（測試流程詳解）

> 這是 [overall_strategies.md](overall_strategies.md) 的**測試流程伴讀版**。
> overall_strategies.md 講「每個策略是什麼」、[overall_results.md](overall_results.md) 講「結果數字」；
> 本檔講「**每個策略到底是怎麼被測出來的**」——從清空快取、插入 prefetch、到量第一筆延遲。

> **⚠️ 2026-06-22：本檔描述的是 P1 era 的測試引擎（`evict`/`posix_fadvise` 冷清、native prefetch tool 直接交付）。
> Master rerun 改用 [P0 pipeline](IMPLEMENTATION_PIPELINES.md)（[`run_p0.py`](run_p0.py)），差異為:
> ① 冷清一律全機 `/usr/local/sbin/drop-caches`（setuid、免 sudo）取代 `posix_fadvise`;
> ② 殘留驗證走 harness 內建 `--verify-hotset`（`cold_pct`/`delivery_pct`）取代外部 `residency_checker`;
> ③ 交付統一走 `warmer`（pread oracle / async hint 雙臂），native tool 降為離線 hotset 產生器;
> ④ 每 (workload,layout) 加 no-prefetch **baseline** 當分母;`cold_pct>1%` 剔除、op[0]=read 強制、釘核升頻、ra=128。
> 下面的步驟敘述保留作 P1 歷史對照。**正式重跑請以 P0 為準。**

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
benchmark_harness --db test.db --workload workload_a_zipfian.txt \
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
>
> **驗證：「同一份 workload」不是說法，是檔案層級可證的**（md5 對得起來）：
>
> | 步驟 | 指令 / 檔案 | 用的 workload |
> |---|---|---|
> | ① 暖機產 hotpages | [`warmup.sh workload_a_zipfian.txt hotpages_a.csv`](prefetch_slru/runs/warmup.sh)（見 [PREFETCH_SLRU.md:44](prefetch_slru/PREFETCH_SLRU.md#L44)）| `workload_a_zipfian.txt` |
> | ② 正式測試（量測） | [`runmatrix_2d.sh:8`](prefetch_access/runs/runmatrix_2d.sh#L8)：`benchmark_harness --workload $WL_A`，第 ⑤ 步讀 `hotpages_a.csv` | `workload_a_zipfian.txt` |
>
> - **同一份 workload 檔**：兩派的 `workload_a_zipfian.txt` 都是 symlink，最後都指到同一個
>   `benchmark_harness/workloads/workload_a_zipfian.txt`（md5 `af98ec1…`，兩邊相同）。
> - **同一份 hotpages 檔**：`hotpages_a.csv` 全專案只有一份實體檔（`prefetch_access/runs/` 那份是
>   symlink），2d / 2e / 2f 共用（md5 `4c54f44…`）。
> - **所以「重新測試」= 同一份 query 序列被跑兩次**：第一次當 warmup（`--cold-advice none`，
>   不 prefetch、只老實把頁拉進快取）→ mincore dump 成 hotpages；第二次當被量測的 cold-start 測試。
> - **唯一隨 layout 變的是 hotpages，不是 workload**：每個 layout 各一份
>   （`hotpages_a` / `hotpages_a_vacuum` / `hotpages_a_ta`），因為頁面 offset 隨佈局改變——
>   workload 相同，但 DB 佈局不同要各暖機一次。

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

---

# 第四部分：幾個深入疑問（Q&A）

> 前三部分講「怎麼測」，這節收錄讀這套方法時最容易卡住、也最該追問的三個問題——
> 它們講的是「這樣測到底站不站得住」。

## Q1. 2e/3a/3b 的「最熱 K 個 leaf」是誰挑的？為什麼說它是「寫死」的？

挑熱葉的**不是** C 程式（[prefetch_access.c](prefetch_access/src/prefetch_access.c) 只照清單 madvise、不思考），而是前置腳本
[gen_hotleaves.py](prefetch_access/runs/gen_hotleaves.py)。它在做「把 key 翻譯成頁」——因為 workload 只講 key
（`read 150`），但 prefetch 要的是頁號。走一遍（假設一頁裝 100 筆）：

1. **建 rowid→頁 對照表**：用 dbstat 列出每個 leaf 頁，只讀它「第一個 rowid」。頁 A 從 1 開始、
   頁 B 從 101 開始…… 知道每頁開頭就夾得出範圍（A=1~100、B=101~200）。查 key=150 → 落在頁 B。
2. **數 key 頻率**：掃 workload，`read 150` 出現 3 次 → `keycnt[150]=3`。
3. **熱度彙總到頁、取前 K**：key 150 的 3 次算到頁 B → `leafcnt[B]+=3`，最後 `most_common(K)` 取最熱的 K 頁。
4. **寫成靜態 CSV**：把這 K 頁（加上 resident interior）標 `is_resident=1`，凍進 `hot2e_*_K*.csv`。

**「寫死」的意思**：這整套**只在量測前算一次、結果凍成檔案**，量測當下不重算。所以它是一張「事先算好的
標準答案卡」——這也是為什麼它是 **best-case 上界**：答案卡是拿**待測的同一份 workload** 算的
（步驟 2 數的就是它），等於考前看了考卷。

## Q2. 資料被 churn（一直改）之後，那張凍結的熱頁清單還準嗎？

**問題**：我們事先做好一張「開機先載這幾頁」的清單，做完就**凍住不改**。後來資料庫被改了 5 萬次。
那這張清單，還指著當初最熱的那幾頁嗎？還是早就對不上了？

**量出來的結果：還是準。** 改 5 萬次、每 5 千次量一次
（[run_access_churn.sh](prefetch_churn/runs_access_churn/run_access_churn.sh)），2e_K10 的第一筆查詢全程都在
~15–43 µs，**沒有越改越慢**。

**為什麼？這次直接翻數據驗證、不用猜。** 這個實驗每次都存了一張「現在每頁是什麼」的快照，比對 churn 前後：

| 驗的東西 | 結果 |
|---|---|
| 原本 26,331 頁，有幾頁位置變了？ | **0 頁**（種類、檔案位置全沒動）|
| 新資料加在哪？ | **全加在最後面**（新頁號 26332 以後；舊頁號完全沒動）|
| 清單上那 14 個熱頁，種類有變嗎？ | **沒有**（churn 前後一模一樣）|

→ 原本的熱頁**位置一動都沒動**，清單當然照樣指對。原因是 SQLite 很「懶」：**刪**資料只在原頁留個空洞、
**加**資料全開在檔尾新頁、**改**值原地蓋掉——舊頁都不搬家。

> ⚠️ **但這裡有個大前提，這也是這個結論最弱的地方：**
>
> 清單會準，**完全是因為這場 churn 剛好不搬頁**。實驗腳本自己說它在測「DB layout 漂移」，但數據顯示
> layout 根本沒漂移（0 頁移動、只在尾巴長）。**等於它測出「不衰退」，是因為根本沒有漂移可以衰退——
> 不是清單撐過了壓力測試。** 換一個**會搬頁**的 workload，結果就可能完全不同：
>
> - **VACUUM／重建**：整個 DB 重寫、頁號全部重編 → 清單整張作廢。
> - **往熱區中間狂 insert**：把熱頁塞爆 → 分裂 → 一半熱資料搬到新頁，清單指著舊頁、漏掉搬走的。
>   （這次 insert 全接尾巴，剛好避開了這個。）
> - **把 row 改大的 update**：撐爆頁 → 同樣分裂。
>
> 原本這幾種都**沒測**——後來補做了一個**故意會搬頁**的 churn 來補這個洞（見下方「補測」）。

**補測：造一個會搬頁的 churn，清單真的 decay 了**（[runs_page_split/](prefetch_churn/runs_page_split/README.md)）

把 churn 改成「**對 workload A 的熱 key 做 update，且 `--payload-size 512` 把 row 撐大**」——near-full 的熱頁被撐爆 →
分裂 → 熱 key 搬到新頁。用新加的 `hot_key_coverage` 指標（讀取命中凍結清單的比例）量 decay：

| 寫入量 | 撐大版（payload 512，會分裂）| 對照：同樣打熱 key 但不撐大（payload 100）|
|---:|:--:|:--:|
| 0 | 24.1% | 24.1% |
| 1 萬 | 11.2% | 24.1% |
| 5 萬 | **0.9%** | **24.1%** |

→ 會搬頁的 churn 把命中率**從 24% 砸到 0.9%（約 27 倍衰退）**；**只打熱 key 但不撐大**的對照組**全程平平 24.1%**
（row 原地改寫、不分裂）——證明 **decay 的兇手是「頁分裂」，不是「打到熱 key」**。`page_count` 也從 26,331 漲到
28,779（row 數全程 600,000 沒變，純分裂）。**VACUUM 更狠**：對**沒 churn 過**的 DB 直接 VACUUM（一筆資料都沒改、
只重編頁號），命中率 **24% → 0.3%** 瞬間崩。

> ⚠️ 但 latency 在這裡**不是乾淨的訊號**：`first_query` 在 ~15–25 µs 抖、`majflt` 只小漲——因為這台 harness 的
> 無 sudo 冷啟動沒把撐大的 DB 完全趕出快取，跑得偏 warm，清單失準沒被罰到時間上。**decay 的結論看 `hot_key_coverage`
> （直接量清單對不對），不要看 latency 欄。**

（附帶更正：原本 runs_access_churn 中 15k 那根 **212 µs** 我一度猜是「頁分裂」——但佈局快照顯示那場 churn 沒有任何頁
移動，所以那根站不住，只是量測雜訊；真正的頁分裂要像上面這樣**刻意撐大 row** 才會發生。）

> **上面三行表格可以自己跑來驗**（不用信我，在 repo 根目錄執行）：
>
> ```sh
> cd prefetch_churn/runs_access_churn/2e_k10/checkpoints
> B=classify_pages_baseline.csv; C=classify_pages_checkpoint_010.csv
>
> # ① 舊頁有沒有變：比對共有的 26331 頁 → 印 0 = 種類+位置一字不差
> diff <(head -26332 "$B") <(head -26332 "$C") | grep -c '^[<>]'
>
> # ② 新資料加在哪：兩檔最大頁號 → 26331 vs 27056（新頁全接尾巴）
> for f in "$B" "$C"; do awk -F, 'NR>1{m=$1} END{print FILENAME, m}' "$f"; done
>
> # ③ 14 個熱頁種類前後比對 → 每行都印 same
> HOT=../../../../prefetch_access/runs/hot2e_C_orig_K10.csv
> awk -F, 'NR>1&&$2==1{print $1}' "$HOT" | while read p; do
>   b=$(awk -F, -v p=$p '$1==p{print $2}' "$B")
>   c=$(awk -F, -v p=$p '$1==p{print $2}' "$C")
>   echo "$p $b $([ "$b" = "$c" ] && echo same || echo CHANGED)"
> done
> ```
>
> ⚠️ **這份快照只記每頁的 `頁號 / 種類 / 檔案位置`，不記「哪些 row 在哪一頁」。** 所以它證的是
> 「頁面佈局沒搬」這半；「熱頁仍是對的預載目標」那半要靠**延遲**（churn 全程 ~15–43 µs 沒爛）來補。
> 兩份證據合起來，才撐住「清單沒過期」這個結論。
