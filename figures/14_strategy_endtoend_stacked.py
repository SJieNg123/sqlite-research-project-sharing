"""Figure 14: End-to-end cold start (preprocessing + first-q) — KILLER figure.

Story: counter to figure 13's headline. Once preprocessing (the warmer's wall-clock,
preproc_us = warmer_us) is added, 2f SLRU's first-query win collapses: its ~5.7-7.5 ms
preproc dwarfs the ~100 µs first-query and pushes end-to-end OVER the baseline. The
cheap structural picks (layers_5 / 2e_K10) keep e2e well under baseline.

Stacked bar (first-q bottom + preproc top); baseline = horizontal dashed reference.

Data (P0 master batch, authoritative): p0_runs/summary_p0.csv, async arm, layout=orig,
median of 10 reps. fq=fq_median, preproc=preproc_us_median (e2e=e2e_median).
"""
from plot_utils import ROOT, save, load_p0, P0_STRATS, P0_LABELS, STRATEGY_COLORS
import matplotlib.pyplot as plt
import numpy as np

P0 = load_p0("async")
STRATEGIES = P0_STRATS
WORKLOADS = ['A', 'B', 'C']
WL_TITLE = {'A': 'Workload A (Zipfian)', 'B': 'Workload B (uniform)',
            'C': 'Workload C (churn-heavy)'}

fig, axes = plt.subplots(1, 3, figsize=(13, 5.0), sharey=False)
x = np.arange(len(STRATEGIES))

for ax, wl in zip(axes, WORKLOADS):
    fqs = [float(P0[(wl, 'orig', s)]['fq_median']) for s in STRATEGIES]
    pfs = [float(P0[(wl, 'orig', s)]['preproc_us_median'] or 0) for s in STRATEGIES]
    e2es = [f + p for f, p in zip(fqs, pfs)]
    baseline = e2es[0]  # baseline has preproc=0 -> e2e = first-q
    colors = [STRATEGY_COLORS.get(s, "#3b82f6") for s in STRATEGIES]
    ax.bar(x, fqs, color=colors, alpha=0.9, edgecolor='black', linewidth=0.5,
           label='first-q (SQL latency)')
    ax.bar(x, pfs, bottom=fqs, color='#fbbf24', alpha=0.95, edgecolor='black',
           linewidth=0.5, hatch='///', label='preprocessing (warmer)')
    ax.axhline(baseline, color='#dc2626', ls='--', lw=1.4, alpha=0.8, zorder=3,
               label=f'baseline cold start ({baseline:.0f} µs)')
    for xi, e2e, fq, pp in zip(x, e2es, fqs, pfs):
        if pp > fq * 2:  # 2f SLRU (and big-preproc cells): annotate the trap
            ax.text(xi, e2e * 1.04, f'{e2e:.0f} µs\n⚠ {e2e/baseline:.1f}× base',
                    ha='center', va='bottom', fontsize=7.5, color='#dc2626', fontweight='bold')
        else:
            improve = (e2e - baseline) / baseline * 100
            sign = '+' if improve >= 0 else ''
            ax.text(xi, e2e * 1.05, f'{e2e:.0f} ({sign}{improve:.0f}%)',
                    ha='center', va='bottom', fontsize=7.5,
                    color='#dc2626' if improve > 0 else 'black')
    ax.set_xticks(x)
    ax.set_xticklabels([P0_LABELS[s] for s in STRATEGIES], fontsize=9, rotation=25, ha='right')
    ax.set_title(WL_TITLE[wl], fontsize=11)
    ax.set_yscale('log')
    ax.set_ylim(80, max(e2es) * 3.5)
    ax.grid(axis='y', alpha=0.25, which='both')
    ax.set_axisbelow(True)
    if wl == 'A':
        ax.legend(loc='upper left', fontsize=7.5, framealpha=0.92)

axes[0].set_ylabel('end-to-end cold start (µs, log scale)', fontsize=10)
fig.suptitle('End-to-end cold start: preprocessing + first-q vs baseline (P0). '
             'Compare Figure 13 — 2f SLRU\'s first-query win collapses on e2e.',
             fontsize=11, y=1.0)
fig.tight_layout()
save(fig, '14_strategy_endtoend_stacked')
