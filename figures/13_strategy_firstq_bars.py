"""Figure 13: Pure first-query bar chart — strategy comparison per workload.

Story: the "deceptive" view. Showing only first-query latency (the SQL latency,
NOT counting prefetch preprocessing), 2f SLRU looks dominant. Pair with figure 14,
which adds preprocessing cost and exposes 2f SLRU's end-to-end collapse.

Data (P0 master batch, authoritative): p0_runs/summary_p0.csv, async arm, layout=orig,
median of 10 reps (warmup dropped). Strategies: baseline + 6 P0 strategies.
"""
from plot_utils import ROOT, save, load_p0, P0_STRATS, P0_LABELS, STRATEGY_COLORS
import matplotlib.pyplot as plt
import numpy as np

P0 = load_p0("async")
STRATEGIES = P0_STRATS
LABELS = [P0_LABELS[s] for s in STRATEGIES]
COLORS = [STRATEGY_COLORS.get(s, "#3b82f6") for s in STRATEGIES]
WORKLOADS = ['A', 'B', 'C']
WL_TITLE = {'A': 'Workload A (Zipfian)', 'B': 'Workload B (uniform)',
            'C': 'Workload C (churn-heavy)'}

fig, axes = plt.subplots(1, 3, figsize=(13, 4.6), sharey=False)
x = np.arange(len(STRATEGIES))

for ax, wl in zip(axes, WORKLOADS):
    medians = [float(P0[(wl, 'orig', s)]['fq_median']) for s in STRATEGIES]
    bars = ax.bar(x, medians, color=COLORS, alpha=0.9, edgecolor='black', linewidth=0.5)
    baseline = medians[0]
    ax.axhline(baseline, color='#9ca3af', ls='--', lw=1.0, alpha=0.6, zorder=0)
    for xi, val in zip(x, medians):
        ax.text(xi, val * 1.06, f'{val:.0f}', ha='center', va='bottom', fontsize=8, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(LABELS, fontsize=9, rotation=25, ha='right')
    ax.set_title(WL_TITLE[wl], fontsize=11)
    ax.set_yscale('log')
    ax.set_ylim(80, max(medians) * 2.5)
    ax.grid(axis='y', alpha=0.25, which='both')
    ax.set_axisbelow(True)

axes[0].set_ylabel('first-query latency (µs, log scale)', fontsize=10)
fig.suptitle('First-query latency by strategy — async arm, layout=orig (P0; preprocessing NOT included)',
             fontsize=12, y=1.0)
fig.tight_layout()
save(fig, '13_strategy_firstq_bars')
