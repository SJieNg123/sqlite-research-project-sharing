#!/bin/bash
# S3: sub-working-set RAM-pressure sweep (review item R3 W3).
# The old axis used cgroup MemoryMax=20M, which is ABOVE the ~17.3 MB resident working set
# (A/B) -> no real reclaim -> ratio ~1.0. Here we step the cap BELOW the working set and
# watch, per strategy, how much of the prefetched hotset survives to first-query
# (delivery_pct = mincore residual) and what that does to first-q.
#
# Hotset footprints decide who feels the squeeze:
#   2e_K10  ~112 KB  (targeted)      -> below any viable cap -> never evicted -> robust
#   2e_K500 ~2.07 MB                  -> still fits >=6M
#   2f_slru ~17.7 MB (= whole WS)     -> cannot fit < ~16M -> dump gets reclaimed -> collapses
# Floor: ~6M is the smallest cap that still measures cleanly (4M -> cold gate excludes all).
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=results/ram_pressure
mkdir -p "$OUT"
SEED=1
WL="A,B"                                  # both have ~17.3 MB working set
STR="2e_K10,2e_K500,2f_slru"              # baseline auto-runs; tiny / medium / huge hotset
for CAP in none 16M 12M 8M 6M; do
  tag=$([ "$CAP" = none ] && echo "unlimited" || echo "$CAP")
  echo "=== mem cap=$CAP ===" >&2
  python3 run_experiment.py run --seed "$SEED" --db orig \
      --workload "$WL" --strategy "$STR" \
      --mem-limit "$CAP" \
      --async-reps 5 --pread-reps 2 --baseline-reps 3 \
      --outdir "$OUT/cap_$tag" >/dev/null 2>"$OUT/cap_$tag.log"
  echo "done cap=$CAP -> $OUT/cap_$tag/summary.csv" >&2
done
echo "ALL_DONE ram_pressure" >&2
