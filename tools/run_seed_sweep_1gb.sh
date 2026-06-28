#!/bin/bash
# R3 size-sensitivity sweep (1 GB DB): run the A/B/C x strategy matrix across the
# same workload seeds as the 100 MB sweep (tools/run_seed_sweep.sh), but against
# the 1gb layout only, into a SEPARATE tree so results/seeds/ (the committed 100 MB
# R3 data) is never touched. Pairing each strategy to the SAME-seed baseline makes
# the cross-seed effect % drift-robust, so this aligns 1 GB uncertainty with 100 MB.
#
# Per seed: (1) regen 1gb access-pattern hotsets from that seed's query stream
# (--no-freeze: supplementary, leaves the master freeze manifest alone),
# (2) run the matrix at default reps (async 10 / pread 5 / baseline 10 -- same as
# results/seeds, so the orig-vs-1gb CI comparison is apples-to-apples).
#
# Usage: tools/run_seed_sweep_1gb.sh [seed-list]   (default "1 2 3 4 5 6 7 8 9 10")
# Resumable: a seed whose results/seeds_1gb/seedNN/raw.csv already looks complete is skipped.
set -uo pipefail
cd /home/u03/sqlite-research-project-sharing || exit 1

SEEDS="${*:-1 2 3 4 5 6 7 8 9 10}"
WL=A,B,C
mkdir -p results/seeds_1gb
LOG=results/seeds_1gb/sweep.log
ts() { date -u +%FT%TZ; }

echo "=== 1gb sweep start $(ts)  seeds: $SEEDS  workloads: $WL ===" | tee -a "$LOG"
for n in $SEEDS; do
  pad=$(printf '%02d' "$n")
  out="results/seeds_1gb/seed${pad}"
  raw="$out/raw.csv"
  if [ -f "$raw" ] && [ "$(wc -l < "$raw")" -gt 300 ]; then
    echo "--- seed $n SKIP (already $(wc -l < "$raw") rows) $(ts) ---" | tee -a "$LOG"
    continue
  fi

  echo "--- seed $n regen  $(ts) ---" | tee -a "$LOG"
  if ! python3 run_experiment.py run --seed "$n" --db 1gb --workload "$WL" \
        --regen-hotsets --yes --no-freeze --outdir "$out" >>"$LOG" 2>&1; then
    echo "!!! seed $n REGEN FAILED $(ts)" | tee -a "$LOG"; continue
  fi

  echo "--- seed $n matrix $(ts) ---" | tee -a "$LOG"
  if ! python3 run_experiment.py run --seed "$n" --db 1gb --workload "$WL" \
        --outdir "$out" >>"$LOG" 2>&1; then
    echo "!!! seed $n RUN FAILED $(ts)" | tee -a "$LOG"; continue
  fi

  rows=$( [ -f "$raw" ] && wc -l < "$raw" || echo 0 )
  echo "--- seed $n DONE $(ts)  raw=$raw rows=$rows ---" | tee -a "$LOG"
done
echo "=== 1gb sweep complete $(ts) ===" | tee -a "$LOG"
