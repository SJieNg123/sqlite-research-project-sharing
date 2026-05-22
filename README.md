# SQLite Research Project

研究 SQLite cold-start 行為、page residency、prefetch 與 page layout 的工具與實驗集合。

---

## 📖 這個專案在做什麼 — 故事版

### 第 0 章：起點 — 一個被忽略的 0.35%

SQLite 是世界上部署量最多的 DBMS（地球上每支手機裡都有好幾個）。它用 **B+tree** 存資料，整個 DB 是一個 flat 的 4 KB page 陣列。每筆 query 都得從 root 走到 leaf，**沿路經過的 interior page 全部都要在記憶體裡**。

但 interior page 通常只佔整個 DB 的 **0.35%**（92 個 / 26,331 個）。聽起來微不足道，直到你考慮**冷啟動**：

> App 剛開機、SQLite 程式剛啟動、或久未使用 → OS page cache 是空的 → 第一筆 query 要把那 ~4 個 interior page 從 disk 拉進來 → **first query 比後續慢 10–100 倍**。

問題清楚了：**能不能在第一筆 query 之前，先把那 92 個關鍵的 interior page 預載入 cache？**

這就是整個 repo 的研究主題。

### 第 1 章：先看清楚地形 — `classify_pages/`

要 prefetch interior page，首先得**知道哪些 page 是 interior**。SQLite 自己不會告訴你 — 它只給你 SELECT。

所以第一步是寫一個**不依賴 libsqlite** 的 page-type 分類器，直接讀 SQLite 的 file format spec、解析每個 page 的 b-tree flag byte：

```
0x02 → interior_index    0x0A → leaf_index
0x05 → interior_table    0x0D → leaf_table
```

跑完 `classify_pages test.db`，得到一份 CSV：每個 page 編號 + 它的型別 + 它在檔案裡的 offset。配上 `plot_pages.py` 可以畫出 page layout 圖，肉眼看到 interior 散得多開。

**這個工具還順手算了一個叫 scatter score 的數字** — 0 代表 interior 全擠在檔頭、1 代表均勻分布。**真實 DB 的 scatter ≈ 0.96**。Interior pages 不只少，還散得到處都是。這意味著 OS sequential readahead 救不了我們，**必須顯式 prefetch**。

### 第 2 章：建一台儀器 — `benchmark_harness/`

要證明 prefetch 有沒有用，需要可重現的測量。`benchmark_harness` 就是這個專案的測量儀器：

1. mmap 整個 DB
2. 跑 `madvise(MADV_DONTNEED)` 或 `drop_caches` 假裝冷啟動
3. 用 `mincore()` 記錄哪些 page 還在 RAM（cold snapshot）
4. （如果要測 prefetch）執行 prefetch script，再 mincore 一次（after-prefetch snapshot）
5. 逐筆跑 workload，用 `clock_gettime()` + `getrusage()` 記 latency + page fault delta
6. 跑完再 mincore 一次（after-run snapshot）

產出兩種 artifact：**per-operation CSV**（每筆 query 一列）+ **run record log**（整次的 metadata 與 residency 分布）。

> **🔧 最近一次更新**：原本 benchmark_harness 沒有把「協助測量 prefetch」當主任務寫進去；後來加了 `--post-cold-script` 讓 prefetch + residency snapshot 進入 cold boundary 之內，現在量到的 `first_query_latency_us` 才能真正反映「prefetch 之後、第一筆 query 的延遲」。

### 第 3 章：第一次嘗試 — Range vs Perpage（Week 9）

有了測量工具，先試最直覺的兩種 prefetch 策略：

| 策略 | 做法 |
|------|------|
| `range` | 把相鄰的 interior page 合成 range，每個 range 一次 `madvise(MADV_WILLNEED)` |
| `perpage` | 每個 interior page 都單獨一次 madvise |

**結果讓人意外：**

| 策略 | syscall | first query | 改善 |
|------|---------|-------------|------|
| baseline | 0 | 73 µs | — |
| `range` | 87 | 53.6 µs | -27% |
| `perpage` | 92 | 48.0 µs | -34% |

`range` **只省了 5 次 syscall**（92→87），而且**反而比 perpage 慢**。為什麼？因為 interior pages scatter 太嚴重，相鄰的根本沒幾個；而 `range` 涵蓋的大區間裡夾雜了一堆 leaf pages 也被一起載進來，浪費 I/O。

**第一個學到的教訓**：當 page 已經散開時，「批次合併」這種傳統 I/O 最佳化技巧無效。

### 第 4 章：找到甜蜜點（Week 10）

如果不該載**所有**的 92 個 interior page，那載多少才剛好？掃 N = 1, 5, 10, 20, 46, 92：

```
N=1    →  38 µs  (-48%)
N=5    →  33 µs  (-54%) ← 甜蜜點
N=10   →  44 µs  (-39%)
N=20   →  35 µs  (-53%)
N=46   →  41 µs  (-45%)
N=92   →  50 µs  (-31%) ← 越多越糟
```

呈現一個 **U 型曲線**。為什麼？

`madvise(MADV_WILLNEED)` 是**非同步**的 — 它叫 OS 排程 I/O 就馬上回傳，**不等載完**。

- N 太少（1 個）：上層 interior 載到了，中層還沒，第一筆 query 還是會 fault
- **N=5 剛好**：5 個 page 只花 94 µs 就 prefetch 完，OS 在第一筆 query 跑到前剛好載完
- N 太多（92 個）：prefetch syscall 本身花了 2,229 µs，benchmark 開始時 OS 還沒載完，後面 query 還是要 fault；而且 prefetch 本身已經吃掉時間

**第二個學到的教訓**：**load 5 個 page（佔整個 DB 的 0.02%）就能砍掉一半以上的 cold-start latency**。Prefetch 不是越多越好，要剛好讓 OS 來得及做完。

### 第 5 章：VACUUM 的背叛（Week 11）

直覺：SQLite 內建的 `VACUUM` 命令會把 DB 整理得更緊湊，layout 應該變整齊，prefetch 應該更有效。

**實際跑出來完全相反：**

| 條件 | scatter | first query | 改善 |
|------|---------|-------------|------|
| Before VACUUM + prefetch 5 | 0.96 | 33.4 µs | -54% |
| After VACUUM + prefetch 5 | **1.13** | **66.2 µs** | **-9%** |

scatter 從 0.96 變 1.13（**更散**），prefetch 效益從 -54% 退化到 -9%。

翻 SQLite source code（`src/vacuum.c` 的 `sqlite3RunVacuum()`）發現原因：**它按 row 的插入順序重排 page，完全沒考慮 page type**。新的 interior page 全部被推到一大堆 leaf page 之後，變得**更**分散。

**第三個學到的教訓**：SQLite 內建的 VACUUM 是 type-unaware 的，反而破壞 cold-start 性能。**這是一個改進 SQLite 本身的具體切入點：實作 type-aware VACUUM，把 interior 集中到檔頭**。

### 第 6 章：免費的乘數效應 — `multiprocess/`（Week 12）

到目前為止，所有實驗都假設只有一個 process。但實際應用（手機、伺服器）常常有**很多 process 共用同一個 DB**。

問題：如果一個 process 做 prefetch，其他 process 拿不拿得到好處？

關鍵在 SQLite 的 `PRAGMA mmap_size`：開啟它之後 SQLite 用 `mmap(MAP_SHARED)` 開檔，理論上**所有 process 共享同一份 OS page cache**。

實驗驗證：fork 3 個 child 各讀 1/3 的 DB，parent 自己沒讀任何東西，最後 mincore 看到 **25,613 / 25,613 全 resident**。

對照組（每個 process 用 private buffer pool）：3 個 process 各自佔 10 MB RAM，**完全不共享**。

| 模式 | 3 process | 10 process | 100 process |
|------|-----------|------------|-------------|
| MAP_SHARED mmap | ~100 MB | **~100 MB** | **~100 MB** |
| Private buffer pool | ~30 MB | ~100 MB | ~1 GB |

**第四個學到的教訓**：**一個 process 呼叫一次 `madvise(MADV_WILLNEED)`，所有 mmap 同一個 DB 的兄弟 process 都立刻拿到加速**。在多 process 部署下，prefetch 的成本被攤平，效益被放大。

### 第 7 章：層次三 — 動態世界的測試 `prefetch_churn/`

到這裡為止的實驗都用**靜態**的乾淨 DB。但真實 app 不停在寫入、刪除、更新 — page layout 會隨時間漂移。所以最新一輪實驗（「層次三」）測：**隨著 DB 被 churn，prefetch 的效益會怎麼變化？**

設計：同一個 DB，跑 10 個 checkpoint，每個 checkpoint 之間執行 5,000 筆 mixed workload（含 1,000 insert + 1,000 delete）製造 churn。每個 checkpoint 做兩件事：
1. 跑 `classify_pages` 看當下 layout
2. drop cache → 跑 cold-start query → 量 latency

兩組對照：**有 prefetch** vs **無 prefetch**。

結果：

| | baseline | ck001 | ck005 | ck010 |
|---|---|---|---|---|
| no_prefetch first_query | 4,918 µs | 4,511 | 5,709 | **6,892** |
| prefetch first_query | 5,130 µs | 5,398 | 7,055 | **6,300** |

**觀察：**
- 兩組的 first_query latency 都隨 churn 累積而上升（4,918 → 6,892 µs）— 這是 scatter 增加造成的
- 新出現的 interior page 全部在檔尾（page 26,393、26,474、…、27,030）
- baseline 時 prefetch 沒效益（甚至略差），但 **churn 累積後 prefetch 開始幫忙，平均省 ~590 µs（~10%）**
- 寫入越多次，OS 的 sequential readahead 越無效，**顯式 prefetch 越不可取代**

**第五個學到的教訓**：prefetch 在真實的、被使用過一段時間的 DB 上**仍然有效**，但 baseline 也變得更慢，所以絕對省的時間（μs）比百分比更值得看。

### 第 8 章：54% 跟 10% 看起來矛盾，其實不矛盾

```
prefetch_vacuum:  73 µs   → 33 µs   省 40 µs   (-54%)  ← Zipf workload + 乾淨 DB
prefetch_churn:   6,892 µs → 6,300 µs 省 592 µs (-10%)  ← uniform workload + churned DB
```

**百分比看起來差 5 倍，絕對時間卻是 prefetch_churn 省得多 14 倍。** 為什麼？

一筆冷啟動 query 的成本拆解：

```
[Interior page faults] + [Leaf page fault] + [SQLite CPU]
       ↑                       ↑
   prefetch 能解決         prefetch 解決不了
                          （不知道 query 要哪一筆）
```

- **Zipf workload**：少數熱 key 反覆被查，leaf 自然變熱；Interior 是唯一 bottleneck → prefetch 把它解掉就大勝
- **Uniform workload**：每筆 query 都打到沒看過的 leaf → leaf fault 不可避免 → prefetch 只能解決一部分

百分比看起來低不是 prefetch 沒用，是 baseline 本來就被「leaf 一定冷」拉高了。

### 第 9 章：目前進度與下一步

#### ✅ 已完成

- **工具鏈完整**：classify_pages、benchmark_harness、residency_checker、prefetch、prefetch_layers 全部可用
- **找到 prefetch 甜蜜點**：上層 5 個 interior page = -54% cold-start（最佳情境）
- **解析了 VACUUM 為何傷害 layout**：sqlite3RunVacuum() 是 type-unaware
- **驗證了 MAP_SHARED 共享**：一個 process prefetch，所有人受惠
- **動態世界驗證**：在 churned DB 上 prefetch 仍然有 ~10% 改善
- **改造了 benchmark_harness 的 cold boundary**：現在能精確隔離 prefetch 階段
- **層次三實驗已交付**（已開 PR）

#### 🚧 進行中 / 待做

- **Workload 多樣性還不夠**：目前實驗只跑兩種 workload（Zipf 的 workloadc + 接近 uniform 的 page_churn_high）。Zipf 的「熱點落在 high key vs low key」會造成完全不同的 churn 模式 — high key hotspot ≈ append-only、low key hotspot ≈ 劇烈 churn。**這兩種變體還沒測**。
- **Type-aware VACUUM 還沒實作**：Week 11 已經指出問題，但實際改 SQLite source code 還沒做
- **單一 N 設定**：churn 實驗只測 `prefetch_layers N=5`，沒對照 N=1、10、20 在 churned DB 上的曲線

#### 🔬 待回答的研究問題

1. Type-aware VACUUM 真的能把 prefetch 效益從 -9% 救回 -54% 嗎？
2. 在「low key hotspot」的 Zipf workload 下，prefetch 效益會比 uniform 還差嗎？
3. 多 process 場景下，prefetch worker 該多久跑一次？（DB 持續被 churn 時）

---

## Repository Layout

每個實驗都是獨立的子目錄，包含自己的程式碼、文件與數據：

```
├── classify_pages/         # SQLite page-type 分類器
├── benchmark_harness/      # Cold-start workload benchmark 工具
├── residency_checker/      # Page residency 檢查工具
├── prefetch_churn/         # Prefetch + page churn 主實驗（orchestrator）
├── multiprocess/           # Multi-process mmap 實驗
├── prefetch_vacuum/        # Prefetch + VACUUM 實驗
└── frontend/               # 16-week 研究計畫 UI 元件
```

每個實驗目錄裡都同時放：
- 程式碼（C source、Python script、shell script）
- 該實驗的文件（`*.md`）
- 該實驗使用或產生的資料（`workloads/`、`results/`、`logs/` 等）

對照故事章節：

| 目錄 | 章節 | 角色 |
|------|------|------|
| `classify_pages/` | 第 1 章 | 看清 DB 內部結構的基礎工具 |
| `benchmark_harness/` | 第 2 章 | 測量儀器 |
| `residency_checker/` | 第 2 章 | 輔助 residency 量測 |
| `prefetch_vacuum/` | 第 3–5 章 | 找到甜蜜點 + 揭露 VACUUM 問題 |
| `multiprocess/` | 第 6 章 | 證明 mmap 共享，prefetch 效益乘 N |
| `prefetch_churn/` | 第 7–8 章 | 動態世界驗證 + workload 偏斜度討論 |
| `frontend/16week_plan.jsx` | — | 整個研究計畫的 UI tracker |

## 各實驗目錄

### [classify_pages/](classify_pages/) — SQLite Page Classifier

不依賴 libsqlite 的 page-type 分類器，直接照 SQLite file format 解析。

- `classify_pages.c` — C 分類器，輸出 CSV
- `plot_pages.py` — matplotlib 視覺化 + scatter-score 診斷
- `build_testdb.py` — 建立符合研究 schema 的 test DB

```bash
gcc -O2 -Wall -o classify_pages classify_pages/classify_pages.c
python3 classify_pages/build_testdb.py
./classify_pages test.db > pages.csv 2> stats.txt
python3 classify_pages/plot_pages.py pages.csv page_layout.png
```

### [benchmark_harness/](benchmark_harness/) — Cold-start Benchmark Harness

觀察 SQLite workload 在 cold-start 情境下的 latency / page fault / residency。詳見 [benchmark_harness/BENCHMARK_HARNESS.md](benchmark_harness/BENCHMARK_HARNESS.md)。

- `benchmark_harness.c` — 主程式
- `benchmark_harness_analyze_residency_by_page_type.py` — 配合 classify_pages 分析 residency
- `benchmark_harness_plot_latency_vs_faults.py` — latency vs faults 圖
- `benchmark_harness_plot_results.py` — 結果圖
- `benchmark_harness_residency_report.py` — residency 報告
- `workloads/workloadc.txt` — 測試用 workload

### [residency_checker/](residency_checker/) — Residency Checker

檢查 SQLite database 檔案中每個 page 是否 resident。詳見 [residency_checker/RESIDENCY_CHECKER.md](residency_checker/RESIDENCY_CHECKER.md)。

### [prefetch_churn/](prefetch_churn/) — Prefetch Churn Experiment（主實驗）

外層 orchestration script，循環執行 classify → prefetch → benchmark → 寫入造成 page churn，量測 prefetch 對 cold-start query latency 的效果如何隨 page layout churn 變化。詳見 [prefetch_churn/SQLITE_PREFETCH_CHURN_EXPERIMENT.md](prefetch_churn/SQLITE_PREFETCH_CHURN_EXPERIMENT.md)。

- `sqlite_prefetch_churn_experiment.py` — orchestration script
- `join_and_plot_pages.py` — 合併 page 與 residency 資料、繪圖
- `testdb_builder.py` — 建立 benchmark 用的大型 DB
- `drop_caches.sh` — root helper，清空 Linux page cache
- `workloads/` — page churn workload 檔案
- `results/` — 各 checkpoint 的 churn / prefetch summary CSV
- `logs/` — benchmark_harness run 紀錄

### [multiprocess/](multiprocess/) — Multi-process mmap 實驗

詳見 [multiprocess/MULTIPROCESS_MMAP.md](multiprocess/MULTIPROCESS_MMAP.md) 與 [multiprocess/MADVISE_KERNEL_NOTES.md](multiprocess/MADVISE_KERNEL_NOTES.md)。

### [prefetch_vacuum/](prefetch_vacuum/) — Prefetch + VACUUM 實驗

詳見 [prefetch_vacuum/PREFETCH_VACUUM.md](prefetch_vacuum/PREFETCH_VACUUM.md)。

### [frontend/](frontend/) — 16-week Research Plan UI

React 元件，呈現 16 週研究計畫。

## What classify_pages does

1. 讀 100-byte database header；取出 `page_size` (offset 16)、`page_count` (offset 28)、`first_freelist_trunk` (offset 32)。
2. 走 freelist trunk chain，標記所有 trunk + leaf freelist page。
3. 標記保留的 lock-byte page（若在檔案範圍內）。
4. 對其餘每個 page 讀 b-tree flag byte：
   - `0x02` → interior index
   - `0x05` → interior table
   - `0x0A` → leaf index
   - `0x0D` → leaf table
   - 其他 → overflow（b-tree cell 的內容延續）
5. 輸出 `page_number,page_type,file_offset` 每 page 一列。

Page 1 特別處理：它的 b-tree flag byte 在 file offset 100（在 100-byte db header 之後），不在 offset 0。

## Scatter score

`classify_pages/plot_pages.py` 對 interior pages 計算 scatter score：

- **0.0** = 完全集中在檔案開頭
- **1.0** = 均勻分布在整個檔案

真實世界的 database（以及 VACUUM 之後的 database）會接近 1.0 — 這正是本工具要量化的現象。type-aware layout 演算法應該能把這個數字推向 0.0。
