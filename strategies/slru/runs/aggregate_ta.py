#!/usr/bin/env python3
"""Aggregate 2f x 1c matrix results: median per cell for first_q_us, avg_us, prefetch_us, n_prefetch.

avg_us is extracted from stderr logs (the inline capture in runmatrix_ta.sh has a known bug:
the harness writes ops=... to stderr, but the script redirects 2> log before the grep on stdout
so the inline LINE comes back empty).
"""
import csv
import re
import statistics
from pathlib import Path

DIR = Path(__file__).parent
SRC = DIR / "matrix_ta_results.csv"
OUT = DIR / "matrix_ta_aggregated.csv"

# Load matrix CSV
rows = list(csv.DictReader(SRC.open()))

# Patch in avg_us from stderr log per row
avg_re = re.compile(r"avg_latency_us=([0-9.]+)")
for r in rows:
    log = DIR / f"log_{r['workload']}_{r['strategy']}_ta_r{r['rep']}.err"
    if log.exists():
        m = avg_re.search(log.read_text())
        if m:
            r["avg_us"] = m.group(1)

# Group by (workload, strategy) → list of reps
by_cell = {}
for r in rows:
    key = (r["workload"], r["strategy"])
    by_cell.setdefault(key, []).append(r)

# Median per cell
fields = ["workload", "strategy", "n_reps",
          "first_q_us_med", "avg_us_med",
          "prefetch_us_med", "n_prefetch"]
out_rows = []
for (wl, strat), reps in sorted(by_cell.items()):
    fq = [float(r["first_query_us"]) for r in reps if r["first_query_us"]]
    av = [float(r["avg_us"]) for r in reps if r["avg_us"]]
    pf = [float(r["prefetch_us"]) for r in reps if r["prefetch_us"]]
    n_pf = reps[0]["n_prefetch"]
    out_rows.append({
        "workload": wl,
        "strategy": strat,
        "n_reps": len(reps),
        "first_q_us_med": f"{statistics.median(fq):.2f}" if fq else "",
        "avg_us_med": f"{statistics.median(av):.2f}" if av else "",
        "prefetch_us_med": f"{statistics.median(pf):.2f}" if pf else "",
        "n_prefetch": n_pf,
    })

with OUT.open("w") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(out_rows)

print(f"Wrote {OUT}")
print()
print("=== 2f SLRU × Layout 1c (type-aware) — median per cell ===")
print()
# Pretty-print
hdr = f"{'WL':<3} {'strat':<10} {'first_q (µs)':>13} {'avg (µs)':>10} {'prefetch (µs)':>14} {'n_pf':>6}"
print(hdr)
print("-" * len(hdr))
for r in out_rows:
    print(f"{r['workload']:<3} {r['strategy']:<10} "
          f"{r['first_q_us_med']:>13} {r['avg_us_med']:>10} "
          f"{r['prefetch_us_med']:>14} {r['n_prefetch']:>6}")

# Compare to baseline within workload
print()
print("=== vs baseline (within workload) ===")
print()
for wl in sorted({r["workload"] for r in out_rows}):
    cells = {r["strategy"]: r for r in out_rows if r["workload"] == wl}
    base_fq = float(cells["baseline"]["first_q_us_med"])
    base_av = float(cells["baseline"]["avg_us_med"]) if cells["baseline"]["avg_us_med"] else None
    for s in ("layers5", "slru"):
        c = cells[s]
        fq = float(c["first_q_us_med"])
        delta_fq = (fq - base_fq) / base_fq * 100
        line = f"  WL={wl} {s:<8}: first_q {fq:>7.2f} µs ({delta_fq:+.1f}%)"
        if base_av and c["avg_us_med"]:
            av = float(c["avg_us_med"])
            delta_av = (av - base_av) / base_av * 100
            line += f"   avg {av:.2f} µs ({delta_av:+.1f}%)"
        print(line)
