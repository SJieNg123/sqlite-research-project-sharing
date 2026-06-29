"""Figure 16: sub-working-set RAM-pressure sweep (review item R3 W3).

Steps the cgroup memory cap BELOW the ~17.3 MB resident working set (A/B) and shows, per
strategy, how much of the prefetched hotset stays resident to first-query (delivery_pct =
mincore residual) and what that does to first-q. Story:
  - 2e_K10 (112 KB hotset) and 2e_K500 (2 MB) stay 100% delivered and flat -> RAM-robust.
  - 2f_slru (17.7 MB dump = whole WS) cannot fit < ~16M: delivery collapses, first-q climbs
    from its 94 us floor back toward baseline -> the cache-dump strategy breaks under pressure.

Data: results/ram_pressure/cap_<tag>/summary.csv (async arm + baseline), seed 1, layout orig.
"""
import csv, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from plot_utils import save, STRATEGY_COLORS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SWEEP = os.path.join(ROOT, "results/ram_pressure")
WS_MB = 17.3                                  # A/B resident working set
# cap tag -> (MB for ×WS label, x position). unlimited drawn at the left as the control.
CAPS = [("unlimited", None), ("16M", 16), ("12M", 12), ("8M", 8), ("6M", 6)]
STRATS = ["2e_K10", "2e_K500", "2f_slru"]
WORKLOADS = ["A", "B"]
WL_TITLE = {"A": "Workload A (Zipfian)", "B": "Workload B (uniform)"}


def load(tag):
    out = {}
    p = os.path.join(SWEEP, f"cap_{tag}", "summary.csv")
    with open(p) as f:
        for r in csv.DictReader(f):
            out[(r["workload"], r["strategy"], r["arm"])] = r
    return out


DATA = {tag: load(tag) for tag, _ in CAPS}
xpos = list(range(len(CAPS)))
xlabels = ["∞\n(unlim)"] + [f"{mb}M\n{mb/WS_MB:.2f}×WS" for _, mb in CAPS[1:]]

fig, axes = plt.subplots(2, 2, figsize=(11, 8.2), sharex=True)
for col, wl in enumerate(WORKLOADS):
    ax_d, ax_f = axes[0][col], axes[1][col]
    base_fq = [float(DATA[t].get((wl, "baseline", "baseline"), {}).get("fq_median", "nan"))
               for t, _ in CAPS]
    for s in STRATS:
        col_s = STRATEGY_COLORS.get(s, "#333")
        dpct = [float(DATA[t].get((wl, s, "async"), {}).get("delivery_pct_median", "nan"))
                if (wl, s, "async") in DATA[t] else float("nan") for t, _ in CAPS]
        fq = [float(DATA[t].get((wl, s, "async"), {}).get("fq_median", "nan"))
              if (wl, s, "async") in DATA[t] else float("nan") for t, _ in CAPS]
        ax_d.plot(xpos, dpct, "o-", color=col_s, lw=2, ms=6, label=s)
        ax_f.plot(xpos, fq, "o-", color=col_s, lw=2, ms=6, label=s)
    ax_f.plot(xpos, base_fq, "--", color="#dc2626", lw=1.5, label="baseline (no prefetch)")
    ax_d.axvline(0.5, color="#9ca3af", ls=":", lw=1)   # mark "cap < WS" region start
    ax_d.set_title(WL_TITLE[wl], fontsize=11)
    ax_d.set_ylim(0, 108); ax_d.grid(alpha=0.3)
    ax_f.set_yscale("log"); ax_f.grid(alpha=0.3, which="both")
    ax_f.axvline(0.5, color="#9ca3af", ls=":", lw=1)
    if col == 0:
        ax_d.set_ylabel("hotset delivery_pct\n(mincore residual @ first-q)", fontsize=9.5)
        ax_f.set_ylabel("first-query latency (µs, log)", fontsize=9.5)
    ax_d.legend(fontsize=8, loc="lower right", framealpha=0.9)
    ax_f.set_xticks(xpos); ax_f.set_xticklabels(xlabels, fontsize=8.5)

fig.suptitle(f"Sub-working-set RAM pressure (cgroup cap, layout orig; working set ≈ {WS_MB:.0f} MB): "
             "2e_K10/2e_K500 stay 100% delivered & flat (tiny hotset, never evicted); "
             "2f_slru (17.7 MB dump) collapses as cap drops below WS.",
             fontsize=9.5, y=0.99)
fig.text(0.5, 0.005, "Cap stepped from ∞ down past the working set. 4M omitted: cold gate "
         "excludes all cells (below the measurable floor).", ha="center", fontsize=8, color="#6b7280")
fig.tight_layout(rect=[0, 0.02, 1, 0.97])
save(fig, "16_ram_pressure_sweep")
