# Prefetch-time calibration

每個 prefetch tool（`prefetch_layers` / `prefetch_access` / `prefetch_slru`）
跑完之後會印 `time_us=X.XX` 到 stderr。但 `benchmark_harness` 跑 prefetch
的時候**沒抓**這個值——所有 dimension 的 result CSV 都只記 `first_query_us`、
不記 prefetch tool 自己花的時間。

這個資料夾就是補這個缺口。獨立跑每個 (tool, layout, workload, strategy)
組合 3 次、解析 stderr 把 time_us 撈出來、聚合成 CSV。

> **為什麼可以離線跑**：`madvise(MADV_WILLNEED)` 是 OS hint、不等 I/O，所以
> prefetch tool 自己的 wallclock 跟 DB 是 cold 還是 warm 沒太大關係，主要由
> **syscall 數量** + **binary 邏輯**決定。離線量到的 time ≈ 線上跑時的 time。

## 檔案

| 檔案 | 內容 |
|---|---|
| `prefetch_time_calibration.csv` | **每 rep 原始紀錄**（1,053 rows = 3 tools × 351 cells × 3 reps）|
| `prefetch_time_summary.csv` | **每 cell 1 row**（median over 3 reps，351 rows）|
| `calibrate_prefetch_time.py` | 跑 calibration 的 driver（位於 repo 根目錄）|
| `aggregate.py` | 從 raw → summary 的腳本 |

## Schema

```
tool                : prefetch_layers / prefetch_access / prefetch_slru
db_layout           : orig / vacuum / ta
workload            : A / B / C   (prefetch_layers 用 "ALL" — 不依 workload)
strategy            : layers_N / 2d / 2e_K{10,40,50,92,100,500} / 2f_SLRU
N_or_K              : layers 的 N 或 access 的 K（其他空白）
prefetch_time_us_med: 3 reps 取 median（µs）
n_prefetch          : 實際 prefetch 了幾個 page
n_syscalls          : 發了幾個 madvise syscall
```

## 涵蓋

| Tool | 組合 | Cells |
|---|---|---:|
| `prefetch_layers` (2c) | 3 layout × N=0..92 × 3 reps | 279 |
| `prefetch_access` (2d/2e) | 3 layout × 3 workload × {2d, 2e_K10/40/50/92/100/500} = 9 × 7 | 63 |
| `prefetch_slru` (2f) | 3 layout × 3 workload | 9 |
| **總計** | | **351** |

（prefetch_layers 不分 workload —— 同個 layout 下、給定 N 個 madvise，跟讀的
順序無關；只 sweep N。但每個 layout 的 classify CSV 不同，所以 layout 分開記。）

## 主要發現（給 dimension 表加上 prefetch overhead 後）

| 策略 | prefetch_time | first-q 改善 | 真實「端到端 cold start」效應 |
|---|---:|---:|---|
| **2c layers_5** | 1-2 µs | -40~50% | 幾乎沒成本，**淨贏** |
| **2c layers_92** | 13-15 µs | -30~75% | overhead ~ 5% first-q，**淨贏** |
| **2d (interior only)** | 2-6 µs | -10~50% | 幾乎沒成本，**淨贏** |
| **2e_K10** | 4-7 µs | -45~85% | overhead < 5%，**淨贏** |
| **2e_K500** | ~80 µs | -45~75% | overhead 10-20% first-q，**仍淨贏** |
| **2f SLRU** | **1,200-1,900 µs** | -94~95% | overhead **比 first-q 大 80-130 倍**！「first-q -94%」是誤導；真實 cold start 慢 7~12 倍 |

> **關鍵**：2f SLRU 的 first-q 看起來超強（17 µs），但 prefetch 自己花 1.8 ms。
> 端到端 cold start = prefetch + first_q = ~1,820 µs，**比 baseline (~500 µs) 慢 3.6×**。
> 2f 的真正價值不在 first query，在 warmup-pass 之後的 avg latency（已 documented 在第五維）。

## 怎麼用

要看「特定 (workload, layout, strategy) 的 prefetch overhead 是多少」：

```python
import csv
def get_prefetch_time(tool, layout, workload, strategy):
    with open('calibration/prefetch_time_summary.csv') as f:
        for r in csv.DictReader(f):
            if (r['tool'] == tool and r['db_layout'] == layout
                and r['workload'] == workload and r['strategy'] == strategy):
                return float(r['prefetch_time_us_med'])
    return None
```

要算 end-to-end cold start：
```
end_to_end_us = prefetch_time_us + first_query_us
```

## 重跑

```bash
cd /home/u03/sqlite-research-project-sharing
python3 calibrate_prefetch_time.py   # ~1 分鐘
python3 calibration/aggregate.py     # 即時
```

## 跟線上 benchmark 的差距

我們的 calibration 是「離線量 prefetch tool 自身 wallclock」，**沒模擬**：
- `benchmark_harness` fork + exec 的 overhead（~1-2 ms）
- 從 `madvise` 回傳到第一筆 query 開始計時的 gap
- async readahead 對後續 first_query 的 latency 影響（這個會反映在 first_query_us，不在 prefetch_time）

對 prefetch_layers / prefetch_access：calibration time 就是 prefetch tool 的真實
overhead，沒誤差。
對 prefetch_slru：calibration time (1.2-1.8 ms) 比 dimension docs 裡的 "7.5 ms"
小很多——原因是 mincore-based dump 在第五維是包含 mincore 量測 + readahead 等
**整段** post-cold 時間。要更精細的話需要拆解 prefetch_slru.c 內部 timer。
