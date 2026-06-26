# 主控執行文檔：Type-aware Shadow-tagging VFS + Prefetch Warmer（**Level 1 only**）

> 參考 [type_aware_physical_segregation/README.md](../type_aware_physical_segregation/README.md) 的 PART A，
> 抽成一個**獨立、只做 Level 1** 的子專案。**Level 2（FEMU / NVMe passthrough / 物理隔離）明確不做**——
> 見文末「§X 明確排除」。之後這個方向的所有程式與實驗，都開在本資料夾底下的子目錄。

---

## 進度

| Phase | 狀態 | 產出 |
|---|---|---|
| **A0** 探索/環境盤點 | ✅ 完成 | [PLAN.md](PLAN.md)（非 root、無 liburing、amalgamation 位置、write-hint 實測）|
| **A1** page_classify O(1) 模組 + unit test | ✅ 完成 | [src/page_classify.{c,h}](src/page_classify.c)、[src/test_page_classify.c](src/test_page_classify.c)（ALL PASSED）|
| **A1** shadow-tagging VFS（live 活表）| ⬜ 未做 | hotset 暫走 `classify_pages` oracle 路徑（結構派、無作弊）|
| **A2** stateless warmer（fadvise/pread）| ✅ 完成 | [src/warmer.c](src/warmer.c) + [runs/hotset_*.csv](runs/) |
| **A2.5/L3-L4** 線上預取（pointer-ahead / fan-out）VFS | ✅ 完成 | [src/trav_bench.c](src/trav_bench.c)（自寫 VFS shim）|
| **A3** ablation **L0/L1/L2/L5**（batch warmer，240 reps）| ✅ **有結果** | **[runs/README.md](runs/README.md)** Part A |
| **A3** ablation **L3/L4**（線上預取，90 reps）| ✅ **有結果** | **[runs/README.md](runs/README.md)** Part B — 點查詢下是負結果 |
| **A1** live VFS / **decay 對照** | ⬜ 未做 | 下一步 |

**結果一句話**：暖 interior 把冷啟動第一筆砍 **510→113 µs（−78% pread）/ −34%（fadvise）**，但 pread 的 8 ms 暖成本在
關鍵路徑上會淨虧 → **TTFQ 兩版都報**；最划算折衷是 **L2「只暖查詢那棵樹＋fadvise」（−35%、保守僅 425 µs）**；
hot-leaf（L5）對第一筆 = null；**線上 pointer-ahead/fan-out（L3/L4）對點查詢 = 負結果（過度預取，fan-out 慢 40 倍）**。
詳見 [runs/README.md](runs/README.md)。

---

## 0. 這個資料夾在做什麼、為什麼要做

### 動機（接續本 repo 既有發現）

既有的 prefetch 原型（[prefetch_access/](../prefetch_access/)、[prefetch_slru/](../prefetch_slru/)、
[prefetch_churn/](../prefetch_churn/)）用的 hotpages 清單是 **t=0 拍一張、之後凍住不更新**的。這帶來兩個問題：

1. **會過期（decay）**：[prefetch_churn/runs_page_split/](../prefetch_churn/runs_page_split/README.md) 已實測——
   一旦 churn 會搬頁（row growth 造成 leaf split，或 VACUUM），凍住清單的命中率
   **`hot_key_coverage` 從 24% 崩到 0.9%**（VACUUM 下 → 0.3%）。
2. **有作弊嫌疑（train/test 重疊）**：hot-leaf 是拿待測 workload 自己 profiling 出來的 → 命中率虛高、是上界。

本資料夾把它升級成**可運作的真系統**，對症兩個問題：

- **寫入時即時維護 hotset（shadow tagging）** → 清單跟著 DB 走，不再事後重掃、也不靠「紀律禁止寫入」。
- **cold start 用 file change counter 偵測過期** → 從「靠紀律」升級成「靠機制偵測」，不符就 best-effort/跳過。
- **stateless warmer，只暖 OS page cache** → 沒有第二份資料副本、沒有 cache coherence 問題。
- **hot-leaf 嚴格 train/test 切分** → 直接消掉作弊嫌疑（紅線 F11）。

### 範圍

- ✅ **Level 1 = application + OS 層**：type-aware shadow-tagging VFS、獨立 prefetch warmer、嚴謹 cold-start 量測。
- ⛔ **Level 2 不做**：FEMU emulator、NVMe passthrough、namespace / LBA identity mapping、temperature stream、
  物理隔離——全部排除（見 §X）。

---

## 0.1 與既有資產的關係（重用，不重造）

| 既有資產 | 在本子專案的角色 |
|---|---|
| [classify_pages/classify_pages.c](../classify_pages/) | 重構出共享 **O(1) `page_classify`** 模組（VFS 與 offline 共用）；精確版（走 freelist）保留為 **oracle**，用來驗活表正確性、算 precision/recall、活表不可用時 fallback。 |
| [benchmark_harness/](../benchmark_harness/) | 沿用做 cold-start 量測（`--cold-advice`、`--drop-caches-script`、ops/latency/majflt）。 |
| [residency_checker/](../residency_checker/) | 驗證 warmer 真的把目標頁暖進 page cache（mincore）。 |
| `layout_rewriter/runs/evict`（posix_fadvise DONTNEED）| 無 sudo 冷啟動的 evict 工具。 |
| [prefetch_churn/measure_staleness.py](../prefetch_churn/measure_staleness.py)（本 session 新增）| 當 warmer 的**健康檢查 / coverage 尺**：量 live 清單對不對、以及偵測 decay。 |
| [prefetch_churn/runs_page_split/](../prefetch_churn/runs_page_split/README.md)（本 session 新增）| **decay baseline / 動機**。新 warmer 要證明：同樣的搬頁 churn 下，靠 file change counter 能偵測並降級，而不是靜默暖錯頁。 |

---

## 0.2 設計原則

1. **baseline 與 treatment 同一份程式**，用 env var 開關（不要 fork 兩份）。
2. **不美化、不灌水**；null result 是有效結果（紅線 F10）。
3. **warmer 必須 stateless**：只暖 OS page cache，不自存頁面內容（紅線 F4）。
4. **不 over-engineer**：這是 PoC 級別的研究實作，不是 production server。
5. **檔案都在本資料夾底下的子目錄**（`src/`、`runs/`、`PLAN.md`…），不要散落到 /tmp、家目錄。

---

## 0.3 紅線（Level 1 子集，違反會毀掉專案）

> 取自 template §0.2，只留 Level 1 相關（拿掉 F7–F9 那些 Level 2 NVMe 條目）。

| # | 禁止 | 為什麼 |
|---|------|--------|
| F1 | VFS 自開任何指向 DB 檔的 `fd` | POSIX advisory lock：同 process `close()` 掉指向該 inode 的任一 fd，會釋放該 process 在該 inode 的**所有**鎖 → 摧毀 SQLite 的鎖 → `SQLITE_BUSY`/損毀。一律委派 parent xWrite。 |
| F2 | VFS 內走訪 freelist 分類 | O(N) 同步 I/O，會讓寫入崩潰/死鎖。VFS 只能用 O(1) byte-signature，猜不到就 OTHER。 |
| F3 | 挖 parent VFS 的 `unixFile` 內部 fd | 版本一變就壞。 |
| F4 | warmer/VFS 自建記憶體 cache buffer 存頁面**內容** | 自有 data cache 就要負責跟 Pager 維持 coherence，極易讀到舊資料。warmer 保持 stateless。**註：page→class 的 metadata 活表不違反 F4**（只記型別、不存內容）。 |
| F5 | 量到 warm cache | 每次 run 前 drop cache + 開新 process。無 root 不能 drop → harness **大聲報錯中止**，絕不默默量。 |
| F6 | hotset sidecar 過期卻照用 | sidecar 內存 SQLite **file change counter**（header offset 24）；cold start 先比對，不符就 best-effort/跳過、**不重建**（cold start 要快），並 log。不可靜默全用。 |
| F10 | 美化/灌水量測 | null result 有效。 |
| F11 | hot-leaf 的 profile 與 benchmark 用同一批 query | 作弊、命中率虛高。**硬規則：profiling workload 與 cold-start benchmark workload 必須切分（train/test disjoint）**，報告明說 hot-leaf 是 workload-dependent。 |

---

## 1. Phase 規劃（每個 Phase 結束跑收尾流程：編譯過 → 過驗證關卡 → `integrity_check`（若動寫入路徑）→ commit）

### Phase A0 — 探索與環境盤點 → `PLAN.md`
- 確認既有資產真實檔名/輸出格式（`classify_pages` 輸出、`benchmark_harness` flag、evict 機制）。
- 環境實測（結論寫進 `PLAN.md`）：`uname -r`、`gcc`、`id -u`（有無 root）、`liburing` 是否可用（最小 io_uring 讀寫程式）、SQLite 版本/amalgamation。
- **write-hint 實測**（印證「Level 1 不注入真 kernel hint」）：`fcntl(F_SET_RW_HINT)`、`pwritev2 RWF_*`、io_uring SQE 有無 per-I/O hint 欄位。
- **驗證關卡 A0**：`PLAN.md` 含「既有資產盤點 + 環境實測 + 各 Phase 檔案清單」，每個實測項都有實際指令輸出佐證。

### Phase A1 — Type-aware shadow-tagging VFS
- **A1.1 共享 `src/page_classify.{c,h}`**：O(1)、只看 byte signature、零 I/O。規則釘死：page1 看 `buf[100]`、否則 `buf[0]`；`0x05/0x02`→INTERNAL、`0x0D/0x0A`→LEAF、其餘→OTHER。把 `classify_pages.c` 重構成呼叫這份共享模組（offline 額外走 freelist 的精確邏輯保留）。附 unit test。
- **A1.2 `src/type_aware_vfs.{c,h}`（shim）**：`sqlite3_vfs_find(NULL)` 取 parent unix VFS；所有方法委派 parent，只有 `xWrite`（且只對 `SQLITE_OPEN_MAIN_DB`）多分類一步。**嚴禁自開 fd / 挖內部 fd（F1/F3）**。
- **A1.3 shadow tagging = 維護 in-RAM 活表**（page number → class），每次寫入增量更新；build 結束把所有 INTERNAL 頁 `(page_number, file_offset)` 倒成 sidecar `<db>.hotset`，header 寫入當下 file change counter。全程 env 開關。
- **驗證關卡 A1**：跑 workload → `PRAGMA integrity_check`=ok；`kill -9` crash 後重開仍 ok；`page_classify` unit test 全綠；活表產的 hotset 與 `classify_pages.c` oracle 的 INTERNAL 集合比對（記錄偽陽/偽陰）。

### Phase A2 — Prefetch warmer + 線上語意預取（軟體 prefetch）
- **A2.1 hotset 來源**：主路徑 = A1.3 倒出的 `<db>.hotset`；oracle/fallback = `classify_pages.c`。**過期防線（F6）**：warmer 啟動讀當前 DB 的 file change counter 比對 sidecar，不符 → best-effort/跳過、不重建、log。
- **A2.2 stateless warming**：warmer 開**自己的** fd（SQLite 還沒 open，安全），把目標頁暖進 OS page cache 後 close。暖法擇一：io_uring batched read 進「用完即丟 scratch buffer」，或 `posix_fadvise(WILLNEED)`/`readahead()`（要確保 resident 就實際讀 bytes）。**嚴禁自建 data cache（F4）**。
- **A2.3（可選 ablation）hot-leaf**：獨立 profiling pass 在 **training workload** 上對每頁 leaf 累計 read tally → top-K 寫 `<db>.hotleaf`（含 file change counter）。warmer `WARM_HOTLEAF=1` 時一併暖。**train/test 必須 disjoint（F11）**。
- **A2.4 暖的時機（避免拖累 TTFQ）**：env 切換暖法 ∈ {off, top（只同步暖樹頂 root+1~2 層）, full, top+bg（樹頂同步 + 其餘背景）}；預設建議 top+bg。

#### A2.5 線上語意預取（software，query 走訪中邊走邊拉）
> 跟「開檔前批次 warmer」**互補**：warmer 是「開檔前一次暖一批」；這裡是「查詢實際走訪 B-tree 時，邊解析現在這頁、邊把下一層先發出去」。**純軟體、跟著邏輯指標走、與物理佈局無關**，Level 1 即可做。每招獨立 env 開關，供 A3 ablation 疊加。

- **Pointer-ahead prefetch（語意 async prefetch）**：internal 頁本身裝著 child 的頁號。讀到一個 internal、parse 出 child 頁號後，**立刻把那幾個 child async 發出去**（一邊處理現在這頁、一邊背景拉下一層），不要等真的需要才讀。
- **Fan-out 平行讀**：把一個 node 的多個 child **一次平行發出**（io_uring batched），不要一個一個等。
- **（列為對照、不主推）連續性 readahead**：internal 若被物理聚在同一區，多抓旁邊幾頁幾乎免費——但這**需要先有物理聚集**（type-aware layout / 物理隔離），效益依賴佈局，**屬 Level 2 槓桿**。⚠️ **連續 ≠ fan-out**：連續抓的是「物理鄰居」，純隔離下物理鄰居只是「剛好排旁邊的其他 internal」、未必是這個 node 的小孩 → 要真的拿到小孩還是得 fan-out。本 Level-1 子專案**只主推 pointer-ahead + fan-out**；readahead 只在 ablation 當對照、並標註其效益依賴佈局（Level 2）。

> ⛔ 仍守紅線：線上預取也是**只暖 OS page cache / 觸發 readahead，不自存頁面內容（F4）**；不得自開指向 DB 的 fd（F1）——若在 VFS xRead 內做，用 parent 的 fd 或交給獨立 warmer fd。

- **驗證關卡 A2**：用 `residency_checker` 確認目標頁暖進 page cache；counter 不符時確有降級+log；各 env 開關可獨立開合。

### Phase A3 — Ablation 量測（層層疊加看效能）+ 對照
量測設計成 **ablation ladder**：從 baseline 開始一層一層加技術，每層獨立可開關（env），**孤立出每一層的增量貢獻**——不要只報「全開 vs 全關」。

| 層 | 疊加的技術 | 想看什麼 |
|---|---|---|
| **L0** | baseline（無任何 prefetch、純 on-demand fault）| 對照基準 |
| **L1** | ＋ cold-start warmer（批次暖 resident internal）| warmer 本身的貢獻 |
| **L2** | ＋ 樹頂優先暖法（root+上層同步、其餘背景）| 暖法對 TTFQ 的影響 |
| **L3** | ＋ pointer-ahead prefetch（線上語意預取）| 邊走邊拉下一層的貢獻 |
| **L4** | ＋ fan-out 平行讀 | 平行 vs 串列發 child 的貢獻 |
| **L5** | ＋ hot-leaf（可選、train/test 切分）| 觀察式熱葉到底有沒有幫助 |

- 每層對 **baseline 與「上一層」**各報一次增量，疊加曲線一眼看出每招值多少。每層都是同一份程式 + env 開關（§0.2 原則 1）。
- 併入：**活表 precision/recall**（live hotset vs `classify_pages.c` oracle）、**held-out hot-leaf**（profiling 用 train、量測用 test）、**decay 對照**（[measure_staleness.py](../prefetch_churn/measure_staleness.py) + [runs_page_split](../prefetch_churn/runs_page_split/README.md) 的搬頁 churn，驗證 file change counter 能偵測過期並降級，對比凍住清單的靜默 decay）。
- 全部量測**一律遵守 §2 的統計嚴謹度與誠實規則**。
- **驗證關卡 A3**：每層有 drop-cache 佐證、≥20–30 reps、報 median/p95/p99、TTFQ 雙版本、null result 照實寫。

---

## 2. 實驗嚴謹性與誠實規則（所有量測一律遵守）

### 2.1 統計嚴謹度
- 每個條件**至少跑 20–30 次**。
- 報 **median / p95 / p99 / min / stdev**——**不要只報 mean**。
- **cold start 是 tail-sensitive 的，尾端（p95/p99）才是重點**。
- `taskset` 綁核降噪；記錄**機器 / kernel / 檔案系統 / 裝置**。

### 2.2 誠實規則（不可妥協，接 §0.3 F10）
- **數據說什麼就報什麼，絕不美化、不灌水。**
- **null result（沒看到改善）是有效且預期內的結果**——某技術沒幫助就明說並解釋，不要藏。
- ⛔ **嚴禁倒果為因**，例如宣稱「不靠 warmer 就把 TTFQ 降到 warmer 等級」。
- 若某改善其實來自別的因素（例如佈局而非預取本身）→ 明說並拆開。

### 2.3 TTFQ 要報兩個版本（接 warmer 的管線設計，不挑好看的）
我們的管線是「**warmer 先跑 → 才開 SQLite 量 TTFQ**」，所以 warmer 的時間沒被算進 TTFQ。有啟動空檔（warmer 能跟其他啟動工作平行）時這樣量公平；但 warmer 若**卡在關鍵路徑**，就高估了好處。所以**兩個版本都報**：

| 版本 | 定義 | 假設 |
|---|---|---|
| **樂觀版** | 不含 warmer 時間，從 DB open 量起 | warmer 已在背景 / 空檔跑完 |
| **保守版** | 含 warmer 時間（= warmer wall-clock ＋ 樂觀版）| warmer 卡在關鍵路徑 |
| **最穩：Time-to-warm** | 前 N 個 query 累計延遲 | 不受上面爭議，warmer 真正發光處 |

> 真相落在樂觀與保守之間，看部署到底有沒有空檔。**兩個都報出來才不會騙到自己**——這條直接接上 §2.2「null result / 不灌水」的誠實線。

---

## 3. 預期交付（都放在本資料夾底下）

```
prefetch_warmer/
  README.md            ← 本檔（主控執行文檔）
  PLAN.md              ← A0 產出（環境/資產盤點）
  src/                 ← page_classify.{c,h}、type_aware_vfs.{c,h}、warmer 主程式、unit test
  runs/                ← 量測腳本與結果 CSV（cold-start、precision/recall、held-out、decay 對照）
```

---

## X. 明確排除（Level 2，本子專案一律不做）

以下屬 template 的 PART B / Level 2，**本資料夾不碰**：

- FEMU emulator、裸裝置 / 無檔案系統操作。
- NVMe passthrough（`nvme_passthru_cmd`、`ioctl(NVME_IOCTL_IO_CMD)`、cdw13 directives）。
- namespace = 一 DB、LBA identity mapping、physical segregation。
- temperature-aware 多 stream（stream 0/1/2）、fast tier、two-pass build。

> 若之後要做 Level 2，另開資料夾或回到 [type_aware_physical_segregation](../type_aware_physical_segregation/)，不在此混入。
