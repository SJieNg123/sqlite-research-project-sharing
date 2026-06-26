#!/bin/sh
# 2c Layers_N sweep × Workload A/B/C × Layout 1b (VACUUM DB).
# N values: 0 (baseline), 1, 5, 10, 20, 46, 92. 3 reps each.
# Emits CSV: workload,N,rep,first_query_us,avg_us,majflt,minflt
set -u
DIR=/home/u03/sqlite-research-project-sharing/layout_rewriter/runs
BH=/home/u03/sqlite-research-project-sharing/benchmark_harness/benchmark_harness
WL_A=/home/u03/sqlite-research-project-sharing/benchmark_harness/workloads/workload_a_zipfian.txt
WL_B=/home/u03/sqlite-research-project-sharing/benchmark_harness/workloads/workload_uniform.txt
WL_C=/home/u03/sqlite-research-project-sharing/prefetch_churn/workloads/page_churn_benchmark_high.txt
mkdir -p "$DIR/bench_records_Nsweep_vac" "$DIR/ops_csv_Nsweep_vac"
echo "workload,N,rep,first_query_us,avg_us,majflt,minflt"

for WL_LABEL in A B C; do
  case "$WL_LABEL" in
    A) WL="$WL_A" ;;
    B) WL="$WL_B" ;;
    C) WL="$WL_C" ;;
  esac
  for N in 0 1 5 10 20 46 92; do
    if [ "$N" = "0" ]; then
      PCS=""
    else
      PCS="--post-cold-script $DIR/prefetch_layers${N}_vacuum.sh"
    fi
    for REP in 1 2 3; do
      OUT="$DIR/ops_csv_Nsweep_vac/ops_${WL_LABEL}_N${N}_r${REP}.csv"
      LINE=$($BH --db "$DIR/test_vacuum.db" --workload "$WL" \
        --output "$OUT" --record-dir "$DIR/bench_records_Nsweep_vac" \
        --cold-advice dontneed --drop-caches-script "$DIR/cold_vacuum.sh" \
        $PCS 2>&1 | grep "^ops=" || echo "MISSING")
      FQ=$(echo "$LINE"  | sed -n 's/.*first_query_latency_us=\([0-9.]*\).*/\1/p')
      AVG=$(echo "$LINE" | sed -n 's/.*avg_latency_us=\([0-9.]*\).*/\1/p')
      MAJ=$(echo "$LINE" | sed -n 's/.*total_majflt=\([0-9]*\).*/\1/p')
      MIN=$(echo "$LINE" | sed -n 's/.*total_minflt=\([0-9]*\).*/\1/p')
      echo "$WL_LABEL,$N,$REP,$FQ,$AVG,$MAJ,$MIN"
    done
  done
done
