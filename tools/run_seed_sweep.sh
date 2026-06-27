#!/bin/bash
# R3 workload-sensitivity sweep: run the full A/B/C x layout x strategy matrix
# across workload seeds. Per seed: (1) regen access-pattern hotsets from that
# seed's query stream, (2) run the matrix at default reps (async 10 / pread 5 /
# baseline 10 -- same as results/main, so cross-seed comparison is apples-to-apples).
#
# Usage: tools/run_seed_sweep.sh [seed-list]   (default "1 2 3 4 5 6 7 8 9 10")
# Resumable: a seed whose results/seeds/seedNN/raw.csv already looks complete is skipped.
set -uo pipefail
cd /home/u03/sqlite-research-project-sharing || exit 1

SEEDS="${*:-1 2 3 4 5 6 7 8 9 10}"
mkdir -p results/seeds
LOG=results/seeds/sweep.log
ts() { date -u +%FT%TZ; }

echo "=== sweep start $(ts)  seeds: $SEEDS ===" | tee -a "$LOG"
for n in $SEEDS; do
  pad=$(printf '%02d' "$n")
  raw="results/seeds/seed${pad}/raw.csv"
  if [ -f "$raw" ] && [ "$(wc -l < "$raw")" -gt 1000 ]; then
    echo "--- seed $n SKIP (already $(wc -l < "$raw") rows) $(ts) ---" | tee -a "$LOG"
    continue
  fi

  echo "--- seed $n regen  $(ts) ---" | tee -a "$LOG"
  if ! python3 run_experiment.py run --seed "$n" --regen-hotsets --yes >>"$LOG" 2>&1; then
    echo "!!! seed $n REGEN FAILED $(ts)" | tee -a "$LOG"; continue
  fi

  echo "--- seed $n matrix $(ts) ---" | tee -a "$LOG"
  if ! python3 run_experiment.py run --seed "$n" >>"$LOG" 2>&1; then
    echo "!!! seed $n RUN FAILED $(ts)" | tee -a "$LOG"; continue
  fi

  rows=$( [ -f "$raw" ] && wc -l < "$raw" || echo 0 )
  echo "--- seed $n DONE $(ts)  raw=$raw rows=$rows ---" | tee -a "$LOG"
done
echo "=== sweep complete $(ts) ===" | tee -a "$LOG"
