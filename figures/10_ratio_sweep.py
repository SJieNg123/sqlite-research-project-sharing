"""Figure 10: 2e K-sweep (interior + top-K leaves) — P0.

Story: 2e prefetches resident interior pages PLUS the top-K hot leaf pages.
Sweeping K shows how first-query latency falls as more hot leaves are pinned;
the shape is workload×layout dependent (A/C have natural hot leaves → drop fast;
B uniform has none → flat). K=0 is 2d (interior-only).

Data (P0): p0_runs_ksweep/summary_p0.csv — 2d + 2e_K{10,40,50,92,100,500} on
A/B/C × {orig,vacuum,ta}, async arm, first-query median (warmup dropped).
"""
import csv, re
from collections import defaultdict
from plot_utils import ROOT, LAYOUT_COLORS, save
import matplotlib.pyplot as plt

SUMMARY = ROOT / "p0_runs_ksweep/summary_p0.csv"

# (workload, db) -> {K: fq_median}; 2d => K=0
g = defaultdict(dict)
for r in csv.DictReader(open(SUMMARY)):
    if r["arm"] != "async" or not r["fq_median"]:
        continue
    s, w, db = r["strategy"], r["workload"], r["db"]
    if s == "2d":
        g[(w, db)][0] = float(r["fq_median"])
    else:
        m = re.fullmatch(r"2e_K(\d+)", s)
        if m:
            g[(w, db)][int(m.group(1))] = float(r["fq_median"])

WORKLOADS = ["A", "B", "C"]
LAYOUTS = [("orig", "1a"), ("vacuum", "1b"), ("ta", "1c")]
Ks = sorted({k for d in g.values() for k in d})

fig, axes = plt.subplots(1, 3, figsize=(13, 4.6), sharey=True)
ymax = max((v for d in g.values() for v in d.values()), default=1)
for ax, w in zip(axes, WORKLOADS):
    for db, lbl in LAYOUTS:
        d = g.get((w, db), {})
        ys = [d.get(k) for k in Ks]
        ax.plot(Ks, ys, "-o", color=LAYOUT_COLORS[db], lw=1.7, ms=5, label=f"layout {lbl}")
    ax.set_xscale("symlog", linthresh=10)
    ax.set_xticks([0, 10, 40, 92, 100, 500])
    ax.set_xticklabels(["0\n(2d)", "10", "40", "92", "100", "500"], fontsize=8)
    ax.set_xlabel("K (top hot-leaf pages prefetched)")
    ax.set_title(f"Workload {w}")
    ax.grid(True, linestyle=":", alpha=0.4)
    if w == "A":
        ax.set_ylabel("first-query latency (µs, async, median)")
        ax.legend(loc="upper right", fontsize=8)
axes[0].set_ylim(0, ymax * 1.05)
fig.suptitle("2e K-sweep · interior + top-K hot leaves · P0 (async first-query)", fontsize=12, y=1.02)
fig.tight_layout()
save(fig, "10_ratio_sweep")
