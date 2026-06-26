#!/usr/bin/env python3
"""Prefetch-time calibration sweep.

Each prefetch tool (prefetch_layers / prefetch_access / prefetch_slru) prints
`time_us=X.XX` to stderr at the end of its run. Benchmark_harness does NOT
capture this — every result CSV in the project that reports first_query_us is
missing the preprocessing-time accounting. This script runs each (tool, db,
strategy_params) combination 3 times standalone, parses stderr, and emits a
single calibration CSV that downstream readers can join into result tables.

Output: calibration/prefetch_time_calibration.csv
  schema: tool,db_layout,workload,strategy,N_or_K,rep,prefetch_time_us,n_prefetch,n_syscalls
"""
import csv, re, subprocess, sys
from pathlib import Path

ROOT = Path("/home/u03/sqlite-research-project-sharing")
PL = ROOT / "prefetch_vacuum/src/prefetch_layers"
PA = ROOT / "prefetch_access/src/prefetch_access"
PS = ROOT / "prefetch_slru/src/prefetch_slru"

DBS = {
    "orig":   ROOT / "layout_rewriter/runs/test.db",
    "vacuum": ROOT / "layout_rewriter/runs/test_vacuum.db",
    "ta":     ROOT / "layout_rewriter/runs/test_typeaware.db",
}
CLASSIFY = {
    "orig":   ROOT / "layout_rewriter/runs/classify_before.csv",
    "vacuum": ROOT / "layout_rewriter/runs/classify_vacuum.csv",
    "ta":     ROOT / "layout_rewriter/runs/classify_after.csv",
}
HOTPAGES_BASE = {  # for 2d: hotpages_{a,b,c}{,_vacuum,_ta}.csv
    ("A", "orig"):   ROOT / "prefetch_access/runs/hotpages_a.csv",
    ("A", "vacuum"): ROOT / "prefetch_access/runs/hotpages_a_vacuum.csv",
    ("A", "ta"):     ROOT / "prefetch_access/runs/hotpages_a_ta.csv",
    ("B", "orig"):   ROOT / "prefetch_access/runs/hotpages_b.csv",
    ("B", "vacuum"): ROOT / "prefetch_access/runs/hotpages_b_vacuum.csv",
    ("B", "ta"):     ROOT / "prefetch_access/runs/hotpages_b_ta.csv",
    ("C", "orig"):   ROOT / "prefetch_access/runs/hotpages_c.csv",
    ("C", "vacuum"): ROOT / "prefetch_access/runs/hotpages_c_vacuum.csv",
    ("C", "ta"):     ROOT / "prefetch_access/runs/hotpages_c_ta.csv",
}

REPS = 3
# Each tool prints a different stderr line:
#   prefetch_layers / prefetch_slru:  "n_prefetch=N syscalls=N time_us=X"
#   prefetch_access:                  "n_interior=I n_leaf=L syscalls=S resident_interior_total=... resident_leaf_total=... time_us=X"
RE_TIME = re.compile(r"time_us=([\d.]+)")
RE_NPREF = re.compile(r"n_prefetch=(\d+)")
RE_NSYS = re.compile(r"syscalls=(\d+)")
RE_NINT = re.compile(r"n_interior=(\d+)")
RE_NLEAF = re.compile(r"n_leaf=(\d+)")

def run_and_parse(argv):
    """Run a prefetch tool, parse its stderr, return (time_us, n_prefetch, n_syscalls).
    n_prefetch = total pages prefetched (sum of interior+leaf for prefetch_access).
    Returns (None, 0, 0) on failure."""
    try:
        r = subprocess.run([str(a) for a in argv], capture_output=True, text=True, timeout=30)
        out = r.stderr + "\n" + r.stdout  # search both
        m_t = RE_TIME.search(out)
        if not m_t:
            return (None, 0, 0)
        t = float(m_t.group(1))
        m_n = RE_NPREF.search(out)
        if m_n:
            nph = int(m_n.group(1))
        else:
            # prefetch_access path: n_prefetch = n_interior + n_leaf
            ni = RE_NINT.search(out)
            nl = RE_NLEAF.search(out)
            nph = (int(ni.group(1)) if ni else 0) + (int(nl.group(1)) if nl else 0)
        m_s = RE_NSYS.search(out)
        sysc = int(m_s.group(1)) if m_s else nph
        return (t, nph, sysc)
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"  ERROR: {e}", file=sys.stderr)
        return (None, 0, 0)

def emit(out, row):
    out.writerow(row)

outdir = ROOT / "calibration"
outdir.mkdir(exist_ok=True)
outpath = outdir / "prefetch_time_calibration.csv"

with outpath.open("w", newline="") as f:
    out = csv.writer(f)
    out.writerow(["tool", "db_layout", "workload", "strategy", "N_or_K",
                  "rep", "prefetch_time_us", "n_prefetch", "n_syscalls"])

    # ============================================================
    # 1) prefetch_layers (2c) — layout × N=0..92 × 3 reps
    # ============================================================
    print(f"[1/3] prefetch_layers: 3 layouts × 93 N × {REPS} reps = {3*93*REPS} runs", file=sys.stderr)
    for layout in ["orig", "vacuum", "ta"]:
        db = DBS[layout]
        cl = CLASSIFY[layout]
        for N in range(0, 93):
            for rep in range(1, REPS + 1):
                if N == 0:
                    # N=0 = baseline, no prefetch tool runs; record 0 µs
                    emit(out, ["prefetch_layers", layout, "ALL", "layers_0", 0,
                               rep, 0.0, 0, 0])
                    continue
                t, nph, sysc = run_and_parse([PL, db, cl, N, 4096])
                emit(out, ["prefetch_layers", layout, "ALL", f"layers_{N}", N,
                           rep, t if t is not None else "",
                           nph, sysc])
        print(f"  layout={layout} done", file=sys.stderr)

    # ============================================================
    # 2) prefetch_access (2d / 2e_K) — 3 layouts × 3 workloads × {2d, 2e_K10..K500} × 3 reps
    # ============================================================
    K_VALUES = [10, 40, 50, 92, 100, 500]
    print(f"[2/3] prefetch_access: 9 (wl,layout) × (1+6) strategies × {REPS} reps", file=sys.stderr)
    for w in ["A", "B", "C"]:
        for layout in ["orig", "vacuum", "ta"]:
            db = DBS[layout]
            cl = CLASSIFY[layout]
            # 2d mode: use hotpages_base, n_interior=0 (no cap), n_leaf=0 (skip leaves)
            base_hot = HOTPAGES_BASE[(w, layout)]
            for rep in range(1, REPS + 1):
                t, nph, sysc = run_and_parse([PA, db, cl, base_hot, 0, 0, 4096])
                emit(out, ["prefetch_access", layout, w, "2d", 0,
                           rep, t if t is not None else "",
                           nph, sysc])
            # 2e_K mode: use hot2e_W_layout_KN.csv, n_interior=0, n_leaf=K
            for K in K_VALUES:
                hot = ROOT / f"prefetch_access/runs/hot2e_{w}_{layout}_K{K}.csv"
                if not hot.exists():
                    print(f"  SKIP {hot.name} (missing)", file=sys.stderr)
                    continue
                for rep in range(1, REPS + 1):
                    t, nph, sysc = run_and_parse([PA, db, cl, hot, 0, K, 4096])
                    emit(out, ["prefetch_access", layout, w, f"2e_K{K}", K,
                               rep, t if t is not None else "",
                               nph, sysc])
        print(f"  workload={w} done", file=sys.stderr)

    # ============================================================
    # 3) prefetch_slru (2f) — 3 layouts × 3 workloads × 3 reps
    # ============================================================
    print(f"[3/3] prefetch_slru: 9 (wl,layout) × {REPS} reps", file=sys.stderr)
    for w in ["A", "B", "C"]:
        for layout in ["orig", "vacuum", "ta"]:
            db = DBS[layout]
            hot = HOTPAGES_BASE[(w, layout)]  # full resident hot set
            for rep in range(1, REPS + 1):
                t, nph, sysc = run_and_parse([PS, db, hot, 4096])
                emit(out, ["prefetch_slru", layout, w, "2f_SLRU", "",
                           rep, t if t is not None else "",
                           nph, sysc])
        print(f"  workload={w} done", file=sys.stderr)

print(f"\nDONE: wrote {outpath}", file=sys.stderr)
