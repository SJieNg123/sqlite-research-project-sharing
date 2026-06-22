"""Figure 2: Layout × strategy effect on first-query latency (Workload A).

Story: layout interacts with strategy. The Δ callout shows the best strategy vs
the (layout-specific) no-prefetch baseline per layout.

Data (P0 master batch, authoritative): p0_runs/summary_p0.csv, Workload A, async arm,
first-query median of 10 reps (warmup dropped).
"""
from plot_utils import ROOT, save, load_p0, STRATEGY_COLORS
import matplotlib.pyplot as plt
import numpy as np

P0 = load_p0("async")
LAYOUTS = [("orig", "1a (orig)"), ("vacuum", "1b (VACUUM)"), ("ta", "1c (type-aware)")]
# representative strategy slice for the layout-interaction story
STRATS = ["baseline", "layers_5", "2e_K10", "2f_slru"]
LABELS = {"baseline": "baseline\n(no prefetch)", "layers_5": "layers_5",
          "2e_K10": "2e_K10", "2f_slru": "2f SLRU"}

def fq(layout, s):
    return float(P0[("A", layout, s)]['fq_median'])

fig, ax = plt.subplots(figsize=(8.8, 4.4))
x = np.arange(len(LAYOUTS))
w = 0.20
allvals = []
for i, s in enumerate(STRATS):
    vals = [fq(layout, s) for layout, _ in LAYOUTS]
    allvals += vals
    bars = ax.bar(x + (i - 1.5) * w, vals, w, color=STRATEGY_COLORS.get(s, "#3b82f6"), label=LABELS[s])
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width()/2, v + 6, f"{v:.0f}", ha="center", va="bottom", fontsize=8)

# Δ best-vs-baseline per layout
for j, (layout, _) in enumerate(LAYOUTS):
    base = fq(layout, "baseline")
    best = min(fq(layout, s) for s in STRATS if s != "baseline")
    pct = (best - base) / base * 100
    ax.annotate(f"Δ {pct:+.0f}%", xy=(j, best), xytext=(j + 0.05, base + 60),
                fontsize=10, color="#1d4ed8", fontweight="bold",
                arrowprops=dict(arrowstyle="->", color="#1d4ed8", lw=0.8))

ax.set_xticks(x, [n for _, n in LAYOUTS])
ax.set_ylabel("first-query latency (µs, async, median of 10 reps)")
ax.set_title("Layout × prefetch strategy · Workload A · cold start (P0)")
ax.legend(loc="upper center", ncol=4, bbox_to_anchor=(0.5, -0.12))
ax.set_ylim(0, max(allvals) * 1.20)
fig.tight_layout()
save(fig, "02_layout_effect")
