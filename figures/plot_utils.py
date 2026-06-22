"""Shared style + paths for all W14 publication figures.

Run any figure with:  python3 figures/0X_<name>.py
Output PNGs land in  figures/out/  at 150 dpi.
"""
import os
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
OUT  = Path(__file__).resolve().parent / "out"
OUT.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "figure.dpi": 110,
    "savefig.dpi": 150,
    "savefig.bbox": "tight",
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "axes.titlesize": 12,
    "axes.labelsize": 10,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.linestyle": ":",
    "grid.alpha": 0.4,
    "legend.frameon": False,
    "legend.fontsize": 9,
})

WORKLOAD_COLORS = {
    "A": "#1f77b4",
    "B": "#2ca02c",
    "C": "#d62728",
    "Z": "#9467bd",
}
LAYOUT_COLORS = {
    "1a": "#888888",
    "orig": "#888888",
    "1b": "#1f77b4",
    "vacuum": "#1f77b4",
    "1c": "#d62728",
    "ta": "#d62728",
}
STRATEGY_COLORS = {
    "base":      "#9ca3af",
    "baseline":  "#9ca3af",
    "range":     "#94a3b8",
    "perpage":   "#cbd5e1",
    "layers_5":  "#3b82f6",
    "layers_46": "#1d4ed8",
    "layers_92": "#1e3a8a",
    "2d":        "#10b981",
    "2e_K10":    "#059669",
    "2e_K50":    "#047857",
    "2e_K100":   "#065f46",
    "2e_K500":   "#064e3b",
    "2f_SLRU":   "#f59e0b",
    "2f_slru":   "#f59e0b",
}

# --- P0 master batch (authoritative) -----------------------------------------
P0_SUMMARY = ROOT / "p0_runs/summary_p0.csv"
# canonical strategy order for P0 figures (baseline first = the improvement-% denominator)
P0_STRATS  = ["baseline", "layers_5", "layers_92", "2d", "2e_K10", "2e_K500", "2f_slru"]
P0_LABELS  = {"baseline": "baseline", "layers_5": "layers_5", "layers_92": "layers_92",
              "2d": "2d", "2e_K10": "2e_K10", "2e_K500": "2e_K500", "2f_slru": "2f SLRU"}

def load_p0(arm="async"):
    """Return {(workload, db, strategy): row} from summary_p0.csv for one arm.
    baseline rows are stored under arm 'baseline' but exposed for every requested arm."""
    import csv
    out = {}
    for r in csv.DictReader(open(P0_SUMMARY)):
        if r["arm"] == arm or r["strategy"] == "baseline":
            out[(r["workload"], r["db"], r["strategy"])] = r
    return out

def save(fig, name):
    p = OUT / f"{name}.png"
    fig.savefig(p)
    plt.close(fig)
    print(f"  wrote {p.relative_to(ROOT)}")
    return p
