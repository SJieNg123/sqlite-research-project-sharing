"""Figure 5: Strategy comparison across workloads × layouts.

Story: no single best strategy for *first-query* — 2f_slru wins fq everywhere,
but the cheap structural picks (layers_5 / 2e_K10) carry most of the benefit at a
fraction of the preprocessing cost (see fig 14). 2e_K10 shines on C.

Data (P0 master batch, authoritative): p0_runs/summary_p0.csv, async arm,
first-query median of 10 reps (warmup dropped).
"""
from plot_utils import ROOT, save, load_p0, P0_STRATS, P0_LABELS, STRATEGY_COLORS
import matplotlib.pyplot as plt
import numpy as np

P0 = load_p0("async")
LAYOUTS = [("orig", "1a"), ("vacuum", "1b"), ("ta", "1c")]
STRATS = P0_STRATS                      # baseline + 6 strategies
WORKLOADS = ["A", "B", "C"]

fig, axes = plt.subplots(1, 3, figsize=(14, 4.6), sharey=True)
n_strats = len(STRATS)
gap = 0.15
bar_w = (1 - gap) / n_strats

allvals = []
for ax, w in zip(axes, WORKLOADS):
    x = np.arange(len(LAYOUTS))
    for i, s in enumerate(STRATS):
        vals = [float(P0[(w, l, s)]['fq_median']) for l, _ in LAYOUTS]
        allvals += vals
        offset = (i - (n_strats - 1) / 2) * bar_w
        ax.bar(x + offset, vals, bar_w, color=STRATEGY_COLORS.get(s, "#3b82f6"),
               label=P0_LABELS[s] if w == "A" else None)
    ax.set_title(f"Workload {w}")
    ax.set_xticks(x, [n for _, n in LAYOUTS])
    ax.set_xlabel("layout")
    ax.grid(True, axis="y", linestyle=":", alpha=0.4)

axes[0].set_ylabel("first-query latency (µs, async, median of 10 reps)")
axes[0].set_ylim(0, max(allvals) * 1.05)
fig.legend(loc="upper center", ncol=n_strats, bbox_to_anchor=(0.5, 1.04),
           fontsize=9, frameon=False)
fig.suptitle("All strategies × layouts × workloads · P0 · async arm · first-query median",
             fontsize=12, y=1.10)
fig.tight_layout()
save(fig, "05_strategy_comparison")
