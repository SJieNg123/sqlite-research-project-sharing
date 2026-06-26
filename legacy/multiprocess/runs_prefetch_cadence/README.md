# Multi-process Prefetch Worker Cadence

Tests the README §13 research gap: **how often should a background prefetch worker run when multiple processes share a DB that's being continuously churned?**

## Design

Three concurrent actors on the same 103 MB DB:

1. **Writer** (thread, sqlite3 Python) — replays a 5000-op slice of `page_churn_write.txt` in a loop, ~200 writes/sec. Inserts go to id=700000+ so they land on **new** leaves (separate from reader's hot leaves at [590k, 610k]). Updates / readmodifywrite touch existing rows in the workload's pre-existing range.
2. **Prefetch worker** (thread, calls `prefetch_access` binary) — every `T_PREFETCH` seconds, runs 2e_K10 prefetch (interior + top-10 hot leaves for workload C). Uses the static `hot2e_C_orig_K10.csv` (no per-fire warmup).
3. **Probe** (main thread) — every round: evict all DB pages → sleep `T_GAP` (3 s) → run `benchmark_harness` with 100 reads from workload C and `--cold-advice none` (so the reader inherits whatever cache state the prefetcher left).

We sweep `T_PREFETCH ∈ {1.0 s, 5.0 s, 30.0 s, never}` with 4 rounds per cadence.

The probe measures: did the prefetcher fire between the evict and the read? If yes → cache warm → low first_q. If no → cache cold → high first_q.

## Result

| Cadence (s) | n | median first_q | mean first_q | Δ vs never | majflt |
|-------------|---|----------------|--------------|------------|--------|
| 1.0         | 4 | 16 µs          | 19 µs        | **-94%**   | 19.8   |
| 5.0         | 4 | 164 µs         | 177 µs       | -40%       | 20.2   |
| 30.0        | 4 | 357 µs         | 322 µs       | +9% (noise)| 20.5   |
| never       | 4 | 315 µs         | 295 µs       | —          | 20.5   |

**Δ_prefetch** (gap between last prefetch fire and the evict that started this probe) confirms the mechanism:

- Cadence=1 s, all rounds: Δ ≈ -2 s (prefetcher fired ~2 s **after** evict, i.e. during the 3 s gap, before the read) → hot.
- Cadence=5 s: Δ ranged from -2 s (warm, 12 µs) to +1 s (cold, 315 µs) → 50/50 hit rate, high variance.
- Cadence=30 s: Δ grew monotonically (2, 5, 8, 11 s) — the single startup fire was the only one; subsequent rounds caught no prefetch → cold.

## Rule of thumb

**Cadence ≤ gap_s gives reliable warmth; cadence ≥ 10× gap_s is equivalent to no prefetcher.**

For a typical interactive workload where the application may sit idle 1-3 s between memory-pressure events, a **1 s prefetcher cadence** drops first-query latency from ~300 µs to ~20 µs (-94%) at a cost of ~1 madvise burst per second (~14 syscalls × 1 = 14 syscalls/s per shared DB).

## Caveats

1. **Writer doesn't churn the hot leaves** in this run (writer inserts to id ≥ 700000, reader queries id ∈ [590k, 610k]). A more aggressive experiment would have the writer also touch reader's range — expected: 5 s cadence becomes uniformly cold because writer-mutated leaves are no longer in the static hot set.
2. **Static hotpages** — the prefetcher uses `hot2e_C_orig_K10.csv` from t=0. Per the `prefetch_churn/runs_access_churn` experiment, static hot leaves on workload C survive 50 k-op churn (because inserts to high keys hit the same leaves). For workloads with shifting access patterns, the prefetch worker would need periodic re-warmup.
3. **Single reader** — this is a serial probe, not N concurrent readers. The MAP_SHARED page cache means N readers all benefit from one prefetch (per `multiprocess/MULTIPROCESS_MMAP.md`), so multi-reader scaling should be effectively free.
4. **OS memory pressure is simulated by explicit `evict`**. In production, eviction happens via natural memory pressure (other processes, kernel reclaim). The probe model is a worst-case sawtooth — real cache eviction is more gradual.

## Files

- `cadence_experiment.py` — driver (writer thread + prefetch thread + probe loop)
- `aggregate.py` — summarize CSV (median/mean per cadence)
- `cadence_results.csv` — per-probe metrics (cadence, round, first_q, majflt, time_since_prefetch, fires)
- `rec/` — benchmark_harness run records + writer/prefetch logs (regenerable)

## Reproduce

```bash
cd /home/u03/sqlite-research-project-sharing/multiprocess/runs_prefetch_cadence
python3 cadence_experiment.py --rounds 4 --gap-s 3.0 --cadences "1.0,5.0,30.0,never"
python3 aggregate.py
```

Runtime: ~60 s.
