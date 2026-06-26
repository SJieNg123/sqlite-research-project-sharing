#!/bin/sh
# Strategy 1b (VACUUM) × Workload B (uniform) and C (high-key uniform)
# Emits CSV: workload,db,strategy,rep,first_query_us,avg_us,majflt,minflt
set -u
DIR=/home/u03/sqlite-research-project-sharing/layout_rewriter/runs
BH=/home/u03/sqlite-research-project-sharing/benchmark_harness/benchmark_harness
WL_B=/home/u03/sqlite-research-project-sharing/benchmark_harness/workloads/workload_uniform.txt
WL_C=/home/u03/sqlite-research-project-sharing/prefetch_churn/workloads/page_churn_benchmark_high.txt
mkdir -p "$DIR/bench_records_1b_bc" "$DIR/ops_csv_1b_bc"
echo "workload,db,strategy,rep,first_query_us,avg_us,majflt,minflt"

for WL_LABEL in B C; do
  if [ "$WL_LABEL" = "B" ]; then WL="$WL_B"; else WL="$WL_C"; fi
  for DB_LABEL in orig vacuum; do
    if [ "$DB_LABEL" = "orig" ]; then DB="$DIR/test.db"; else DB="$DIR/test_vacuum.db"; fi
    for STRAT in baseline range perpage layers5; do
      case "$STRAT" in
        baseline) PCS="" ;;
        range)    PCS="--post-cold-script $DIR/prefetch_range_${DB_LABEL}.sh" ;;
        perpage)  PCS="--post-cold-script $DIR/prefetch_perpage_${DB_LABEL}.sh" ;;
        layers5)  PCS="--post-cold-script $DIR/prefetch_layers5_${DB_LABEL}.sh" ;;
      esac
      for REP in 1 2 3; do
        OUT="$DIR/ops_csv_1b_bc/ops_${WL_LABEL}_${DB_LABEL}_${STRAT}_r${REP}.csv"
        LINE=$($BH --db "$DB" --workload "$WL" \
          --output "$OUT" --record-dir "$DIR/bench_records_1b_bc" \
          --cold-advice dontneed --drop-caches-script "$DIR/cold_${DB_LABEL}.sh" \
          $PCS 2>&1 | grep "^ops=" || echo "MISSING")
        FQ=$(echo "$LINE"  | sed -n 's/.*first_query_latency_us=\([0-9.]*\).*/\1/p')
        AVG=$(echo "$LINE" | sed -n 's/.*avg_latency_us=\([0-9.]*\).*/\1/p')
        MAJ=$(echo "$LINE" | sed -n 's/.*total_majflt=\([0-9]*\).*/\1/p')
        MIN=$(echo "$LINE" | sed -n 's/.*total_minflt=\([0-9]*\).*/\1/p')
        echo "$WL_LABEL,$DB_LABEL,$STRAT,$REP,$FQ,$AVG,$MAJ,$MIN"
      done
    done
  done
done
