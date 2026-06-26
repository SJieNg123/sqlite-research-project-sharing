#!/usr/bin/env python3
"""
hotset_residency.py — verify what fraction of an intended prefetch hotset is
actually resident in the OS page cache at a given moment.

P0 pipeline uses this as the post-cold-script verification step, bracketing the
prefetch call (see IMPLEMENTATION_PIPELINES.md §3):

  ① cold check    (after evict, before prefetch):  expect ~0%   -> --max-pct 1
  ② delivery check(after prefetch, before query):  expect high  -> --min-pct 95  (pread arms only)

Inputs
------
snapshot.csv : residency_checker output  ->  page_number,is_resident   (one row per DB page)
hotset       : the pages we INTENDED to load. Two formats auto-detected by header:
                 - warmer hotset :  page_number,file_offset      (every row is in the hotset)
                 - access/slru   :  page_number,is_resident      (only is_resident==1 rows count)

Output (stderr): "<label>_pct=XX.X resident=<hit>/<total>"
                 (machine-readable; harness folds it into the run record)

Exit codes: 0 normal; 2 bad input; 3 a --min-pct / --max-pct gate was violated.

Usage
-----
  hotset_residency.py <snapshot.csv> <hotset.csv> [--label delivery] [--min-pct 95] [--max-pct 100]
"""
import sys
import csv
import argparse


def _die(msg):
    sys.stderr.write("hotset_residency: " + msg + "\n")
    sys.exit(2)


def read_resident_set(path):
    """snapshot (page_number,is_resident) -> set of page numbers with is_resident==1."""
    resident = set()
    with open(path, newline="") as f:
        r = csv.DictReader(f)
        cols = r.fieldnames or []
        if "page_number" not in cols or "is_resident" not in cols:
            _die("snapshot %s needs columns page_number,is_resident (got %s)" % (path, cols))
        for row in r:
            try:
                if int(row["is_resident"]) == 1:
                    resident.add(int(row["page_number"]))
            except (ValueError, TypeError):
                continue
    return resident


def read_hotset(path):
    """Return the set of page numbers we intended to prefetch. Format auto-detected."""
    with open(path, newline="") as f:
        r = csv.DictReader(f)
        cols = r.fieldnames or []
        if "page_number" not in cols:
            _die("hotset %s has no page_number column (got %s)" % (path, cols))
        # access/slru hotpages mark the chosen pages with is_resident==1; warmer
        # hotsets (page_number,file_offset) list only the chosen pages, so take all.
        gate_on_resident = "is_resident" in cols
        pages = set()
        for row in r:
            try:
                pn = int(row["page_number"])
            except (ValueError, TypeError):
                continue
            if gate_on_resident:
                try:
                    if int(row["is_resident"]) != 1:
                        continue
                except (ValueError, TypeError):
                    continue
            pages.add(pn)
    return pages


def main(argv=None):
    ap = argparse.ArgumentParser(description="Hotset residency check for the P0 pipeline.")
    ap.add_argument("snapshot", help="residency_checker output (page_number,is_resident)")
    ap.add_argument("hotset", help="intended prefetch hotset CSV")
    ap.add_argument("--label", default="delivery",
                    help="prefix for the emitted metric (e.g. cold / delivery)")
    ap.add_argument("--min-pct", type=float, default=None,
                    help="exit 3 if resident%% < this (delivery gate; use for pread arms)")
    ap.add_argument("--max-pct", type=float, default=None,
                    help="exit 3 if resident%% > this (cold gate; e.g. 1 to assert evicted)")
    args = ap.parse_args(argv)

    resident = read_resident_set(args.snapshot)
    hotset = read_hotset(args.hotset)
    if not hotset:
        _die("hotset %s is empty" % args.hotset)

    hit = len(hotset & resident)
    total = len(hotset)
    pct = 100.0 * hit / total

    sys.stderr.write("%s_pct=%.1f resident=%d/%d\n" % (args.label, pct, hit, total))

    if args.min_pct is not None and pct < args.min_pct:
        sys.stderr.write("GATE FAIL: %s_pct %.1f < min %.1f\n" % (args.label, pct, args.min_pct))
        return 3
    if args.max_pct is not None and pct > args.max_pct:
        sys.stderr.write("GATE FAIL: %s_pct %.1f > max %.1f\n" % (args.label, pct, args.max_pct))
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
