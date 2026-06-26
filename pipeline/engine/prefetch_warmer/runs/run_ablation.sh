#!/bin/bash
# A3 ablation ladder for the Level-1 prefetch warmer.
#
# Each rep: cold-evict the DB -> run the warmer (post-cold-script, env-driven) ->
# benchmark_harness opens SQLite and times the workload. Same binary for every
# arm; only env (WARM_MODE/WARM_METHOD/WARM_HOTSET) changes (§0.2 principle 1).
#
# Arms:
#   L0_off               baseline, no warming
#   L1_int_pread         warm 92 interior pages, pread   (blocking, guarantees resident)
#   L1_int_fadvise       warm 92 interior pages, fadvise (async hint, non-blocking)
#   L5_intleaf_pread     warm 92 interior + 10 hot leaves, pread
#   L5_intleaf_fadvise   warm 92 interior + 10 hot leaves, fadvise
#
# Output: ablation_raw.csv  (mode,rep,first_query_us,avg_us,majflt,minflt,warmer_us,warmed_pages)
set -u
ROOT=/home/u03/sqlite-research-project-sharing
DB=$ROOT/prefetch_access/runs/test.db
BH=$ROOT/benchmark_harness/benchmark_harness
WL=$ROOT/prefetch_access/runs/workload_a_zipfian.txt
DIR=$ROOT/prefetch_warmer/runs
REPS=${REPS:-30}
cd "$DIR"
mkdir -p bench_records

OUT=ablation_raw.csv
echo "mode,rep,first_query_us,avg_us,majflt,minflt,warmer_us,warmed_pages" > "$OUT"

run_arm() {
  local tag="$1" mode="$2" method="$3" hs="$4"
  for rep in $(seq 1 "$REPS"); do
    local o
    o=$(WARM_MODE="$mode" WARM_METHOD="$method" WARM_HOTSET="$hs" \
        "$BH" --db "$DB" --workload "$WL" --output /tmp/ablation_ops.csv \
        --record-dir bench_records --cold-advice dontneed \
        --drop-caches-script "$DIR/cold.sh" --post-cold-script "$DIR/warm_wrapper.sh" 2>&1)
    local fq av mj mn wu wp
    fq=$(echo "$o" | sed -n 's/.*first_query_latency_us=\([0-9.]*\).*/\1/p')
    av=$(echo "$o" | sed -n 's/.*avg_latency_us=\([0-9.]*\).*/\1/p')
    mj=$(echo "$o" | sed -n 's/.*total_majflt=\([0-9]*\).*/\1/p')
    mn=$(echo "$o" | sed -n 's/.*total_minflt=\([0-9]*\).*/\1/p')
    wu=$(echo "$o" | sed -n 's/.*warmer_us=\([0-9.]*\).*/\1/p')
    wp=$(echo "$o" | sed -n 's/.*warmed_pages=\([0-9]*\).*/\1/p')
    echo "$tag,$rep,${fq:-NA},${av:-NA},${mj:-NA},${mn:-NA},${wu:-NA},${wp:-NA}" >> "$OUT"
  done
  echo "  done $tag ($REPS reps)"
}

echo "=== ablation: $REPS reps/arm ==="
run_arm L0_off              off  ""      ""
run_arm L1_int_pread        warm pread   "$DIR/hotset_internal.csv"
run_arm L1_int_fadvise      warm fadvise "$DIR/hotset_internal.csv"
run_arm L2_root_pread       warm pread   "$DIR/hotset_treetop_root.csv"
run_arm L2_items_pread      warm pread   "$DIR/hotset_items_interior.csv"
run_arm L2_items_fadvise    warm fadvise "$DIR/hotset_items_interior.csv"
run_arm L5_intleaf_pread    warm pread   "$DIR/hotset_internal_hotleaf.csv"
run_arm L5_intleaf_fadvise  warm fadvise "$DIR/hotset_internal_hotleaf.csv"
echo "ALL DONE -> $OUT"
