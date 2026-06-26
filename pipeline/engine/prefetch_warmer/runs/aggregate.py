#!/usr/bin/env python3
"""Aggregate ablation_raw.csv into the rigor-compliant summary:
median / p95 / p99 / min / stdev of first-query latency per arm, plus the
two-version TTFQ (optimistic = first-query only; conservative = + warmer time).
"""
import csv
import statistics as st
import sys

RAW = sys.argv[1] if len(sys.argv) > 1 else "ablation_raw.csv"

rows = {}
warm = {}
majflt = {}
order = []
with open(RAW) as f:
    for r in csv.DictReader(f):
        m = r["mode"]
        if m not in rows:
            rows[m] = []; warm[m] = []; majflt[m] = []; order.append(m)
        try:
            rows[m].append(float(r["first_query_us"]))
            warm[m].append(float(r["warmer_us"]))
            majflt[m].append(int(r["majflt"]))
        except (ValueError, KeyError):
            pass


def pct(xs, p):
    xs = sorted(xs)
    if not xs:
        return float("nan")
    k = (len(xs) - 1) * p / 100.0
    lo = int(k)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


base = st.median(rows[order[0]]) if order and rows[order[0]] else None

hdr = f"{'arm':<20}{'n':>4}{'median':>9}{'p95':>9}{'p99':>9}{'min':>8}{'stdev':>8}" \
      f"{'warm_us':>10}{'majflt':>8}{'TTFQ_opt':>10}{'TTFQ_cons':>11}{'vs_base':>9}"
print(hdr)
print("-" * len(hdr))
for m in order:
    xs = rows[m]
    if not xs:
        print(f"{m:<20}  (no data)"); continue
    med = st.median(xs)
    wmed = st.median(warm[m]) if warm[m] else 0.0
    ttfq_opt = med                 # warmer assumed off critical path (background/slack)
    ttfq_cons = med + wmed         # warmer on critical path
    vs = f"{(med/base-1)*100:+.0f}%" if base else ""
    print(f"{m:<20}{len(xs):>4}{med:>9.1f}{pct(xs,95):>9.1f}{pct(xs,99):>9.1f}"
          f"{min(xs):>8.1f}{(st.pstdev(xs) if len(xs)>1 else 0):>8.1f}"
          f"{wmed:>10.1f}{st.median(majflt[m]):>8.0f}{ttfq_opt:>10.1f}{ttfq_cons:>11.1f}{vs:>9}")

print()
print("TTFQ_opt  = median first-query only (warmer assumed to run in background/idle slack)")
print("TTFQ_cons = median first-query + median warmer_us (warmer on the critical path)")
print("vs_base   = TTFQ_opt change vs L0_off median (optimistic view)")
print("→ 真相落在 opt 與 cons 之間，看部署有沒有啟動空檔；cold start tail-sensitive，看 p95/p99。")
