"""Figure 3: Cumulative latency over the first 50 queries (warmup region).

Story: the cold→warm transition is where prefetch saves time. The slope = current
per-query latency; baseline is steep for the first ~10 queries (cold faults), while
2e_K500 / 2f_SLRU keep the slope shallow from query 1 (hot pages already mapped).

Data (P0): one representative cold run per strategy from the P0 master batch,
p0_runs/work/rec_{baseline_,}A_orig_<strategy>/ops.csv (async arm, layout=orig).
Single trace each (the batch keeps the last rep's per-op CSV), so no rep band.
"""
import csv
import numpy as np
from plot_utils import ROOT, save
import matplotlib.pyplot as plt

WORK = ROOT / "p0_runs/work"
ARMS = [
    ("baseline", "baseline (no prefetch)",            "#9ca3af"),
    ("layers_5", "layers_5 (5 interior)",             "#3b82f6"),
    ("2e_K10",   "2e_K10 (interior + 10 hot leaves)", "#059669"),
    ("2e_K500",  "2e_K500 (interior + 500 leaves)",   "#064e3b"),
    ("2f_slru",  "2f_SLRU (mincore dump)",            "#f59e0b"),
]
N_WARMUP = 50

def trace(strategy, n):
    d = WORK / ("rec_baseline_A_orig" if strategy == "baseline" else f"rec_A_orig_{strategy}")
    p = d / "ops.csv"
    if not p.exists():
        return None
    lat = []
    with p.open() as f:
        rd = csv.reader(f); next(rd)
        for row in rd:
            lat.append(int(row[5]) / 1000.0)   # elapsed_ns -> us
            if len(lat) == n:
                break
    return np.asarray(lat)

fig, ax = plt.subplots(figsize=(9, 4.6))
end_vals = []
for strat, label, color in ARMS:
    lat = trace(strat, N_WARMUP)
    if lat is None or lat.size == 0:
        continue
    cum = np.cumsum(lat)
    x = np.arange(1, len(cum) + 1)
    ax.plot(x, cum, label=label, color=color, lw=1.8)
    end_vals.append((cum[-1], color))

# right-margin cumulative labels, staggered so they don't overlap
end_vals.sort(key=lambda t: -t[0])
last_y, y_min_sep = None, (max(v for v, _ in end_vals) * 0.06 if end_vals else 0)
for v, color in end_vals:
    y = v if last_y is None or (last_y - v) >= y_min_sep else last_y - y_min_sep
    ax.text(N_WARMUP + 0.6, y, f"{v:.0f} µs", color=color, fontsize=9, va="center", fontweight="bold")
    last_y = y

ax.set_xlabel("query # (1 = first, cold)")
ax.set_ylabel("cumulative latency to N-th query (µs)")
ax.set_title("Cold→warm transition · Workload A · layout orig · P0 (one cold run each)")
ax.set_xlim(0, N_WARMUP + 7)
ax.legend(loc="upper left", fontsize=9)
fig.tight_layout()
save(fig, "03_latency_cdf")
