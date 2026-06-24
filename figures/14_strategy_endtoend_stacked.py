"""Figure 14: End-to-end cold start under TWO deployment models (P0).

Stacked bar per strategy: first-q (bottom) + deliver (prefetch syscalls) + cold open(db).
  - warm-process / integrated e2e = first-q + deliver        (handle already open; ~ static
                                                               effective_first_query) = bar MINUS grey
  - standalone-warmer e2e         = first-q + deliver + open  (re-opens the cold DB) = full bar top
The grey top segment is exactly the cold open(db) you save by integrating prefetch into the
already-running app. 2f's deliver alone dwarfs first-q, so it loses under BOTH models; the cheap
structural picks (layers_5 / 2e_K10) drop UNDER baseline once the cold open is removed — even on
fast Workload A, where the standalone model had them losing.

Data (P0 master batch): p0_runs/summary_p0.csv, async arm, layout=orig, medians.
fq=fq_median, deliver=deliver_us_median, open=open_us_median.
"""
from plot_utils import save, load_p0, P0_STRATS, P0_LABELS, STRATEGY_COLORS
import matplotlib.pyplot as plt
import numpy as np

P0 = load_p0("async")
STRATEGIES = P0_STRATS
WORKLOADS = ['A', 'B', 'C']
WL_TITLE = {'A': 'Workload A (Zipfian)', 'B': 'Workload B (uniform)',
            'C': 'Workload C (churn-heavy)'}

fig, axes = plt.subplots(1, 3, figsize=(13.5, 5.4), sharey=False)
x = np.arange(len(STRATEGIES))

for ax, wl in zip(axes, WORKLOADS):
    row = lambda s: P0[(wl, 'orig', s)]
    fqs   = [float(row(s)['fq_median']) for s in STRATEGIES]
    dels  = [float(row(s).get('deliver_us_median') or 0) for s in STRATEGIES]
    opens = [float(row(s).get('open_us_median') or 0) for s in STRATEGIES]
    warm       = [f + d for f, d in zip(fqs, dels)]            # warm-process / integrated e2e
    standalone = [w + o for w, o in zip(warm, opens)]          # standalone-warmer e2e
    baseline = fqs[0]                                          # baseline: deliver=open=0
    colors = [STRATEGY_COLORS.get(s, "#3b82f6") for s in STRATEGIES]

    ax.bar(x, fqs, color=colors, alpha=0.9, edgecolor='black', linewidth=0.5,
           label='first-q (SQL latency)')
    ax.bar(x, dels, bottom=fqs, color='#fbbf24', alpha=0.95, edgecolor='black',
           linewidth=0.5, hatch='///', label='deliver (prefetch syscalls)')
    ax.bar(x, opens, bottom=warm, color='#d1d5db', alpha=0.95, edgecolor='black',
           linewidth=0.5, hatch='xx', label='cold open(db) — saved if integrated')
    ax.axhline(baseline, color='#dc2626', ls='--', lw=1.4, alpha=0.85, zorder=4,
               label=f'baseline ({baseline:.0f} µs)')

    for xi, wv, sv in zip(x, warm, standalone):
        wi = (wv - baseline) / baseline * 100          # warm-process e2e vs baseline (headline)
        wsign = '+' if wi >= 0 else ''
        ax.text(xi, sv * 1.06, f'{wsign}{wi:.0f}%', ha='center', va='bottom',
                fontsize=8.5, fontweight='bold',
                color=('#15803d' if wi < 0 else '#dc2626'))

    ax.set_xticks(x)
    ax.set_xticklabels([P0_LABELS[s] for s in STRATEGIES], fontsize=9, rotation=25, ha='right')
    ax.set_title(WL_TITLE[wl], fontsize=11)
    ax.set_yscale('log')
    ax.set_ylim(80, max(standalone) * 4.0)
    ax.grid(axis='y', alpha=0.25, which='both')
    ax.set_axisbelow(True)
    if wl == 'A':
        ax.legend(loc='upper left', fontsize=7.2, framealpha=0.92)

axes[0].set_ylabel('end-to-end cold start (µs, log scale)', fontsize=10)
fig.suptitle('End-to-end cold start, two models (P0, layout orig): '
             'warm-process e2e = first-q+deliver (bar minus grey) · standalone = full bar. '
             'Grey = cold open(db) saved by integrating prefetch.',
             fontsize=10, y=1.0)
fig.tight_layout()
save(fig, '14_strategy_endtoend_stacked')
