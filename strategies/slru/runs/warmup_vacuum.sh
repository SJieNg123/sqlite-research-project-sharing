#!/bin/sh
# warmup_vacuum.sh <workload.txt> <hotpages_out.csv>
set -e
WORKLOAD="$1"
OUT="$2"
DIR=/home/u03/sqlite-research-project-sharing/prefetch_slru/runs
DB="$DIR/test_vacuum.db"

"$DIR/evict" "$DB"

"$DIR/benchmark_harness" \
  --db "$DB" \
  --workload "$WORKLOAD" \
  --output "$DIR/warmup_vac_ops.csv" \
  --record-dir "$DIR/warmup_vac_records" \
  --cold-advice none \
  --mmap-size $(stat -c%s "$DB") \
  > "$DIR/warmup_vac_stdout.log" 2> "$DIR/warmup_vac_stderr.log"

"$DIR/residency_checker" "$DB" "$OUT" >> "$DIR/warmup_vac_stderr.log" 2>&1

TOTAL=$(awk -F, 'NR>1{n++} END{print n}' "$OUT")
HOT=$(awk -F, 'NR>1 && $2==1{n++} END{print n+0}' "$OUT")
echo "WARMUP done: workload=$WORKLOAD  resident=$HOT/$TOTAL pages  output=$OUT"
