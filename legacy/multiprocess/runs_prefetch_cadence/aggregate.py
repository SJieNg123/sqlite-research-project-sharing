#!/usr/bin/env python3
"""Summarize cadence_results.csv — group by cadence, report median/mean first_q."""
import csv, sys, statistics
from pathlib import Path

p = Path(__file__).parent / "cadence_results.csv"
rows = list(csv.DictReader(p.open()))
by_cad: dict[str, list[float]] = {}
faults: dict[str, list[int]] = {}
for r in rows:
    c = r["cadence"]
    by_cad.setdefault(c, []).append(float(r["first_q_us"]))
    faults.setdefault(c, []).append(int(float(r["majflt"])))

print(f"{'cadence':>10} {'n':>3} {'median':>9} {'mean':>9} {'min':>9} {'max':>9} {'majflt':>8}")
order = ["1.0", "5.0", "30.0", "never"]
for c in order:
    if c not in by_cad: continue
    v = by_cad[c]
    fl = faults[c]
    print(f"{c:>10} {len(v):>3} "
          f"{statistics.median(v):>9.1f} {statistics.mean(v):>9.1f} "
          f"{min(v):>9.1f} {max(v):>9.1f} {statistics.mean(fl):>8.1f}")

# vs never baseline
never_mean = statistics.mean(by_cad["never"])
print(f"\nvs never (mean={never_mean:.1f}µs):")
for c in order:
    if c == "never": continue
    m = statistics.mean(by_cad[c])
    pct = (m - never_mean) / never_mean * 100
    print(f"  {c:>10}s  mean={m:>7.1f}µs  Δ={pct:+.1f}%")
