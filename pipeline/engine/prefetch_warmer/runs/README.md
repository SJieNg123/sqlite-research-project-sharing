# A3 — 結果：Level-1 prefetch warmer 的完整 ablation（L0–L5）

完整的 ablation ladder 數據。量測遵守 [../README.md](../README.md) §2 的嚴謹度與誠實規則：
**每臂 30 reps、報 median/p95/p99/min/stdev、cold start 看尾端、TTFQ 報樂觀＋保守兩版、null/負結果照實寫。**

> **編號說明（重要）**：L 編號是照[完整規劃的 6 層 ladder](../README.md#1-phase-規劃) 排的（L0 baseline、L1 warmer、
> L2 tree-top、L3 pointer-ahead、L4 fan-out、L5 hot-leaf），**不是照「實際疊了幾層」**。其中 **L0/L1/L2/L5 是
> 「開檔前 batch warmer」家族**（用 `benchmark_harness` 量），**L3/L4 是「查詢中線上預取」家族**（用獨立的
> `trav_bench` 量、有自己的 baseline）。兩家用不同 harness，**只能各自跟自家 baseline 比，不能跨家比絕對值**。

---

## Part A — Batch warmer 家族（L0 / L1 / L2 / L5），`benchmark_harness`，baseline 510 µs

設定：DB `prefetch_access/runs/test.db`（60 萬列、103 MiB、4 KiB 頁）；workload `workload_a_zipfian.txt`（Zipfian 點查）；
每 rep `evict`（fadvise DONTNEED）→ warmer（post-cold-script）→ harness 開 SQLite 量 first-query。真冷啟動（majflt≈180）。

| 臂 | 暖什麼（頁數）/ 暖法 | median µs | p95 | p99 | stdev | warm 成本 µs | **TTFQ 樂觀** | **TTFQ 保守** |
|---|---|--:|--:|--:|--:|--:|--:|--:|
| **L0** | baseline，不暖 | 510 | 520 | 532 | 27 | 0 | 510 | 510 |
| **L1** | 92 interior（全），**pread** | **113** | 122 | 129 | 5 | 8006 | **113（−78%）** | 8120 |
| **L1** | 92 interior（全），**fadvise** | 335 | 354 | 357 | 27 | 162 | 335（−34%） | 497 |
| **L2** | 3 roots only，pread | 413 | 432 | 435 | 35 | 213 | 413（−19%） | 626 |
| **L2** | 51 items-tree interior，pread | 334 | 356 | 370 | 27 | 4390 | 334（−35%） | 4723 |
| **L2** | 51 items-tree interior，**fadvise** | 334 | 350 | 351 | 24 | **92** | 334（−35%） | **425（最低保守）** |
| **L5** | 92 interior ＋ 10 hot leaf，pread | 114 | 131 | 137 | 7 | 8763 | 114（−78%） | 8877 |
| **L5** | 92 interior ＋ 10 hot leaf，fadvise | 337 | 350 | 380 | 26 | 175 | 337（−34%） | 512 |

> **L5 ＝ L1 ＋ 10 hot leaf（巢狀疊加，102 頁）。** 但因 L2/L3/L4 是「不同暖法/不同家族」、不是「再往上疊一層」，
> 所以 L5 在數據裡實際是「**L1 再加熱葉**」，不是「L4 之上加熱葉」。L5 這個編號是對齊[規劃 ladder](../README.md#1-phase-規劃) 的
> 位置（hot-leaf 排最頂），不代表中間 L2–L4 都疊上去了。

### Part A 的發現

1. **暖 interior 大砍 TTFQ**：L1 pread 510→113 µs（**−78%**），穩（stdev 5、p99 129）。
2. **pread vs fadvise 是核心取捨**：pread 砍最多但暖 92 個冷頁要 8 ms，保守版淨虧；fadvise 暖幾乎免費（162 µs）但只
   −34%（非同步 readahead 第一筆前沒讀完）。
3. **L2 tree-top ＝ 成本/效益的調節旋鈕，但沒有免費的 −78%**：
   - **3 roots（near-free，warm 213µs）只買到 −19%**——root 在每筆路徑上，暖它省一個 fault，但下面的 interior 仍 fault。
   - **51 items-interior（fadvise，warm 只 92µs）買到 −35%，保守 TTFQ 425 是全表最低**——「只暖查詢真的會走的那棵樹」
     在 fadvise 下最划算。
   - ⚠️ **但「精準只暖 items 子樹」沒有打贏「全暖 92」**：L2_items_pread（51 頁）first-query 334 µs，比 L1_pread（92 頁）
     的 113 µs **還差**。推測是 **readahead 副作用**——pread 全部 92 個散在檔案裡的 interior 時，kernel readahead 順手把
     查詢要的那個 leaf 也帶進來了；只暖 51 頁就少了這個意外紅利。**這是個誠實的反直覺點：targeted 不一定贏，因為
     pread 的「附帶 readahead」也在出力。**
4. **L5 hot-leaf 對第一筆是 null result**：L5 比 L1 只差 1 µs。單點查詢只碰一個 leaf，多暖 10 個熱葉幫不到「第一筆」。

---

## Part B — 線上預取家族（L3 / L4），`trav_bench`，**自己的 baseline 186 µs**

自寫的 SQLite VFS shim（[../src/trav_bench.c](../src/trav_bench.c)）：`xRead` 讀到 interior 頁時，parse 它的 child 頁號、
**邊走訪邊預取下一層**。單一點查詢（key 155）、30 reps、每 rep 先 fadvise(DONTNEED) 冷快取。

| 臂 | 線上預取法 | median µs | p95 | p99 | stdev | vs 自家 baseline |
|---|---|--:|--:|--:|--:|--:|
| **L0′** | baseline（不預取）| 186 | 198 | 205 | 5 | +0% |
| **L3** | pointer-ahead（fadvise child）| 402 | 610 | 666 | 112 | **＋116%** |
| **L4** | fan-out（pread child）| 7594 | 7720 | 9235 | 431 | **＋3982%** |

### Part B 的發現 —— 這是個乾淨的「負結果」

**對點查詢，線上預取會傷效能，不是幫忙。** 原因量得很清楚：讀一個 interior 頁時，它有 **499 個 child**，但點查詢
只會往下走 **1 個**。VFS 不知道查詢的 key，只能把 **499 個全預取**：

- **L4 fan-out（pread 全部 499）**：同步多讀 499 個沒用的 leaf → **7594 µs（慢 40 倍）**。災難級過度預取。
- **L3 pointer-ahead（fadvise 499）**：背景 readahead 那 499 個沒用的 leaf 偷走 I/O 頻寬 → **402 µs（慢 1 倍）**。

→ 這正是投影片警告的「**一次 point lookup 卻暖了全部 → 過度預取**」，現在量出來了。**線上 pointer-ahead 要有用，必須
是「語意感知」的（知道 key、只預取要 descend 的那一個 child）**——但純 VFS 看不到 key，只能 fan-out 全部。或者它只在
**range scan**（真的會走訪很多 leaf）才划算；本 workload 是點查詢，所以是負結果。**照實記錄（紅線 F10）。**

---

## 全 ladder 一句話總結

- **想砍冷啟動第一筆**：暖 interior 有效（−34~78%），但**沒有免費的 −78%**——要嘛付 8 ms pread（保守版淨虧），要嘛
  用 fadvise 拿 −34%（近乎免費）。最划算的折衷是 **L2 只暖查詢那棵樹 + fadvise（−35%、保守 425）**。
- **hot-leaf（L5）** 對單點第一筆 = null。
- **線上 pointer-ahead / fan-out（L3/L4）** 對點查詢 = **負結果（過度預取）**，除非做成語意感知或用於 range scan。
- **誠實**：avg 穩態五臂都 2.04 µs → batch warmer 好處 100% 在 TTFQ；兩家 baseline 不同不可跨比；負結果照報。

## 重現

```sh
cd prefetch_warmer
# batch warmer 家族 (Part A)
( cd src && gcc -O2 warmer.c -o warmer )
( cd runs && bash run_ablation.sh && python3 aggregate.py ablation_raw.csv )
# 線上預取家族 (Part B)
( cd src && gcc -O2 trav_bench.c ../../benchmark_harness/sqlite3.c -I../../benchmark_harness -o trav_bench -lpthread -ldl -lm )
( cd src && for m in off ahead fanout; do WARM_MODE=$m ./trav_bench ../../prefetch_access/runs/test.db 155 30; done )
```
