#!/bin/sh
# warmup.sh <workload.txt> <hotpages_out.csv>
# 1. evict
# 2. run workload (populates page cache)
# 3. mincore dump → resident page CSV
set -e
WORKLOAD="$1"
OUT="$2"
DIR=/home/u03/sqlite-research-project-sharing/prefetch_slru/runs
DB="$DIR/test.db"

"$DIR/evict" "$DB"

"$DIR/benchmark_harness" \
  --db "$DB" \
  --workload "$WORKLOAD" \
  --output "$DIR/warmup_ops.csv" \
  --record-dir "$DIR/warmup_records" \
  --cold-advice none \
  --mmap-size $(stat -c%s "$DB") \
  > "$DIR/warmup_stdout.log" 2> "$DIR/warmup_stderr.log"

"$DIR/residency_checker" "$DB" "$OUT" >> "$DIR/warmup_stderr.log" 2>&1

# Quick stats
TOTAL=$(awk -F, 'NR>1{n++} END{print n}' "$OUT")
HOT=$(awk -F, 'NR>1 && $2==1{n++} END{print n+0}' "$OUT")
echo "WARMUP done: workload=$WORKLOAD  resident=$HOT/$TOTAL pages  output=$OUT"
