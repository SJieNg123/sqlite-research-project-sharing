#!/bin/sh
# warmup_ta.sh <workload.txt> <hotpages_out.csv>
# Same as warmup_vacuum.sh but for layout 1c (type-aware DB).
set -e
WORKLOAD="$1"
OUT="$2"
DIR=/home/u03/sqlite-research-project-sharing/prefetch_slru/runs
DB="$DIR/test_typeaware.db"

"$DIR/evict" "$DB"

"$DIR/benchmark_harness" \
  --db "$DB" \
  --workload "$WORKLOAD" \
  --output "$DIR/warmup_ta_ops.csv" \
  --record-dir "$DIR/warmup_ta_records" \
  --cold-advice none \
  --mmap-size $(stat -c%s "$DB") \
  > "$DIR/warmup_ta_stdout.log" 2> "$DIR/warmup_ta_stderr.log"

"$DIR/residency_checker" "$DB" "$OUT" >> "$DIR/warmup_ta_stderr.log" 2>&1

TOTAL=$(awk -F, 'NR>1{n++} END{print n}' "$OUT")
HOT=$(awk -F, 'NR>1 && $2==1{n++} END{print n+0}' "$OUT")
echo "WARMUP done: workload=$WORKLOAD  resident=$HOT/$TOTAL pages  output=$OUT"
