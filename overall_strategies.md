# Overall Strategies — 現有策略總覽

> **測試流程詳解**：本檔講「每個策略是什麼」。想知道「**每個策略到底是怎麼
> 測出來的**」（共用的 benchmark_harness 引擎、cold-start 機制、結構派 vs
> 歷史派的前置、每個策略的確切 post-cold-script 指令），請看
> [strategies_explained.md](strategies_explained.md)。

> 結果數字均為 **統一 pipeline**（harness MADV chain + `/usr/local/sbin/drop-caches` 全機 drop
> + harness 內建 `--verify-hotset` 量 `cold_pct`/`delivery_pct`,全 cell `cold_pct`=0）;
> 權威全表見 [overall_results.md](overall_results.md)。

這個 repo 嘗試了三類正交的策略，每類處理不同的層級：

1. **Layout 策略**（build-time，一次性，影響整個 file 的物理排列）
2. **Prefetch 策略**（runtime，每次 cold start 跑一次）
3. **Memory-sharing 策略**（architectural，影響多 process 的 RAM 用量）

三類可以**自由組合** — 例如「type-aware layout + layers_5 prefetch + MAP_SHARED」
是目前測過的全局最佳組合。

> **編號規約：**
> - **1a/1b/1c** = Layout（orig / VACUUM / type-aware）
> - **2a–2f** = Prefetch 策略（range / perpage / layers_N / 2d / 2e_K* / 2f SLRU）
> - **3a / 3b** = Access-pattern **ratio variants**：interior:leaf = 7:3 / 5:5（由 2e_K40 / 2e_K92 實現）
> - **4a / 4b** = Memory-sharing（MAP_SHARED / Private buffer pool）

---

## 一、Layout 策略

決定 interior pages 在 file 裡的物理位置。一次性決策，做完之後所有 cold start
都受影響。

### 策略 1a — 原始 layout（do nothing）

不做任何事，SQLite 怎麼分配就怎麼放。Interior pages 散佈於整個 file（**scatter
score ≈ 0.96**，92 個 interior 散在 page 2..26,007 之間）。是所有實驗的基準線。

**狀態：** 永遠存在。
**結論：** 沒有任何 prefetch 也能拿 baseline；`layers_5` 不需要做 layout 改動。統一 pipeline 下 layers_5 first-query 改善:A/orig **−22%**、B/orig **−43%**、C/orig 僅 −3%(C 要 N=92 才 −37%)。

### 策略 1b — SQLite 內建 VACUUM（已驗證，效果 workload-dependent）

呼叫 `VACUUM;`。理論上應該把 file 緊湊化，實際上 [src/vacuum.c](https://sqlite.org/src/file?name=src/vacuum.c)
的 `sqlite3RunVacuum()` 按照 insertion order 重排，**不看 page type**。

**狀態：** 已驗證（[prefetch_vacuum/](prefetch_vacuum/) Week 11、[pipeline/preparation/layout_rewriter/runs/](pipeline/preparation/layout_rewriter/runs/) 補測 A、[pipeline/preparation/layout_rewriter/runs/matrix_1b_bc_results.csv](pipeline/preparation/layout_rewriter/runs/matrix_1b_bc_results.csv) 補測 B、C）。
**Layout 結果：**
- scatter score 從 **0.96 → 1.13**（變得**更**散）
- 檔案從 107.8 MB 縮到 104.9 MB（reclaim ~3%）

**Latency 結果（async first-query;權威表見 [overall_results.md](overall_results.md)）：**

| Workload | baseline（orig→vacuum）| layers_5 改善（orig → vacuum）|
|---|---|---|
| A (Zipfian) | 529→716 µs（VACUUM **+35% 更慢**）| -22% → -20% |
| B (Uniform) | 760→1046 µs（VACUUM **+38% 更慢**）| -43% → -49% |
| C (high-key) | 1096→993 µs（-9% 略快）| -3% → -10% |

> VACUUM 在 A/B 上把 baseline first-query **變慢**(orig→vacuum +35/38%);layers_5 的相對
> 改善 orig vs vacuum 大致持平。**單獨 VACUUM 不利 cold-start**。baseline:A/orig 529、
> B/orig 760、C/orig 1096 µs(權威全表見 [overall_results.md](overall_results.md))。

**結論：**
- **不要為了 cold-start 性能 VACUUM**：A、B 上會讓 baseline 變慢 5-8%。
- **特例：高 id 區段查詢（C）反而會變快 6%**，因 VACUUM 把整檔壓緊，
  high-key region 的 seek 距離縮短。
- VACUUM 對 reclaim disk space 仍然有用，且不會破壞 layers_5 在 B 上的
  prefetch 效益。

### 策略 1c — Type-aware layout（layout_rewriter，已完成，效果 workload-dependent）

[pipeline/preparation/layout_rewriter/layout_rewriter.c](pipeline/preparation/layout_rewriter/layout_rewriter.c) — 在
binary 層級重排 file：page 1 留原位，**interior pages 全部搬到 slots 2..93
（連續）**，leaf 接著，overflow/freelist 在最後。同時 patch 所有跨頁指標：
interior 的 child pointer、overflow 的 next-page、freelist 的 next-trunk、page 1
header 的 freelist pointer，以及產 SQL 修正 `sqlite_master.rootpage`。

**狀態：** 已完成 + 端到端驗證（A 在 [pipeline/preparation/layout_rewriter/results/](pipeline/preparation/layout_rewriter/results/)；B、C 在 [pipeline/preparation/layout_rewriter/runs/matrix_1c_bc_results.csv](pipeline/preparation/layout_rewriter/runs/matrix_1c_bc_results.csv)）。
**Layout 結果：**
- scatter score 從 **0.96 → 0.0001**（幾乎完美 clustering）
- `PRAGMA integrity_check;` 通過

**Latency 結果（async first-query vs 同 DB baseline;權威表見 [overall_results.md](overall_results.md)）：**

| Workload | ta baseline（vs orig）| 最佳結構/access on ta | first-q 最低 on ta |
|---|---|---|---|
| A (Zipfian) | 695 µs（vs orig 529,**+31%**）| 2e_K10 -42%、layers_92 -34% | 2f_slru -82%（128 µs）|
| B (Uniform) | 788 µs（vs orig 760,+4%）| layers_92 -24%、2d -22% | 2f_slru -84%（127 µs）|
| C (high-key) | 871 µs（vs orig 1096,**-21% 較快**）| 2e_K10 -76%、layers_92 -43% | 2f_slru -86%（122 µs）|

**結論：**
- **type-aware 把 baseline 推高 on A/B**（A +31%、B +4%）、在 C 反而較快(-21%);
  first-query 最低一律是 2f_slru(載整個 working set)但其 e2e 多半不具優勢(見 overall_results)。
  A/ta layers_5 first-q −25%。
- **配方依 workload 而定**：Zipfian 點讀 → ta + layers_5；File-tail 讀
  → ta + perpage；Uniform 全段讀 → 不要 ta。
- `range` 在任何 layout 都不該選 —— `MADV_WILLNEED` 對單一大 range 的
  readahead 是 bounded（~32/92 pages）。

---

## 二、Prefetch 策略

> 權威全表(含 N/K-sweep、RAM、churn、cadence、Z)見 [overall_results.md](overall_results.md)。

決定 cold start 後、第一筆 query 跑之前，要主動把哪些 page 載進 OS page cache。

### Structure-based（不看存取歷史，純粹看 page 結構）

#### 策略 2a — Range（structure-based，已完成）

把連續的 interior pages 合併成 range，每個 range 呼叫一次 `madvise(MADV_WILLNEED)`。
[prefetch_vacuum/src/prefetch.c](prefetch_vacuum/src/prefetch.c) 的 `range` mode。

**狀態：** 結構式逐頁 prefetch,已被 layers_N 取代。
**結果：**
- 原始 layout：92 個 interior → 87 syscalls，改善 **-27%**
- type-aware layout：92 個 interior → **1 syscall**（連續），但 kernel
  readahead 是 bounded，1 個 `MADV_WILLNEED` 只實際載入 32/92 pages → 改善僅 **-4%**

**結論：** 即使 layout 完美，`MADV_WILLNEED` 是 advisory，**不保證載入量**。
range 在任何 layout 下都不是好選擇。

#### 策略 2b — Perpage（structure-based，已完成）

對每個 interior page 個別呼叫一次 `madvise(MADV_WILLNEED)`。
[prefetch_vacuum/src/prefetch.c](prefetch_vacuum/src/prefetch.c) 的 `perpage` mode。

**狀態：** 結構式逐頁 prefetch,已被 layers_N 取代。
**結果：**
- 原始 layout：92 syscalls，改善 **-34%**
- type-aware layout：92 syscalls，改善 **-33%**

**結論：** 比 range 載入更多 page。`MADV_WILLNEED` 仍是 async hint
（**不阻塞、不保證**在下次存取前完成載入），但每個 page 一個 hint 比 range
模式單一大 hint 能讓 kernel readahead 更精準排程。實測 92 個 hint 全發後，
first-q 之前實際 cache 命中數遠高於 range 模式的 32/92——這是「**更多細粒度
hint = kernel 有更多機會在 first-q 之前 finish I/O**」的證據，**不是**「kernel
保證 load」。Syscall overhead 本身 ≈ 14 µs（calibration 量過），可忽略。

#### 策略 2c — Layers N（structure-based，已完成 + 找到甜蜜點）

只 prefetch **按 file offset 升序排前 N 個 interior page**（skip leaves）。
[prefetch_vacuum/src/prefetch_layers.c](prefetch_vacuum/src/prefetch_layers.c)
的實作就是 `qsort + take first N interior`。

> **語意警告**：「≈ B+tree 上 N 層」**只在 1c (type-aware) layout 成立**
> ——因為 1c 把所有 interior collocated 到 file 頭 (page 2..93)，所以
> 按 offset 排前 N 就是 B+tree 上 N 層。**在 1a / 1b 不成立**——interior
> 散佈於整個 file，「按 file offset 排前 N」只是「在檔案中最早出現的 N 個
> interior pages」。`page 1` 是 SQLite DB header + `sqlite_master`（schema）
> b-tree 的 root，**不是** `items` 表的 root；使用者表的 root 落在低頁號
> 但**不必為 1**（實測 1a 的前幾個 interior 是 page 2/3/4，但這跟 B+tree
> 樹深無 1-to-1 對應）。這也是為什麼 1a/1b 上 layers_N 效果跟 1c 不同——
> 同一個 binary 同一個算法、效果差異純粹來自 layout 賦予的物理排列。

**狀態：** A/B/C/Z × 3 layout 的 dense N-sweep。多數 cell 是 plateau,形狀依
workload/layout 而定(見下)。

**N-sweep（async first-query;權威全表見 [overall_results.md「layers_N sweep」](overall_results.md)）。** layers_N = 按 file offset 取前 N 個 interior page。

Workload A、layout orig（vs baseline 505 µs;[`results/nsweep_dense/`](results/nsweep_dense/summary.csv)）:

| N | 1 | 5 | 16 | 46 | 92 |
|---:|--:|--:|--:|--:|--:|
| first-q µs | 663 | 333 | 331 | 327 | 333 |
| 改善 | **+31%(更慢)** | **−34%** | −34% | −35% | −34% |

重點:
- **N=1 普遍比 baseline 慢**(A/Z orig ~+36%):只下一頁的 warmer/madvise 開銷 > coverage 受益。
- **A/Z**:N≥5 即進 plateau ~**−30%**(orig);ta 上 layers_5 −24%、layers_92 −35%。
- **B**(uniform,無自然熱葉):orig/vacuum N≥5 全 plateau **−47~49%**(leaf-fault 主導);ta 較弱 −24~27%。
- **C**(高鍵集中):orig **N≤46 幾乎沒用、N=92 才 −40%**(熱 interior 在 file 中段、按 offset 取前 N 選錯頁);ta 上 N=92 −46%。
- **churn 不改變 plateau 形狀**(見 [overall_results.md](overall_results.md) churn 區);static t=0 hotset 不衰退。

**因此 layers_N 的最佳 N 跟 layout/workload 強耦合**(A 上 N=5 夠、C 上要 N=92),不是 universal best。完整三-layout × A/B/C/Z dense N-sweep 見 [overall_results.md](overall_results.md)。

**Dense N=0..92 全 sweep（rigor 補測）**：clean + churn × A/B/C × 3 layouts × 3 reps，
共 ~5,580 額外 benchmark；證實 sparse 6-pt 在 9/12 cells 結論正確；但 **A×1b 漏
N=62 (-31%)、B×1c 漏 N=26 (-36%)、C×1b 漏 N=87 (-57%) 三個 sweet spot**。資料:
[pipeline/preparation/layout_rewriter/runs/nsweep_full/](pipeline/preparation/layout_rewriter/runs/nsweep_full/) +
[prefetch_churn/runs_nsweep_full_{a,b,c}/](prefetch_churn/)；
圖: [Figure 11](figures/out/11_nsweep_full.png) / [Figure 12](figures/out/12_nsweep_full_churn.png)。

### Access-pattern-based（看存取歷史，已完成）

#### 策略 2d — Access pattern，只 interior（已完成）

跑一次 workload 後用 `mincore()` dump residency snapshot，只 prefetch 那些
**實際被走過**的 interior page（按 file offset 排序，cap_interior=0 = 全載
resident 集合）。實作 [strategies/access/src/prefetch_access.c](strategies/access/src/prefetch_access.c)，
~110 行 C，同 mmap + madvise 機制。

> **統一 hotset**：`hotpages_*.csv` 由 `run_experiment.py --regen-hotsets`（全機 `drop-caches` warmup）重產並 checksum 凍結（`results/main/hotset_freeze.sha256`）。下表 async 模式、vs baseline、`cold_pct`=0。

**狀態：** A/B/C × orig/vacuum/ta × {baseline, 2d}。
**結果（first-q 改善 + e2e 兩模型,orig）：**

| Workload | first-q（orig/vac/ta）| e2e_std（orig）| e2e_warm（orig）|
|---|---:|---:|---:|
| A | −24% / −20% / −33% | +28%（較慢）| **−8%（改善）** |
| B | −42% / −50% / −22% | −1%（≈打平）| **−31%** |
| **C** | **−38% / −48% / −42%** | **−11%** | **−31%** |

**結論：**
- 2d 只 prefetch 走過的 interior（~4–30 syscall），deliver 可忽略（~68–110 µs）；first-q 改善與 layers_92 同級。
- **e2e_warm（warm-process,本研究主張）三個 workload 都改善**（A −8%、B −31%、C −31%）；**e2e_std（standalone,含 ~200 µs 冷 open）只有慢 workload(C) 為正**，快 A 反而 +28%。差別是那一次冷 open(db)。
- churn 下 static t=0 hotset 不 decay（見 [overall_results.md](overall_results.md) churn 段、REPORT §6.2.1）。

#### 策略 2e — Access pattern，interior + top-K leaves（已完成）

2d 集合再加 top-K hot leaf：用 `sqlite_dbpage` + varint decoder 把每個 leaf 的
first_rowid 抽出來、建立 key → leaf 對應表；對 workload 的每個 read key 算
所屬 leaf、累加查詢次數；取前 K。實作 [strategies/access/runs/gen_hotleaves.py](strategies/access/runs/gen_hotleaves.py)。

> **統一 hotset**：2e = resident interior ∪ top-K leaves（leaf 由 workload 頻率算,deterministic）；同一 `--regen-hotsets` 重產並凍結。下表 async 模式、first-q %（vs baseline）。

**狀態：** A/B/C × 3 layout × K∈{10,40,50,92,100,500}。

**結果（first-q 改善,orig layout）：**

| Workload (orig) | 2d | 2e_K10 | 2e_K500 | e2e best（warm-process）|
|---|---:|---:|---:|---|
| A | −24% | −26% | **−60%** | 2d/2e_K10 **−7~8%**（standalone 下 +28%）|
| B | −42% | −42% | −36% | layers_5/2d/2e_K10 **−29~31%** |
| **C** | −38% | **−81%** | −81% | **2e_K10：e2e_warm −73%（291 µs）/ e2e_std −53%** |

**結論：**
- **C：top-K hot leaf 解鎖 first-q −81%**，K=10 即 saturate（14–42 syscall），且 **e2e_warm −73%（291 µs）是全矩陣最佳 e2e**。
- **A：要 K=500 才 first-q −60%**，但 deliver ~0.83 ms → e2e 反而大幅變差（warm +97%）；小 K 不夠、大 K 太貴。
- **B（uniform）沒有 hot leaf**，K 無增益,卡在 interior-only 的 −42%。
- **A × ta × K=92 非單調 hump**（first-q +21%，比 K=40 −40% 還差）：ta 集中 interior 後加 92 leaf 引發 readahead pollution，K=500 才回穩（詳見 3b）。
- RAM 20M / churn 下皆穩定（見 2f RAM 段、[overall_results.md](overall_results.md)）。

### SLRU-approximated（已完成）

#### 策略 2f — SLRU prefetch（mincore-dumped resident set，已完成）

跑完一次 workload 後**不要 evict**，直接用 `mincore()` dump 當下 OS page cache
裡的所有 resident page，存成 `hotpages.csv`。下次 cold start 時對每個
`is_resident=1` 的 page 一一呼叫 `madvise(MADV_WILLNEED)`。
[strategies/slru/src/prefetch_slru.c](strategies/slru/src/prefetch_slru.c)。

> **統一 hotset**：2f = 整個 resident working set（base 殘留 `hotpages_*.csv`）；`--regen-hotsets` 重產並凍結。交付走統一 `warmer`，`preproc_us` 取 live `warmer_us`。下表 async 模式、vs baseline。

**和 2d/2e 的差別：** 2d/2e 要攔截 SQLite 的 page read 才能算 access count；
2f 只看 workload 結束後的 residency snapshot，**完全不用碰 SQLite 內部**，
但精度較低 —— 只知道一個 page **有沒有**被用過，不知道**被用幾次**。
實作成本：~70 行 C。

**狀態：** A/B/C × orig/vacuum/ta。
**結果（orig layout;deliver = 逐頁 madvise/pread）：**

| Workload | first-q | deliver | e2e_std | e2e_warm |
|---|---:|---:|---:|---:|
| A | −76%（529→127）| ~7.0 ms | +1285%（13.5×）| +1248% |
| B | −83%（760→128）| ~7.0 ms | +873%（10×）| +843% |
| C | −89%（1096→123）| ~0.76 ms | +2%（1.0×）| **−19%** |

**結論：**
- **first-q 全矩陣最低（−76~89%），且 layout-agnostic**（三 layout 差 < 6 µs）。
- 但 **deliver** 由 hot set 大小決定（A/B ~4k+ page ≈ 7 ms；C ~0.4k page ≈ 0.76 ms），**e2e 兩模型多半不具優勢**——A/B 慢一個數量級;**只有 C（deliver 小）warm-process e2e −19%** 才小贏。
- 適用「batch / avg latency」或 C 類小 working set,而非一般 cold-start critical path；對照圖 [Figure 14](figures/out/14_strategy_endtoend_stacked.png)（兩模型 stacked），純 first-q 的 [Figure 13](figures/out/13_strategy_firstq_bars.png) 會誤導。

**RAM-pressure（cgroup MemoryMax=20M;適用全策略）：** first-q 的「20M / unlimited」ratio 全部落在 **0.95–1.07**（54 cell），RAM 壓力幾乎不影響 first-q——resident working set（~17 MB）略小於 20M cap。詳見 [overall_results.md](overall_results.md) RAM 段、REPORT §6.2.2。

### Access-pattern ratio variants（3a / 3b）

3a / 3b 是 2e 的 ratio 變體：固定 **interior:leaf** 比例分別為 7:3 與 5:5，
由 `2e_K=40` / `2e_K=92` 實現。它們不是新策略，是為了驗證「ratio 是不是
first-q 的主要 axis」（結論：K 才是，ratio 只是 K 的副產品）。

#### 策略 3a — Access pattern, interior + leaf @ 7:3 ratio (= 2e_K40, 已完成)

原始 spec 把「interior 集合再加 leaf」拆成兩個 ratio：3a = 70% interior + 30%
leaf。在 92 個 interior 的 DB 上，這對應到 leaf 數 ≈ 92 × 30/70 ≈ **40**，
所以 3a 由 **2e_K=40** 實現。

**狀態：** 已完成，A/B/C × 3 layouts × 6 reps = 54 cells。
資料 [matrix_2e_ratio_results.csv](strategies/access/runs/matrix_2e_ratio_results.csv)，
視覺化 [figures/out/10_ratio_sweep.png](figures/out/10_ratio_sweep.png)。

**實作細節：** 2e 只 prefetch **resident** interior（warmup 走過的），不是全部 92 個，故實際 ratio 偏 leaf，只有 ta layout 接近 spec。

**Latency（first-q async,vs baseline）：**

| WL | orig | vacuum | ta |
|---|---:|---:|---:|
| A | −33% | −21% | −40% |
| B | −47% | −49% | −25% |
| C | **−86%** | −81% | −78% |

C 已 saturate（K≥10 即 ~−85%）；A/B 與 2d 相當（K=40 未達 K=500 的效益）。

#### 策略 3b — Access pattern, interior + leaf @ 5:5 ratio (= 2e_K92, 已完成)

3b = 50% interior + 50% leaf，由 **2e_K=92** 實現。

**Latency（first-q async,vs baseline）：**

| WL | orig | vacuum | ta |
|---|---:|---:|---:|
| A | −51% | −50% | **+21%** |
| B | −47% | −48% | −25% |
| C | −85% | −81% | −78% |

**A × ta × K=92 = +21%（786 µs，比 K=40 −40%、K=500 −69% 都差）**：ta 集中 interior 後加 92 leaf 引發 readahead pollution，K=500 才回穩。此非單調 hump 為 ta 特有，orig/vacuum 無。

**結論（3a vs 3b）：**
- **C**：任一 ratio 都 saturate，2e_K10 已夠（−85%）。
- **A**：K=40 穩定；K=92 在 ta 上退化（hump）。
- **B（uniform）**：沒有 hot leaf，ratio 怎麼分都 ~−47%。
- 總結：**K（leaf 數）才是主要 axis，ratio 只是 K 的副產品**（見 [Figure 10](figures/out/10_ratio_sweep.png)）。

---

## 三、Memory-sharing 策略（4a / 4b）

決定多 process 場景下 page cache 的共享方式。在手機（背景 service + 主 App）
或 server（worker process pool）這類部署最關鍵。

### 策略 4a — MAP_SHARED mmap（已驗證）

所有 process 用 `mmap(MAP_SHARED)` 開同一個 DB file。整個 fleet 共享 OS page
cache 的同一份 physical copy。**SQLite 開啟 `PRAGMA mmap_size = <size>` 就走
這條路徑**。
[multiprocess/src/multiprocess_residency.c](multiprocess/src/multiprocess_residency.c)。

**狀態：** 已驗證（[multiprocess/](multiprocess/)）。
**結果：**
- 3 個 child process 各讀 1/3 的 DB，parent 完全沒讀任何東西
- 最後 `mincore()` 看到 **25,613 / 25,613 pages 全部 resident**，跨 process 共享確實成立
- 任何一個 process 呼叫 `madvise(MADV_WILLNEED)` prefetch，其他 process 立即受惠

**結論：** **prefetch 的成本固定 O(1)，效益隨 process 數量 O(N) 放大**。是
mobile / embedded 場景下 prefetch 設計的天然 multiplier。

### 策略 4b — Private buffer pool per process（已驗證對照）

`PRAGMA mmap_size=0` + `PRAGMA cache_size=N`，每個 process 持有獨立 buffer pool。
[multiprocess/src/multiprocess_buffer_pool.c](multiprocess/src/multiprocess_buffer_pool.c)。

**狀態：** 已驗證對照組。
**結果：**

| Process 數量 | MAP_SHARED 總 RAM | Private buffer pool 總 RAM |
|---:|---:|---:|
| 3 | ~100 MB | ~30 MB |
| 10 | ~100 MB | ~100 MB |
| 100 | ~100 MB | **~1 GB** |

**結論：** Process 數量少時 private buffer pool 反而省 RAM（因為只 cache 用到
的 working set）；但 process 數量 → ∞ 時 MAP_SHARED 是唯一可行解。**這也是
為什麼 Android / mobile 場景一定要走 mmap 路徑**。

---

## 組合策略 — 目前測過的最佳堆疊

```
Layout:           type-aware (layout_rewriter)    ← scatter 0.00     [1c]
Prefetch:         layers_5                         ← 5 syscalls, 94 µs [2c]
Memory sharing:   MAP_SHARED                       ← 多 process 自動受惠 [4a]
```

統一 pipeline 下:在慢 workload C 上 2e_K10 把 first query 從 baseline 1096 → 211 µs(**−81%**)、warm-process e2e 291 µs(**−73%**),
且 prefetch 的少數 syscall 可由任一 process 出資、整個 fleet 共享成果(cadence 重暖,見 [overall_results.md](overall_results.md))。

---

## 策略狀態總覽

| 類別 | 策略 | 狀態（first-q,orig layout）|
|---|---|---|
| Layout | 1a 原始 | baseline |
| Layout | 1b VACUUM | A/B baseline 變慢（+40/+38%）、C 略快（−6%）|
| Layout | 1c type-aware | A/B baseline 推高（+31/+10%）、C 較快（−18%）|
| Prefetch | 2a Range | 不選——`MADV_WILLNEED` 對單一大 range 的 readahead bounded |
| Prefetch | 2b Perpage | 結構式逐頁,已被 layers_N 取代 |
| Prefetch | 2c Layers N | first-q A −22% / B −43% / C −37%（需 N=92）；最佳 N 與 layout 耦合 |
| Prefetch | 2d interior-only | first-q A −24% / B −42% / C −38%；**warm-process e2e 三 workload 皆改善(−8~31%)** |
| Prefetch | 2e interior+top-K | **C：K=10 first-q −81%（warm e2e −73% / 291µs）**；A 需 K=500 −60% |
| Prefetch | 2f SLRU | first-q −76~89%（全矩陣最低），但 deliver 太重→e2e 多半不具優勢（C 例外 warm −19%）|
| Prefetch | 3a/3b ratio（K40/K92）| K（leaf 數）才是主軸,ratio 非主因 |
| Memory | 4a MAP_SHARED | 成本 O(1)、效益隨 process 數放大 |
| Memory | 4b Private buffer pool | 對照組（process 多時 RAM 爆量）|

> **狀態說明**：上表結果均為 統一 pipeline（`cold_pct`=0），權威全表見 [overall_results.md](overall_results.md)。2a/2b 為早期結構式 prefetch，未納入 batch（已被 layers_N / access-pattern 取代）。pread（oracle 上限）與 async（madvise 實際交付）為兩個獨立比較組，定義見 REPORT §3。
