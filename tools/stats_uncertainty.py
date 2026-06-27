#!/usr/bin/env python3
"""R3 workload-sensitivity uncertainty analysis (pure python, no numpy/scipy).

Pools per-seed raw.csv files and, for every
(workload, layout, strategy, arm, metric), characterises the cross-seed
distribution of the *effect* (strategy vs the SAME-seed baseline):

  per-seed effect %   = (median_strategy - median_baseline) / median_baseline * 100
  across seeds        -> mean, median, bootstrap 95% CI of the mean,
                         min/max, sign-consistency (#same-sign / n)
  verdict             robust      : 95% CI excludes 0  (effect survives across seeds)
                      directional : CI crosses 0 but >= 70% of seeds agree in sign
                      tie         : otherwise (within workload-instantiation noise)

Comparing each strategy to the baseline measured in the SAME seed/batch controls
machine drift; the spread that remains across seeds is genuine workload sensitivity.

Inputs default to results/seeds/seed*/raw.csv (+ results/main as an extra sample
with --include-main). Metrics: first_query_us, e2e_warm_us, e2e_us.

Usage:
  tools/stats_uncertainty.py                       # all seed dirs found
  tools/stats_uncertainty.py --include-main        # also fold in results/main
  tools/stats_uncertainty.py --seeds results/seeds/seed01 results/main --headline
"""
import argparse
import csv
import random
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path("/home/u03/sqlite-research-project-sharing")
METRICS = ["first_query_us", "e2e_warm_us", "e2e_us"]
COLD_MAX = 1.0          # drop reps whose cold check exceeds this % (matches run_experiment)
BOOT_N = 10000
BOOT_SEED = 42
MIN_ROBUST_N = 5        # below this, a bootstrap CI is degenerate -> don't claim robust/tie

# headline cells the report tables actually quote (async arm)
HEADLINE_STRATS = ["layers_5", "layers_92", "2d", "2e_K10", "2e_K500", "2f_slru"]


# ------------------------------------------------------------------ load / aggregate
def load_seed(raw_path):
    """(workload,db,strategy,arm) -> {metric: [values]} from kept reps only."""
    cells = defaultdict(lambda: defaultdict(list))
    with open(raw_path, newline="") as f:
        for r in csv.DictReader(f):
            if r.get("warmup") == "1":
                continue
            try:
                if float(r.get("cold_pct") or 0) > COLD_MAX:
                    continue
            except ValueError:
                pass
            key = (r["workload"], r["db"], r["strategy"], r["arm"])
            for m in METRICS:
                v = r.get(m)
                if v not in (None, ""):
                    try:
                        cells[key][m].append(float(v))
                    except ValueError:
                        pass
    return cells


def seed_medians(cells):
    """(workload,db,strategy,arm) -> {metric: median over kept reps}."""
    return {key: {m: statistics.median(vs) for m, vs in md.items() if vs}
            for key, md in cells.items()}


def baseline_value(medians, w, ly, metric):
    return medians.get((w, ly, "baseline", "baseline"), {}).get(metric)


# --------------------------------------------------------------------- statistics
def bootstrap_ci(values, n=BOOT_N, alpha=0.05):
    """Deterministic percentile bootstrap CI of the mean. None if n<2."""
    k = len(values)
    if k < 2:
        return (None, None)
    rng = random.Random(BOOT_SEED)
    means = sorted(sum(values[rng.randrange(k)] for _ in range(k)) / k
                   for _ in range(n))
    return (means[int((alpha / 2) * n)], means[int((1 - alpha / 2) * n)])


def verdict(lo, hi, sign_frac, n):
    if lo is None or n < MIN_ROBUST_N:
        return f"n<{MIN_ROBUST_N}"      # too few seeds for a trustworthy CI
    if (lo > 0 and hi > 0) or (lo < 0 and hi < 0):
        return "robust"
    return "directional" if sign_frac >= 0.7 else "tie"


# ------------------------------------------------------------------------ analyze
def analyze(seed_files, metrics):
    per_seed = {label: seed_medians(load_seed(p)) for label, p in seed_files}
    comps = defaultdict(dict)   # (w,ly,strat,arm,metric) -> {label: effect%}
    for label, med in per_seed.items():
        for (w, ly, strat, arm), mm in med.items():
            if strat == "baseline":
                continue
            for m in metrics:
                sv, bv = mm.get(m), baseline_value(med, w, ly, m)
                if sv is None or bv in (None, 0):
                    continue
                comps[(w, ly, strat, arm, m)][label] = (sv - bv) / bv * 100.0

    rows = []
    for (w, ly, strat, arm, m), effs in sorted(comps.items()):
        vals = list(effs.values())
        n = len(vals)
        mean = statistics.mean(vals)
        lo, hi = bootstrap_ci(vals)
        npos = sum(1 for v in vals if v > 0)
        nneg = sum(1 for v in vals if v < 0)
        sign_frac = max(npos, nneg) / n if n else 0.0
        rows.append({
            "workload": w, "db": ly, "strategy": strat, "arm": arm, "metric": m,
            "n_seeds": n,
            "mean_pct": round(mean, 2),
            "median_pct": round(statistics.median(vals), 2),
            "ci_lo": None if lo is None else round(lo, 2),
            "ci_hi": None if hi is None else round(hi, 2),
            "min_pct": round(min(vals), 2),
            "max_pct": round(max(vals), 2),
            "sign_consistency": f"{max(npos, nneg)}/{n}",
            "verdict": verdict(lo, hi, sign_frac, n),
            "per_seed": ";".join(f"{lab}={effs[lab]:.1f}" for lab in sorted(effs)),
        })
    return rows, per_seed


# -------------------------------------------------------------------------- output
def write_csv(rows, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = ["workload", "db", "strategy", "arm", "metric", "n_seeds", "mean_pct",
            "median_pct", "ci_lo", "ci_hi", "min_pct", "max_pct",
            "sign_consistency", "verdict", "per_seed"]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


def _fmt_ci(r):
    if r["ci_lo"] is None:
        return "—"
    return f"[{r['ci_lo']:+.1f}, {r['ci_hi']:+.1f}]"


def headline_md(rows, metric, arm="async", layout="orig"):
    """Markdown table of the headline cells for one metric/arm/layout."""
    idx = {(r["workload"], r["strategy"]): r for r in rows
           if r["metric"] == metric and r["arm"] == arm and r["db"] == layout}
    out = [f"### {metric} — {arm} arm, layout {layout}",
           "",
           "| workload | strategy | mean Δ% | 95% CI | sign | verdict |",
           "|---|---|---:|---|---:|---|"]
    for w in ["A", "B", "C"]:
        for s in HEADLINE_STRATS:
            r = idx.get((w, s))
            if not r:
                continue
            out.append(f"| {w} | {s} | {r['mean_pct']:+.1f} | {_fmt_ci(r)} | "
                       f"{r['sign_consistency']} | {r['verdict']} |")
    out.append("")
    return "\n".join(out)


def discover_seed_files(args):
    files = []
    if args.seeds:
        for s in args.seeds:
            p = Path(s)
            raw = p / "raw.csv" if p.is_dir() else p
            files.append((p.name if p.is_dir() else p.stem, raw))
    else:
        for d in sorted((ROOT / "results/seeds").glob("seed*")):
            raw = d / "raw.csv"
            if raw.exists():
                files.append((d.name.replace("seed", ""), raw))
        if args.include_main:
            files.append(("main", ROOT / "results/main/raw.csv"))
    return [(lab, p) for lab, p in files if Path(p).exists()]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", nargs="*", help="explicit seed dirs or raw.csv paths")
    ap.add_argument("--include-main", action="store_true",
                    help="also fold results/main in as an extra sample")
    ap.add_argument("--out", default=str(ROOT / "results/stats/uncertainty.csv"))
    ap.add_argument("--md", default=str(ROOT / "results/stats/uncertainty.md"))
    ap.add_argument("--headline", action="store_true",
                    help="print the headline tables to stdout")
    args = ap.parse_args()

    seed_files = discover_seed_files(args)
    if not seed_files:
        raise SystemExit("no seed raw.csv files found (run the sweep first)")
    print(f"seeds pooled ({len(seed_files)}): {', '.join(lab for lab, _ in seed_files)}")

    rows, _ = analyze(seed_files, METRICS)
    write_csv(rows, Path(args.out))

    md_parts = [f"# R3 workload-sensitivity uncertainty",
                f"\nPooled seeds: {', '.join(lab for lab, _ in seed_files)} "
                f"(n={len(seed_files)}). Bootstrap 95% CI of the mean per-seed effect; "
                f"effect = strategy vs same-seed baseline.\n"]
    for metric in ["e2e_warm_us", "first_query_us", "e2e_us"]:
        md_parts.append(headline_md(rows, metric))
    Path(args.md).write_text("\n".join(md_parts) + "\n")
    print(f"wrote {args.out}\nwrote {args.md}")

    if args.headline:
        for metric in ["e2e_warm_us", "first_query_us"]:
            print("\n" + headline_md(rows, metric))


if __name__ == "__main__":
    main()
