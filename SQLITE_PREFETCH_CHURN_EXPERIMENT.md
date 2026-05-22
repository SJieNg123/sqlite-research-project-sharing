# SQLite Page Churn Experiment

`sqlite_prefetch_churn_experiment.py` 是這個 repo 的外層 orchestration script。它會在同一個工作 DB 上循環執行：

1. 分析目前 DB 的 page layout。
2. 產生本輪 prefetch / residency-before 用的 `post_cold_<label>.sh`。
3. 呼叫 `benchmark_harness`；harness 會先完成 SQLite open / prepare，接著在內部清空 Linux page cache。
4. harness 在 drop cache 後執行 `post_cold_<label>.sh`，依照目前 layout prefetch interior pages 並擷取 `residency_before`。
5. harness 量測 prefetch 後的 query latency。
6. 外層腳本擷取 `residency_after`。
7. 外層腳本執行寫入負載，讓 DB page layout 產生 churn。

這個腳本的目標是觀察「DB layout 隨寫入變化後，prefetch 對 cold-start query latency 的效果如何變化」。

## 權限模型

只有清空 Linux page cache 需要 root 權限。腳本本身、prefetch、benchmark、classifier、residency checker、寫入負載都應該用一般使用者執行。

建議把 drop-cache helper 安裝到固定 root-owned 路徑：

```bash
sudo install -o root -g root -m 0755 drop_caches.sh /usr/local/bin/dropcache.sh
```

用 `sudo visudo` 加入最小 sudoers 規則，將 `user` 換成 `whoami` 的輸出：

```sudoers
user ALL=(root) NOPASSWD: /usr/local/bin/dropcache.sh
```

測試：

```bash
sudo -n /usr/local/bin/dropcache.sh
```

如果沒有 `sudo: a password is required`，就可以自動化執行。

## 建置

先 build 所需工具：

```bash
make
```

`make` 會建置：

- `classify_pages`
- `residency_checker`
- `benchmark_harness`
- `prefetch_vacuum/src/prefetch`
- `prefetch_vacuum/src/prefetch_layers`

## 常用執行方式

```bash
python3 sqlite_prefetch_churn_experiment.py \
  --force \
  --run-benchmarks \
  --write-workload generated_workloads/page_churn_write.txt \
  --drop-caches-script /usr/local/bin/dropcache.sh \
  --prefetch-mode layers \
  --prefetch-pages 5 \
  --benchmark-cold-advice none \
  --benchmark-workload generated_workloads/page_churn_benchmark_high.txt
```

`--benchmark-cold-advice none` 很重要。冷啟動由 `benchmark_harness` 在 SQLite open/prepare 之後呼叫 `dropcache.sh` 完成，接著透過 `post_cold_<label>.sh` 執行 prefetch；如果讓 `benchmark_harness` 再做 madvise cold advice，就可能把 prefetch 結果清掉。

## Memory-Limited cgroup

目前 benchmark 流程把 cold boundary 放在 `benchmark_harness` 裡面，而不是在外層 Python 腳本先 drop cache。每一輪的順序是：

```text
benchmark_harness mmap DB
SQLite open + prepare statements
sudo -n dropcache helper
post_cold_<label>.sh: prefetch, then residency_before
run benchmark workload
residency_after outside the memory-limited scope
```

因此 `residency_before_*` 代表「drop cache 之後、prefetch 之後、正式 query 之前」的 residency。這也避免 SQLite open/schema prepare 先把 DB 前段 pages 暖進 page cache，讓 `first_query_latency_us` 更接近真正 cold-start query latency。

若要讓 cold-start measurement 在受限記憶體環境下執行，可以用 `--systemd-memory-max`。腳本會在每個 checkpoint 用 `systemd-run --user --scope -p MemoryMax=...` 執行量測段落：

```bash
python3 sqlite_prefetch_churn_experiment.py \
  --force \
  --run-benchmarks \
  --write-workload generated_workloads/page_churn_write.txt \
  --drop-caches-script /usr/local/bin/dropcache.sh \
  --prefetch-mode layers \
  --prefetch-pages 5 \
  --benchmark-cold-advice none \
  --benchmark-workload generated_workloads/page_churn_benchmark_high.txt \
  --systemd-memory-max 512M
```

這個設定只限制每輪的 cold-start measurement segment：

```text
benchmark_harness -> drop cache -> prefetch -> residency snapshot -> query benchmark
```

寫入 workload、page classification、CSV summary 產生不在 memory-limited scope 裡。prefetch 和 `benchmark_harness` 會在同一個 scope 裡，讓 prefetch 載入的 page cache 也受到同一個 cgroup memory limit 影響。

若只想手動包單次 harness，等價的基本形式是：

```bash
systemd-run --user --scope -p MemoryMax=512M \
  ./benchmark_harness --db test.db --workload generated_workloads/page_churn_benchmark_high.txt
```

## Workloads

The experiment has two primary workload inputs:

| workload | default | role |
| --- | --- | --- |
| `--write-workload` | `generated_workloads/page_churn_write.txt` | Mutates the DB between checkpoints. This file can contain `read`, `update`, `insert`, `scan`, and `readmodifywrite`; `readmodifywrite` is mapped by `--rmw-action`, defaulting to `delete`. |
| `--benchmark-workload` | `generated_workloads/page_churn_benchmark_high.txt` | Read-only workload used by `benchmark_harness` to measure cold-start latency. `first_query_latency_us` comes from this file's first operation. |

`--workload` remains as a backward-compatible alias for `--write-workload`.
`--insert-workload` is a legacy optional third stream and is disabled by default.

## 預設輸出

預設產物會依照 prefetch mode 分流，避免 no-prefetch baseline 覆蓋 prefetch run：

```text
sqlite_page_churn_runs/no_prefetch/
sqlite_page_churn_runs/prefetch_layers/
sqlite_page_churn_runs/prefetch_range/
sqlite_page_churn_runs/prefetch_perpage/
```

每個 run 目錄裡的主要檔案：

| 路徑 | 用途 |
| --- | --- |
| `test_churn.db` | 從 `test.db` 複製出來、實際被寫入負載修改的工作 DB |
| `interior_page_churn_summary.csv` | 每個 checkpoint 的 page layout 摘要 |
| `interior_page_churn_pages.csv` | 每個 checkpoint 的 interior page 明細 |
| `sqlite_page_churn_benchmark_summary.csv` | 每個 checkpoint 的 benchmark latency 摘要 |
| `checkpoints/` | 每輪 `classify_pages` 的 CSV 和 layout 圖 |
| `benchmarks/` | 每輪 benchmark、prefetch wrapper、residency 結果和 run record |

## 每輪流程

每個 label，例如 `baseline`、`checkpoint_001`，會做：

1. `classify_pages` 產生當輪 page type CSV。
2. 外層腳本產生當輪 prefetch wrapper，例如 `prefetch_checkpoint_001.sh`。
3. 外層腳本產生 `post_cold_checkpoint_001.sh`。這個 script 會在 harness drop cache 後執行，內容包含 prefetch 以及 `residency_before` / joined CSV 產生。
4. 外層腳本呼叫 `benchmark_harness --cold-advice none`，並把 `--drop-caches-script`、必要時的 `--drop-caches-use-sudo`、以及 `--post-cold-script` 傳給 harness。
5. `benchmark_harness` 先 mmap DB、SQLite open、prepare statements。
6. `benchmark_harness` 在內部呼叫 drop-cache helper，例如 `sudo -n /usr/local/bin/dropcache.sh`。
7. `benchmark_harness` 執行 `post_cold_checkpoint_001.sh`，也就是在 drop cache 後、第一筆 benchmark query 前執行 prefetch 和 `residency_before`。
8. `benchmark_harness` 執行 benchmark workload，量測 `first_query_latency_us` 與 per-operation latency/faults。
9. 外層腳本在 benchmark 完成後擷取 `residency_after`，這一步不在 memory-limited measurement segment 裡。
10. 外層腳本執行一段寫入/更新/刪除 workload。
11. 進入下一個 checkpoint。

## Benchmark 輸出

`sqlite_page_churn_runs/<mode>/benchmarks/` 內常見檔案：

| 檔案 | 用途 |
| --- | --- |
| `prefetch_baseline.sh` | baseline 這輪自動產生的 prefetch command wrapper |
| `prefetch_checkpoint_001.sh` | checkpoint 001 的 prefetch command wrapper |
| `ops_checkpoint_001.csv` | `benchmark_harness` 的 per-operation latency/fault 結果 |
| `residency_before_checkpoint_001.csv` | prefetch 後、benchmark 前的 residency 結果 |
| `residency_before_joined_checkpoint_001.csv` | page type 與 before-residency 合併後的結果 |
| `residency_after_checkpoint_001.csv` | benchmark 後的 residency 結果 |
| `residency_after_joined_checkpoint_001.csv` | page type 與 after-residency 合併後的結果 |
| `runs/run-*.log` | `benchmark_harness` run record |

`prefetch_*.sh` 是中間產物，也是實驗紀錄。它固定記錄該輪 prefetch 用了哪個 DB、哪個 classify CSV、多少 pages、以及 page size。

`residency_before_*` 會和 prefetch、benchmark 一起位於 memory-limited measurement segment 裡。`residency_after_*` 則在 benchmark 完成後、回到一般環境再擷取，因此不受 `--systemd-memory-max` 限制。

## 常用參數

| 參數 | 預設值 | 說明 |
| --- | --- | --- |
| `--source-db` | `test.db` | 原始 DB |
| `--work-db` | `sqlite_page_churn_runs/<mode>/test_churn.db` | 會被修改的工作 DB |
| `--force` | off | 若工作 DB 已存在，允許覆蓋並重新開始 |
| `--checkpoints` | `10` | checkpoint 數量 |
| `--ops-per-checkpoint` | `5000` | 每輪主 workload 操作數 |
| `--insert-ops-per-checkpoint` | `5000` | 每輪 insert workload 掃描數 |
| `--run-benchmarks` | off | 啟用 cold-start + prefetch + benchmark 循環 |
| `--drop-caches-script` | `./drop_caches.sh` | drop-cache helper |
| `--prefetch-mode` | `layers` | `none`、`range`、`perpage`、`layers` |
| `--prefetch-pages` | `5` | `layers` 模式 prefetch page 數 |
| `--benchmark-cold-advice` | `none` | 傳給 harness 的 cold advice 模式 |
| `--benchmark-sqlite-open-timing` | `before-cold` | SQLite open 在 drop cache 前完成 |
| `--benchmark-schema-init-timing` | `before-cold` | prepared statements 在 drop cache 前完成 |
| `--benchmark-workload` | `generated_workloads/page_churn_benchmark_high.txt` | benchmark query workload |
| `--systemd-memory-max` | 無 | 以 `systemd-run --user --scope -p MemoryMax=<value>` 執行每輪 cold-start measurement segment |

## 注意事項

- `--run-benchmarks` 使用 `sudo -n`，不會互動式要求密碼；sudoers 沒設好會直接失敗。
- 使用 prefetch 時，請維持 `--benchmark-cold-advice none`；drop cache 仍會透過 `--drop-caches-script` 在 harness 內部執行。
- 每輪寫入後都會重新 classify，避免用舊 page layout prefetch。
- 預設會用 `--force` 重新從 `test.db` 複製工作 DB，方便重複實驗。
- 舊版本曾把產物放在 repo 根目錄；新版預設都放在 `sqlite_page_churn_runs/<mode>/`。
