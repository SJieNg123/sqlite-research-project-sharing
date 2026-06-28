"""Figure 15: DB-size sensitivity of the cross-seed effect (orig 100MB vs 1gb), 95% CI.

Story (§6.2.5): re-run the 10-seed workload-instantiation sweep at 1 GiB and compare
the per-strategy effect (vs same-seed baseline) against the 100 MB orig sweep. Because
the effect is a same-seed relative delta, machine-state drift cancels — so the two
sizes are directly comparable. Rows = metric, cols = workload; each point is the
cross-seed mean effect with its bootstrap 95% CI (filled = robust / CI excludes 0,
hollow = tie/directional). A point whose CI straddles the dashed 0-line is not robust.

Top row (first-query): every cell is negative & robust at both sizes -> the cold-start
benefit is size-robust. Bottom row (warm-process e2e): the size sensitivity is
concentrated in narrow workload C, where 2f_slru / 2e_K500 / layers_92 flip win->loss
as the working set scales with the DB.

Data: orig = results/stats/uncertainty.csv (db=orig); 1gb = results/stats/
uncertainty_1gb.csv. async arm. Both are 10-seed (A/B/C) sweeps.
"""
import csv
from plot_utils import ROOT, save
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ORIG_CSV = ROOT / "results/stats/uncertainty.csv"
GB_CSV   = ROOT / "results/stats/uncertainty_1gb.csv"

WORKLOADS = ["A", "B", "C"]
STRATS    = ["layers_5", "layers_92", "2d", "2e_K10", "2e_K500", "2f_slru"]
METRICS   = [("first_query_us", "First-query latency"),
             ("e2e_warm_us",    "Warm-process e2e")]
COL = {"orig": "#1f77b4", "1gb": "#d62728"}   # 100MB vs 1 GiB
LBL = {"orig": "orig (100 MB)", "1gb": "1gb (~1 GiB)"}


def load(path, db):
    out = {}
    for r in csv.DictReader(open(path)):
        if r["db"] == db and r["arm"] == "async":
            out[(r["workload"], r["strategy"], r["metric"])] = r
    return out


data = {"orig": load(ORIG_CSV, "orig"), "1gb": load(GB_CSV, "1gb")}

fig, axes = plt.subplots(2, 3, figsize=(13.5, 7.4), sharex=True)
DODGE = {"orig": -0.16, "1gb": 0.16}
# bottom row (e2e) is clipped so the readable flips aren't crushed by 2f's +700~930%
YLIM = {"first_query_us": (-95, 18), "e2e_warm_us": (-95, 165)}

for ri, (metric, mlabel) in enumerate(METRICS):
    lo, hi = YLIM[metric]
    for ci, w in enumerate(WORKLOADS):
        ax = axes[ri][ci]
        ax.axhline(0, color="#444", lw=1, ls="--", zorder=1)
        for db in ("orig", "1gb"):
            for si, s in enumerate(STRATS):
                r = data[db].get((w, s, metric))
                if not r:
                    continue
                mean = float(r["mean_pct"])
                clo, chi = float(r["ci_lo"]), float(r["ci_hi"])
                robust = r["verdict"] == "robust"
                x = si + DODGE[db]
                # off-scale point (e.g. 2f e2e on A/B): draw an up-arrow + value at top
                if mean > hi:
                    ax.annotate("", xy=(x, hi - 4), xytext=(x, hi - 22),
                                arrowprops=dict(arrowstyle="-|>", color=COL[db], lw=1.8))
                    ax.text(x, hi - 26, f"+{mean:.0f}%", color=COL[db], fontsize=7.2,
                            ha="center", va="top", rotation=90)
                    continue
                yerr = [[max(mean - clo, 0)], [max(chi - mean, 0)]]
                ax.errorbar(x, mean, yerr=yerr, fmt="o" if db == "orig" else "s",
                            ms=6, mfc=COL[db] if robust else "white",
                            mec=COL[db], color=COL[db], lw=1.6, capsize=3, zorder=3)
        ax.set_xticks(range(len(STRATS)))
        ax.set_xticklabels(STRATS, rotation=35, ha="right", fontsize=8.5)
        ax.set_ylim(lo, hi)
        if ri == 0:
            ax.set_title(f"Workload {w}", fontsize=12)
        if ci == 0:
            ax.set_ylabel(f"{mlabel}\nΔ% vs same-seed baseline", fontsize=9.5)

# legend: size + verdict encoding
handles = [
    Line2D([0], [0], marker="o", color=COL["orig"], lw=0, mfc=COL["orig"], mec=COL["orig"], ms=7, label=LBL["orig"]),
    Line2D([0], [0], marker="s", color=COL["1gb"], lw=0, mfc=COL["1gb"], mec=COL["1gb"], ms=7, label=LBL["1gb"]),
    Line2D([0], [0], marker="o", color="#555", lw=0, mfc="#555", mec="#555", ms=7, label="filled = robust (95% CI excludes 0)"),
    Line2D([0], [0], marker="o", color="#555", lw=0, mfc="white", mec="#555", ms=7, label="hollow = tie / directional"),
]
fig.legend(handles=handles, loc="lower center", ncol=4, bbox_to_anchor=(0.5, -0.02), fontsize=9)
fig.suptitle("DB-size sensitivity of the cross-seed effect (10 seeds each): 100 MB vs ~1 GiB, bootstrap 95% CI",
             fontsize=13, y=0.99)
fig.tight_layout(rect=[0, 0.04, 1, 0.97])
save(fig, "15_size_scaling_ci")
