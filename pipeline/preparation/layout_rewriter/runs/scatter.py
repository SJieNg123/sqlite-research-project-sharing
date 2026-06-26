#!/usr/bin/env python3
"""Compute scatter score (matplotlib-free) from a classify_pages CSV."""
import sys, csv
from collections import Counter
path = sys.argv[1]
rows = []
with open(path) as f:
    for r in csv.DictReader(f):
        rows.append((int(r["page_number"]), r["page_type"]))
rows.sort()
n = len(rows)
counts = Counter(pt for _, pt in rows)
interior_pos = [pn for pn, pt in rows if pt.startswith("interior")]
print(f"file: {path}")
print(f"  total pages: {n}")
for t, c in sorted(counts.items(), key=lambda x: -x[1]):
    print(f"  {t:16s} {c:5d}  ({100*c/n:5.2f}%)")
if interior_pos:
    k = len(interior_pos)
    mean_pos = sum(interior_pos) / k
    ideal_clustered = (k + 1) / 2
    ideal_scattered = n / 2
    ratio = (mean_pos - ideal_clustered) / (ideal_scattered - ideal_clustered)
    print(f"  interior: first={min(interior_pos)} last={max(interior_pos)} "
          f"mean={mean_pos:.1f}")
    print(f"  scatter score: {ratio:.4f}  (0 clustered, 1 scattered)")
