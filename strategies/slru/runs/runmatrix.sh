#!/bin/bash
# 3 strategies × 2 workloads × 3 reps = 18 runs.
# Strategies: baseline (no prefetch), strategy 1 (layers N=5), strategy 4 (slru)
# Workloads:  A (uniform) = workload_uniform.txt, B (skewed) = workload_a_zipfian.txt
set -u
DIR=/home/u03/sqlite-research-project-sharing/prefetch_slru/runs
DB="$DIR/test.db"
REPS=3
RESULTS="$DIR/matrix_results.csv"

echo "workload,strategy,rep,first_query_us,prefetch_us,n_prefetch" > "$RESULTS"

run_one() {
  local workload_label="$1" workload_file="$2" strat_label="$3" post_cold="$4"
  for rep in $(seq 1 $REPS); do
    local ops_csv="$DIR/ops_${workload_label}_${strat_label}_r${rep}.csv"
    local rec_dir="$DIR/rec_${workload_label}_${strat_label}_r${rep}"
    local stderr_log="$DIR/log_${workload_label}_${strat_label}_r${rep}.err"
    rm -rf "$rec_dir"; mkdir -p "$rec_dir"

    local extra=""
    [ -n "$post_cold" ] && extra="--post-cold-script $post_cold"

    "$DIR/benchmark_harness" \
      --db "$DB" \
      --workload "$workload_file" \
      --output "$ops_csv" \
      --record-dir "$rec_dir" \
      --mmap-size $(stat -c%s "$DB") \
      --cold-advice dontneed \
      --drop-caches-script "$DIR/evict_helper.sh" \
      $extra \
      > /dev/null 2> "$stderr_log"

    # Extract first-query latency from ops CSV (second column header = latency_ns)
    local first_q_us
    first_q_us=$(awk -F, 'NR==2 {printf "%.2f", $2/1000.0; exit}' "$ops_csv")
    # Extract prefetch syscall stats (from post-cold-script stderr injected via benchmark_harness)
    local pf_us=$(grep -oE "time_us=[0-9.]+" "$stderr_log" | head -1 | cut -d= -f2)
    local pf_n=$(grep -oE "n_prefetch=[0-9]+" "$stderr_log" | head -1 | cut -d= -f2)
    pf_us=${pf_us:-0}
    pf_n=${pf_n:-0}

    echo "$workload_label,$strat_label,$rep,$first_q_us,$pf_us,$pf_n" | tee -a "$RESULTS"
  done
}

for wl in A:workload_a_zipfian.txt B:workload_b_uniform.txt; do
  label="${wl%%:*}"
  file="$DIR/${wl##*:}"
  run_one "$label" "$file" "baseline" ""
  run_one "$label" "$file" "layers5"  "$DIR/prefetch_layers5.sh"
  run_one "$label" "$file" "slru"     "$DIR/prefetch_slru_${label,,}.sh"
done

echo "---"
echo "DONE → $RESULTS"
