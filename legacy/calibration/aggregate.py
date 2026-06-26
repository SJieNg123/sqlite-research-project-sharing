#!/usr/bin/env python3
"""Aggregate prefetch_time_calibration.csv into one summary CSV with median over reps."""
import csv, statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path("/home/u03/sqlite-research-project-sharing")
SRC = ROOT / "calibration/prefetch_time_calibration.csv"
OUT = ROOT / "calibration/prefetch_time_summary.csv"

g = defaultdict(list)
with SRC.open() as f:
    for r in csv.DictReader(f):
        if r['prefetch_time_us'] == '':
            continue
        key = (r['tool'], r['db_layout'], r['workload'], r['strategy'], r['N_or_K'])
        g[key].append((float(r['prefetch_time_us']), int(r['n_prefetch']), int(r['n_syscalls'])))

with OUT.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["tool", "db_layout", "workload", "strategy", "N_or_K",
                "n_reps", "prefetch_time_us_med", "prefetch_time_us_min",
                "prefetch_time_us_max", "n_prefetch", "n_syscalls"])
    for (tool, layout, wl, strat, nk), rows in sorted(g.items()):
        ts = sorted(x[0] for x in rows)
        nph = rows[0][1]
        sysc = rows[0][2]
        w.writerow([tool, layout, wl, strat, nk, len(ts),
                    f"{statistics.median(ts):.2f}",
                    f"{ts[0]:.2f}",
                    f"{ts[-1]:.2f}",
                    nph, sysc])

print(f"wrote {OUT}: {len(g)} unique cells, 1 median row each")
