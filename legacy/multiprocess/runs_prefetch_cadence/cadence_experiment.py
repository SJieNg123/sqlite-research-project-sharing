#!/usr/bin/env python3
"""Multi-process prefetch worker cadence × DB churn.

Scenario:
  - A long-lived WRITER process continuously churns the DB (insert/update/delete/rmw).
  - A long-lived PREFETCH worker fires every T_PREFETCH seconds: evict + prefetch_access (2e_k10).
  - N concurrent READER probes: each round, evict the DB pages and after a fixed gap measure
    the first-query latency of a single read in workload C.

We sweep T_PREFETCH in {1.0, 5.0, 30.0, never}. The probe gap T_GAP is fixed (3 s).
If T_PREFETCH << T_GAP: prefetcher fires during the gap → reader hits warm cache.
If T_PREFETCH >> T_GAP: prefetcher rarely fires within the gap → reader hits cold cache.

Output: one CSV row per probe (cadence, round, first_q_us, majflt, time_since_prefetch).
"""
import argparse, os, subprocess, sys, threading, time, random, csv, signal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHURN_DIR = ROOT / "prefetch_churn"
ACCESS_DIR = ROOT / "prefetch_access"
HARNESS = ROOT / "benchmark_harness/benchmark_harness"
EVICT = ROOT / "layout_rewriter/runs/evict"
CLASSIFY_BIN = ROOT / "classify_pages/classify_pages"
PREFETCH_ACCESS = ACCESS_DIR / "src/prefetch_access"

# Inputs that already exist in the repo:
SRC_DB = ROOT / "layout_rewriter/runs/test.db"          # 103 MB baseline
HOT_2E_K10 = ACCESS_DIR / "runs/hot2e_C_orig_K10.csv"   # static 2e_k10 hotpages
CLASSIFY_BASE = ACCESS_DIR / "runs/classify_before.csv" # static classify (baseline layout)
WORKLOAD_C = CHURN_DIR / "generated_workloads/page_churn_benchmark_high.txt"
WORKLOAD_WRITE = CHURN_DIR / "generated_workloads/page_churn_write.txt"


def run_writer(db: Path, stop_evt: threading.Event, log: Path):
    """Continuous writer: replay the churn workload in a sqlite3 CLI loop until stop."""
    import sqlite3, time as _t
    conn = sqlite3.connect(str(db), isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    cur = conn.cursor()
    # Read first 10000 lines of the write workload and loop them
    ops = []
    with WORKLOAD_WRITE.open() as f:
        for line in f:
            parts = line.split()
            if not parts: continue
            ops.append(parts)
            if len(ops) >= 5000: break
    next_id = 700000  # avoid conflict with reads in [590k, 610k]
    log_f = log.open("a")
    n = 0
    t0 = _t.time()
    while not stop_evt.is_set():
        for parts in ops:
            if stop_evt.is_set(): break
            op = parts[0]
            try:
                if op == "insert":
                    cur.execute("INSERT INTO items(id,k1,k2,payload) VALUES (?, ?, ?, randomblob(100))",
                                (next_id, f"k{next_id}", f"k{next_id}"))
                    next_id += 1
                elif op == "update":
                    k = int(parts[1])
                    cur.execute("UPDATE items SET payload=randomblob(100) WHERE id=?", (k,))
                elif op == "readmodifywrite":
                    k = int(parts[1])
                    cur.execute("UPDATE items SET payload=randomblob(100) WHERE id=?", (k,))
                # ignore reads/scans/deletes for write-load focus
                n += 1
                if n % 1000 == 0:
                    log_f.write(f"writer t+{_t.time()-t0:.1f}s ops={n} next_id={next_id}\n")
                    log_f.flush()
            except sqlite3.OperationalError as e:
                log_f.write(f"writer err: {e}\n")
                _t.sleep(0.05)
            # gentle pacing: 200 writes/sec
            _t.sleep(0.005)
    log_f.write(f"writer STOP t+{_t.time()-t0:.1f}s total_ops={n}\n")
    log_f.close()
    conn.close()


def run_prefetcher(db: Path, classify: Path, hotpages: Path,
                   period_s: float, stop_evt: threading.Event,
                   state: dict, log: Path):
    """Fire prefetch_access every period_s. Records last fire time in `state`."""
    log_f = log.open("a")
    t0 = time.time()
    while not stop_evt.is_set():
        try:
            # 2e_k10: cap_interior=0 (all resident interior), cap_leaf=10
            r = subprocess.run(
                [str(PREFETCH_ACCESS), str(db), str(classify), str(hotpages),
                 "0", "10", "4096"],
                capture_output=True, text=True, timeout=10
            )
            state["last_fire_at"] = time.time()
            state["fires"] = state.get("fires", 0) + 1
            log_f.write(f"prefetch t+{time.time()-t0:.1f}s rc={r.returncode} (fire #{state['fires']})\n")
            log_f.flush()
        except Exception as e:
            log_f.write(f"prefetch err: {e}\n")
        # sleep period_s, but check stop frequently
        slept = 0.0
        while slept < period_s and not stop_evt.is_set():
            time.sleep(min(0.2, period_s - slept))
            slept += 0.2
    log_f.close()


def probe(db: Path, workload: Path, gap_s: float, state: dict,
          rec_dir: Path, label: str):
    """One probe: evict db, sleep gap_s, run a tiny 100-op cold benchmark with --cold-advice none."""
    # Evict
    subprocess.run([str(EVICT), str(db)], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    evict_at = time.time()
    time.sleep(gap_s)
    # Build tiny workload (first 100 rows of workload C)
    small = rec_dir / f"wl_{label}.txt"
    with workload.open() as src, small.open("w") as dst:
        for i, line in enumerate(src):
            if i >= 100: break
            dst.write(line)
    out_csv = rec_dir / f"ops_{label}.csv"
    rd = rec_dir / f"run_{label}"
    rd.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        [str(HARNESS),
         "--workload", str(small),
         "--db", str(db),
         "--output", str(out_csv),
         "--record-dir", str(rd),
         "--cold-advice", "none"],
        capture_output=True, text=True, timeout=30
    )
    # Parse latest run record
    log_files = sorted(rd.glob("run-*.log"))
    if not log_files:
        return None
    log = log_files[-1].read_text()
    def grab(pat):
        for line in log.splitlines():
            if pat in line:
                # e.g. "first_query_latency_us=...."
                for tok in line.split():
                    if "=" in tok:
                        k, v = tok.split("=", 1)
                        if k == pat:
                            try: return float(v)
                            except ValueError: pass
        return None
    first_q = grab("first_query_latency_us")
    avg = grab("avg_latency_us")
    majf = grab("total_majflt")
    minf = grab("total_minflt")
    time_since = (evict_at - state.get("last_fire_at", 0)) if state.get("last_fire_at") else None
    return {
        "first_q_us": first_q, "avg_us": avg, "majflt": majf, "minflt": minf,
        "evict_at": evict_at, "last_prefetch_at": state.get("last_fire_at"),
        "time_since_prefetch_s": time_since,
        "fires": state.get("fires", 0),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None,
                    help="work DB path; default: copy of SRC_DB into runs_prefetch_cadence/work.db")
    ap.add_argument("--rounds", type=int, default=6)
    ap.add_argument("--gap-s", type=float, default=3.0)
    ap.add_argument("--cadences", default="1.0,5.0,30.0,never",
                    help="comma-separated prefetch periods (seconds) or 'never'")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    rundir = Path(__file__).parent
    rec = rundir / "rec"
    rec.mkdir(exist_ok=True)
    work_db = Path(args.db) if args.db else rundir / "work.db"
    if not work_db.exists():
        print(f"copying {SRC_DB} → {work_db} (103 MB)…", flush=True)
        subprocess.run(["cp", str(SRC_DB), str(work_db)], check=True)
    out = Path(args.out) if args.out else rundir / "cadence_results.csv"
    fields = ["cadence", "round", "first_q_us", "avg_us", "majflt", "minflt",
              "time_since_prefetch_s", "fires_total", "wallclock_s"]
    rows = []
    t_global = time.time()
    for cad_s in args.cadences.split(","):
        cad = cad_s.strip()
        print(f"\n=== cadence={cad} ===", flush=True)
        stop = threading.Event()
        state = {"last_fire_at": None, "fires": 0}
        # Snapshot work DB to per-cadence file so writers don't accumulate across runs
        cad_db = rundir / f"work_{cad}.db"
        subprocess.run(["cp", str(work_db), str(cad_db)], check=True)
        # Start writer
        writer_log = rec / f"writer_{cad}.log"
        wt = threading.Thread(target=run_writer, args=(cad_db, stop, writer_log), daemon=True)
        wt.start()
        # Start prefetcher (unless never)
        pf = None
        if cad != "never":
            period = float(cad)
            pf_log = rec / f"prefetch_{cad}.log"
            pf = threading.Thread(target=run_prefetcher,
                                  args=(cad_db, CLASSIFY_BASE, HOT_2E_K10,
                                        period, stop, state, pf_log),
                                  daemon=True)
            pf.start()
        # Warm-up grace period for writer + prefetcher to settle
        time.sleep(2.0)
        for rnd in range(args.rounds):
            label = f"{cad}_r{rnd}"
            t0 = time.time()
            r = probe(cad_db, WORKLOAD_C, args.gap_s, state, rec, label)
            t_wc = time.time() - t0
            if r is None:
                print(f"  round {rnd}: PROBE FAILED", flush=True)
                continue
            row = {"cadence": cad, "round": rnd,
                   "first_q_us": r["first_q_us"],
                   "avg_us": r["avg_us"],
                   "majflt": r["majflt"], "minflt": r["minflt"],
                   "time_since_prefetch_s": (f"{r['time_since_prefetch_s']:.2f}"
                                             if r["time_since_prefetch_s"] is not None else ""),
                   "fires_total": r["fires"],
                   "wallclock_s": f"{t_wc:.2f}"}
            rows.append(row)
            print(f"  round {rnd}: first_q={r['first_q_us']:.1f}µs majflt={r['majflt']:.0f} "
                  f"Δprefetch={row['time_since_prefetch_s']}s fires={r['fires']}", flush=True)
        # Stop workers
        stop.set()
        wt.join(timeout=5)
        if pf: pf.join(timeout=5)
        # Cleanup per-cadence DB (large)
        try:
            cad_db.unlink()
            for ext in ("-wal", "-shm"):
                p = Path(str(cad_db) + ext)
                if p.exists(): p.unlink()
        except OSError: pass
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows: w.writerow(r)
    print(f"\nwrote {out} ({len(rows)} rows, total {time.time()-t_global:.1f}s)")


if __name__ == "__main__":
    main()
