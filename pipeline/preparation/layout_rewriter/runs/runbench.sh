#!/bin/sh
# runbench.sh <label> <db> [post_cold_script]
LABEL="$1"; DB="$2"; PCS="$3"
mkdir -p bench_records
EXTRA=""
[ -n "$PCS" ] && EXTRA="--post-cold-script $PCS"
/home/u03/sqlite-research-project-sharing/benchmark_harness/benchmark_harness \
  --db "$DB" \
  --workload /home/u03/sqlite-research-project-sharing/benchmark_harness/workloads/workload_a_zipfian.txt \
  --output "ops_${LABEL}.csv" \
  --record-dir bench_records \
  --cold-advice dontneed \
  $EXTRA 2>&1 | tail -8
