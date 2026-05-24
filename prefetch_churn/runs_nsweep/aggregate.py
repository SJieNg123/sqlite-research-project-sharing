#!/usr/bin/env python3
"""Aggregate N-sweep churn results into a matrix CSV and summary."""
import csv
from pathlib import Path

DIR = Path(__file__).parent
NS = [0, 1, 5, 10, 20, 46, 92]
LABELS = ["baseline", "checkpoint_001", "checkpoint_002", "checkpoint_003",
          "checkpoint_004", "checkpoint_005", "checkpoint_006",
          "checkpoint_007", "checkpoint_008", "checkpoint_009",
          "checkpoint_010"]

# Load first_query_latency_us per (N, label)
data = {}
for n in NS:
    csv_path = DIR / f"n{n}" / "benchmark_summary.csv"
    rows = list(csv.DictReader(csv_path.open()))
    for r in rows:
        data[(n, r["label"])] = float(r["first_query_latency_us"])

# Write matrix CSV: rows=labels, cols=N values
matrix_path = DIR / "matrix_first_q_us.csv"
with matrix_path.open("w") as f:
    w = csv.writer(f)
    w.writerow(["label", "ops"] + [f"N={n}" for n in NS])
    for label in LABELS:
        ops = 0 if label == "baseline" else int(label.split("_")[1]) * 5000
        row = [label, ops] + [f"{data[(n, label)]:.2f}" for n in NS]
        w.writerow(row)
print(f"matrix → {matrix_path}")

# Summary: per-N avg across checkpoint_001..010 (skip baseline ops=0 + warmup)
ckp_labels = LABELS[1:]  # checkpoint_001..010
summary_path = DIR / "summary_avg_first_q.csv"
baseline_n0 = sum(data[(0, l)] for l in ckp_labels) / len(ckp_labels)
with summary_path.open("w") as f:
    w = csv.writer(f)
    w.writerow(["N", "avg_first_q_us_ck1-10", "improvement_vs_N0_pct"])
    for n in NS:
        avg = sum(data[(n, l)] for l in ckp_labels) / len(ckp_labels)
        impr = (avg - baseline_n0) / baseline_n0 * 100
        w.writerow([n, f"{avg:.2f}", f"{impr:+.1f}%"])
print(f"summary → {summary_path}")

# Print results
print("\n=== Matrix (first_query_latency_us by N × checkpoint) ===")
with matrix_path.open() as f:
    for line in f:
        print(line.rstrip())

print("\n=== Summary (avg over checkpoint_001..010, baseline N=0) ===")
with summary_path.open() as f:
    for line in f:
        print(line.rstrip())
