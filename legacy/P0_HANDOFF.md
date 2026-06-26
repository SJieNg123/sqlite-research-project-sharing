# P0 Pipeline — Handoff (continue on Ubuntu workstation)

> Written for the Claude Code session on the **u03 Ubuntu workstation** to pick up and run the
> P0 master batch. Authored on the Windows session where the tooling was built (can't run the
> Linux harness there). **Locked spec lives in [IMPLEMENTATION_PIPELINES.md §3](IMPLEMENTATION_PIPELINES.md).**

## What this branch adds (3 P0 tools + doc locks)

| File | What | Status |
|---|---|---|
| `benchmark_harness/benchmark_harness.c` | new `--verify-hotset <csv>` flag → emits `verify_cold_pct` (after drop-caches, before prefetch) and `verify_delivery_pct` (after prefetch, **right before first query**, one `fill_mincore_vec`, ~µs). Fixes "verification perturbs async fq" (漏洞 2). | new funcs syntax-checked w/ stubs (`-Wall -Wextra` clean); **needs Linux build** |
| `p0_env.sh` | pins + records governor=performance / read_ahead_kb (def 128) / THP=madvise; prints one `P0_ENV …` line. Fixes "env unpinned/unrecorded" (漏洞 1). | `sh -n` OK; needs root for sysfs writes |
| `run_p0.py` | general two-arm runner: every (workload×layout×strategy) cell run as **pread (oracle)** + **async (fadvise)** on the SAME hotset (warmer = unified delivery engine). Builds warmer-format hotsets by joining strategy-selected pages with classify. rep-major, warmup drop, `--verify-hotset` wired. Emits `raw_p0.csv` + `summary_p0.csv`. | `--dry-run`/`--list` verified on Windows; hotset page counts match repo's known numbers |
| `REPORT.md` | new §3.5 "pread oracle vs async hint" (selection–delivery decomposition, delivery_loss = fq_async−fq_pread, read_ahead_kb cap) | — |
| `IMPLEMENTATION_PIPELINES.md` | §3 rewritten as **locked P0 spec** (F1–F8 frozen list, env, two arms, in-harness verify, reps/agg, ra_kb sweep) | — |

## Locked decisions (don't re-litigate; see §3.0 F1–F8)
- SQLite: `cache_size=0` + `mmap_size=full` (already in harness code).
- Cold clear: `/usr/local/sbin/drop-caches` (full-machine, echo 3).
- **read_ahead_kb = 128** primary + sweep {0,128,512} on representative cells.
- **pread = reproducible headline/oracle** (report fq only, NOT e2e — it's not deployable);
  **async = realistic** (always report with `delivery_pct`). pread 3 reps, async 10 reps, drop rep-1 warmup, rep-major.
- Output: long format, one row per (workload,db,strategy,arm,rep).

## Next steps on the workstation (in order)

```bash
cd ~/sqlite-research-project-sharing
git fetch origin && git checkout p0-pipeline      # this branch

# 1. build the patched harness (Linux-only: mmap/mincore/madvise)
cd benchmark_harness
gcc -O2 -I. benchmark_harness.c sqlite3.c -o benchmark_harness -lpthread -ldl
./benchmark_harness --help | grep verify-hotset    # confirm the new flag exists
cd ..

# 2. build warmer if missing
gcc -O2 prefetch_warmer/src/warmer.c -o prefetch_warmer/src/warmer

# 3. sanity-check the matrix WITHOUT running (no root needed)
python3 run_p0.py --dry-run            # check cells + hotset page counts look right
python3 run_p0.py --list

# 4. smoke test ONE cell end-to-end (needs the drop-caches setuid wrapper)
sudo sh p0_env.sh layout_rewriter/runs/test.db        # pin + print P0_ENV
python3 run_p0.py --workloads A --layouts orig --strategies layers_5 --pread-reps 1 --async-reps 2
#   inspect p0_runs/raw_p0.csv: cold_pct≈0, pread delivery_pct≈100, async delivery_pct=whatever,
#   fq_pread < fq_async expected; preproc_us(pread)~ms, preproc_us(async)~µs.

# 5. full batch (NIGHTLY — full-machine drop wipes everyone's page cache; announce first)
python3 run_p0.py            # full matrix → p0_runs/{raw_p0.csv,summary_p0.csv,env.txt}
```

## Open caveats to resolve before trusting the full run
1. **2f / 2e hotsets are pre-P0 inputs (F7).** `run_p0.py` pulls `2f_slru` from
   `prefetch_slru/runs/hotpages_*.csv` and `2e_K*` from `prefetch_access/runs/hot2e_*.csv` — these were
   produced under the OLD (P1) pipeline. Per F7 (frozen-hotset rule), regenerate them with a P0 warmup
   pass and checksum-freeze before the master batch, OR accept they carry P1 provenance and note it.
   (A `--regen-hotsets` step was discussed but not yet built.)
2. **`run_p0.py` ROOT** defaults to `/home/u03/sqlite-research-project-sharing`. If the workstation path
   differs, set `P0_ROOT=$(pwd)` or edit the constant.
3. **harness build not yet done on Linux** — step 1 is the first thing to verify (the C compiles clean
   in isolation but full link needs sqlite3.c + pthread/dl on Linux).
4. The repo's CSV "pointer files" (Windows checkout) are real symlinks on Linux; `run_p0.py` handles both.

## Strategy → hotset selection (how run_p0.py builds each cell, for reference)
- `layers_N` → first N interior pages by file offset (from classify).
- `2d` → resident interior pages (from `prefetch_access/runs/hotpages_{w}{suffix}.csv` ∩ interior).
- `2e_K10/K500` → curated interior+top-K leaves (from `hot2e_{W}_{layout}_K{K}.csv`, is_resident==1).
- `2f_slru` → whole resident working set (from slru `hotpages_*`).
All normalised to warmer format `page_number,file_offset` (warmer reads col2 as the pread/fadvise offset).
