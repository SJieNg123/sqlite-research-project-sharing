# Prefetch Warmer（Level 1）實作報告 — 發生了什麼事

> 這份報告完整記錄 `prefetch_warmer/` 這個子專案：為什麼做、做了什麼、怎麼量、量到什麼、以及哪些是
> 誠實該標註的限制。結果優先，技術細節隨後。配套檔案見文末「§8 檔案與重現」。

---

## 1. 一句話結論

我們把「凍結 hotpages 清單」這個研究原型，往「可運作的真系統」推進了一步：實作了一支 **stateless 冷啟動
prefetch warmer**，並用**嚴謹的 ablation 量測（每臂 30 次）**證明——

> **開機前先把 92 個 interior 頁暖進 OS page cache，能把冷啟動第一筆查詢從 508 µs 砍到 118 µs（−77%）。**
> **但「暖」不是免費的**：用 `pread` 同步暖要花 8 ms，一旦卡在關鍵路徑反而淨虧；用 `fadvise` 非阻塞暖幾乎免費，
> 但只砍到 −33%。所以 **TTFQ 必須報「樂觀 / 保守」兩個版本**，不能只挑 −77% 那個好看的講。而且 **hot-leaf 對第一筆
> 查詢是 null result（沒幫助）**。

---

## 2. 為什麼做這個（背景）

本 repo 既有的 prefetch 原型（`prefetch_access` / `prefetch_slru` / `prefetch_churn`）都用一張
**t=0 拍一次、之後凍住不更新**的 hotpages 清單。我們在前面的工作中發現兩個問題：

- **會過期（decay）**：`prefetch_churn/runs_page_split/` 實測證明——一旦 churn 會搬頁（row 撐大造成 leaf split、
  或 VACUUM），凍結清單的命中率 `hot_key_coverage` 從 24% 崩到 0.9%（VACUUM 下 → 0.3%）。
- **有作弊嫌疑**：hot-leaf 是拿待測 workload 自己 profiling 出來的（train/test 重疊）→ 命中率虛高、是上界。

所以開了 `prefetch_warmer/` 這個**只做 Level 1（application + OS 層）**的子專案，目標是把它做成真的會跑、會量到
改善的東西，並用嚴謹方法誠實量「到底有沒有用、用多少、代價多少」。（**Level 2 = FEMU / NVMe 物理隔離，明確不做。**）

---

## 3. 環境盤點（Phase A0，見 [PLAN.md](PLAN.md)）

實測機跑出三個會綁住設計的硬約束：

| 項目 | 實測 | 影響 |
|---|---|---|
| 是不是 root | **否（uid 1004）** | 不能 system-wide drop cache → 冷啟動只能用 `posix_fadvise(DONTNEED)` evict（沿用既有工具）|
| liburing | **沒裝**（但 kernel 6.17 支援 io_uring）| warmer 主路徑改用 `posix_fadvise`/`pread`；io_uring 列為加分項，不擋主線 |
| SQLite | amalgamation 在 `benchmark_harness/sqlite3.{c,h}` | 之後 VFS 直接編這份 |
| write-hint | 只有 `fcntl(F_SET_RW_HINT)`、且 per-inode（整檔）、無 per-page hint | 坐實「Level 1 不注入真 per-page kernel hint，shadow tagging 純 metadata」|

---

## 4. 做了什麼（系統）

### 4.1 O(1) 頁面分類器（Phase A1，[src/page_classify.c](src/page_classify.c)）

一支只看「b-tree 頁型別旗標 byte」就分類的函式：`0x05/0x02` → INTERNAL、`0x0D/0x0A` → LEAF、其餘 → OTHER；
page 1 的旗標在 100-byte 檔頭之後（看 `buf[100]`）。**零 I/O、不走 freelist**（紅線 F2）。附 unit test，全綠
（含 page-1 特例與偽陽性邊界）。這是之後 runtime VFS 與 offline 工具共用的核心。

> 目前 hotset 還是走既有 `classify_pages` 的 **oracle 路徑**（離線精確分類）。live shadow-tagging VFS（寫入時即時
> 維護活表）是 production 路徑，列為未做（§7）。用 oracle 路徑不影響「量 warmer 改善」這件事，而且 interior 是
> **結構推出來的、無 query 歷史 = 無作弊**。

### 4.2 Stateless 冷啟動 warmer（Phase A2，[src/warmer.c](src/warmer.c)）

一支獨立小程式，由量測 harness 在「SQLite 開檔之前」執行：

- 讀一張 hotset（`page_number,file_offset`），把那些頁**暖進 OS page cache**。
- **開自己的 fd**（此時 SQLite 還沒 open，沒鎖衝突，紅線 F1）；**不自存頁面內容**（scratch buffer 用完即丟，
  紅線 F4）——只暖 OS page cache，SQLite 之後常規讀取自然命中。
- 兩種暖法（env `WARM_METHOD` 切換）：
  - **`pread`**：實際把 bytes 讀出來，**保證頁 resident**，但**同步阻塞**。
  - **`fadvise`**：`posix_fadvise(WILLNEED)` 發非阻塞提示，**幾乎不花時間**，但實際 I/O 在背景非同步發生、不保證
    第一個 query 來之前讀完。
- env `WARM_MODE=off` 當 baseline（同一支程式、不暖，符合「baseline/treatment 同程式」原則）。

### 4.3 兩張 hotset（[runs/](runs/)，由 `classify_pages` 產）

- **L1 = 全部 92 個 interior 頁**（結構派，無作弊）。
- **L5 = 92 interior ＋ 10 個 hot leaf**（hot leaf 是史派、有 train/test 顧慮；L5 是 L1 的超集，方便疊加）。

---

## 5. 怎麼量的（Phase A3，ablation）

**量測設計成 ablation ladder**：從 baseline 開始一層一層加技術，每層獨立 env 開關，看每層的**增量**貢獻。

- DB：`prefetch_access/runs/test.db`（60 萬列、~103 MiB、4 KiB 頁）；workload：`workload_a_zipfian.txt`（Zipfian 點查）。
- 每 rep 流程：`evict`（fadvise DONTNEED 冷快取）→ warmer（post-cold-script）→ `benchmark_harness` 開 SQLite 量
  first-query / avg / majflt。
- **嚴謹度**（守 §2 of README）：**每臂 30 reps**、報 **median / p95 / p99 / min / stdev**、cold start 看尾端、
  **TTFQ 報樂觀＋保守兩版**、null result 照實寫。冷啟動是**真的冷**（majflt ≈ 180，有真 I/O）。

---

## 6. 結果（150 reps）

| 臂 | 暖什麼 / 怎麼暖 | median µs | p95 | p99 | stdev | warm 成本 µs | **TTFQ 樂觀** | **TTFQ 保守** |
|---|---|--:|--:|--:|--:|--:|--:|--:|
| **L0** | baseline，不暖 | 508 | 518 | 530 | 30 | 0 | 508 | 508 |
| **L1** | 92 interior，**pread** | **118** | 140 | 141 | 9 | **8028** | **118（−77%）** | **8146（＋1503%）** |
| **L1** | 92 interior，**fadvise** | 340 | 353 | 361 | 21 | 161 | **340（−33%）** | **500（−2%）** |
| **L5** | ＋10 hot leaf，pread | 117 | 142 | 159 | 12 | 8767 | 117（−77%） | 8883 |
| **L5** | ＋10 hot leaf，fadvise | 339 | 358 | 391 | 26 | 168 | 339（−33%） | 507 |

> TTFQ 樂觀 = 只算 first-query（假設 warmer 在背景/啟動空檔跑完）；TTFQ 保守 = first-query ＋ warmer wall-clock
> （假設 warmer 卡在關鍵路徑）。

### 四個發現（誠實版）

**① 暖 interior 確實大砍 TTFQ。** 508 → 118 µs（−77%），而且很穩（stdev 9、p99 才 141）。
原理：點查的路徑是 root → interior → leaf；baseline 第一筆要現場 fault 那些 interior 頁，暖過就省掉了。

**② 但「暖」要花時間，pread vs fadvise 是整個故事的核心取捨。**
- `pread` 同步暖 92 個**冷**頁要 **8 ms**（92 次隨機冷讀）。first-query 雖然只剩 118 µs，但若 warmer 卡在關鍵
  路徑，**保守 TTFQ = 8146 µs，比 baseline 還慢 16 倍**。→ pread 暖法**只有在有啟動空檔可重疊時才划算**。
- `fadvise` 非阻塞，暖只花 161 µs，保守 TTFQ ≈ 500 µs ≈ **打平 baseline**；代價是 first-query 只降到 340 µs
  （−33%，因為非同步 readahead 在第一筆來之前還沒讀完）。
- → **真相落在兩版之間**：要「保證便宜」選 fadvise（−33%、近乎免費）；要「最快 TTFQ」且確定有空檔才選 pread。

**③ hot-leaf 對第一筆查詢是 null result。** L5 比 L1 只差 1 µs（118→117 / 340→339）。因為第一筆是**單點**查詢、
只碰**一個** leaf，那個剛好是不是熱葉是碰運氣——多暖 10 個熱葉對「第一筆」幫不到。守紅線 F10：沒幫助就照實寫。

**④ warmer 是把 I/O「搬走」不是「消滅」。** 五臂 `majflt` 幾乎不動（177–181），而且 **avg 穩態延遲五臂都是
2.04 µs**——warmer 對整段 workload 的吞吐毫無影響，**好處 100% 集中在第一筆（TTFQ）**。pread 那 8 ms 就是被搬到
warmer 階段的冷讀 I/O。→ 這招只對「**反覆冷啟動、在意第一筆延遲**」的場景（serverless / 短命 process）有意義；
對長壽進程無感。

> 註：上面 ①–④ 的數字是首批（5 臂）。後續補做了 **L2 tree-top（8 臂、240 reps）** 與 **L3/L4 線上預取（90 reps）**，
> 完整表格與下面 ⑤⑥ 的數字以 [runs/README.md](runs/README.md) 為準（baseline 從 508 微調到 510，結論一致）。

**⑤ L2 tree-top ＝ 成本/效益旋鈕，但沒有免費的 −78%。** 只暖 3 個 root（near-free，warm 213 µs）只買到 −19%；
只暖「查詢真的會走的那棵 items 樹」51 頁 ＋ fadvise（warm 僅 92 µs）買到 −35%、**保守 TTFQ 425 µs 是全表最低**。
反直覺點:**精準只暖 51 頁的 items 子樹,first-query(334)反而輸給全暖 92 頁的 L1 pread(113)**——因為 pread 全部 92 個
散落 interior 時,kernel readahead 順手把查詢要的 leaf 也帶進來了;targeted 省了成本、也丟了這個附帶紅利。

**⑥ 線上 pointer-ahead / fan-out（L3/L4）對點查詢是負結果。** 自寫 VFS（[src/trav_bench.c](src/trav_bench.c)）邊走訪邊
預取 child:讀一個 interior 頁有 **499 個 child**,但點查詢只 descend **1 個** → VFS 不知 key 只能全預取 499 個 →
**fan-out（pread）慢 40 倍、pointer-ahead（fadvise）慢 1 倍**。正是投影片警告的「過度預取」。線上預取要有用得**語意感知
（只取要走的那個 child）**或只用於 **range scan**。（兩家 baseline 不同:warmer 家族 510 µs vs 線上家族 186 µs,不可跨比。）

---

## 7. 限制與未做（下一步）

- ✅ **已補做（見 [runs/README.md](runs/README.md)）**:L2 tree-top（root-only / items-only × pread/fadvise）、
  L3/L4 線上預取(VFS)。發現如 ⑤⑥。
- **A1 live shadow-tagging VFS**：目前 hotset 走 `classify_pages` oracle；寫入時即時維護活表是 production 路徑。
- **decay 偵測對照**：接 `prefetch_churn/measure_staleness.py` + `runs_page_split`，驗 sidecar 內的 file change
  counter 能在 DB 動過時偵測過期 → 降級/跳過，而非靜默暖錯頁。
- **量測本身的已知限制**：本批冷啟動是真的冷（majflt≈180）；但 workload 是單一 Zipfian 點查，single-process。
  不同 workload / 並發下的數字未測。

---

## 8. 檔案與重現

```
prefetch_warmer/
  README.md                  主控執行文檔（Level 1、紅線、Phase 規劃）
  PLAN.md                    A0 環境盤點
  prefetch_warmer_report.md  本報告
  src/
    page_classify.{c,h}      A1 O(1) 分類器
    test_page_classify.c     A1 unit test（ALL PASSED）
    warmer.c                 A2 stateless warmer（pread/fadvise）
  runs/
    hotset_internal.csv          L1：92 interior（結構派）
    hotset_internal_hotleaf.csv  L5：92 interior + 10 hot leaf
    warm_wrapper.sh / cold.sh    post-cold-script / evict
    run_ablation.sh              5 臂 × 30 reps
    aggregate.py                 median/p95/p99 + 雙版 TTFQ
    ablation_raw.csv             原始 150 筆
    ablation_summary.txt         彙總表
    README.md                    結果詳解
```

重現：
```sh
cd prefetch_warmer/src && gcc -O2 page_classify.c test_page_classify.c -o test_page_classify && ./test_page_classify
gcc -O2 warmer.c -o warmer
cd ../runs && bash run_ablation.sh && python3 aggregate.py ablation_raw.csv
```
