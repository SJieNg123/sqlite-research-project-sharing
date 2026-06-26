#!/bin/sh
# runmatrix.sh — emit CSV: db,strategy,rep,first_query_us,avg_us,majflt,minflt
mkdir -p bench_records ops_csv
BH=/home/u03/sqlite-research-project-sharing/benchmark_harness/benchmark_harness
WL=/home/u03/sqlite-research-project-sharing/benchmark_harness/workloads/workload_a_zipfian.txt
echo "db,strategy,rep,first_query_us,avg_us,majflt,minflt"
for DB_LABEL in orig ta; do
  if [ "$DB_LABEL" = "orig" ]; then DB=test.db; CSV=classify_before.csv; else DB=test_typeaware.db; CSV=classify_after.csv; fi
  for STRAT in baseline range perpage layers5; do
    case "$STRAT" in
      baseline) PCS="" ;;
      range)    PCS="--post-cold-script ./prefetch_range_${DB_LABEL}.sh" ;;
      perpage)  PCS="--post-cold-script ./prefetch_perpage_${DB_LABEL}.sh" ;;
      layers5)  PCS="--post-cold-script ./prefetch_layers5_${DB_LABEL}.sh" ;;
    esac
    for REP in 1 2 3; do
      OUT="ops_csv/ops_${DB_LABEL}_${STRAT}_r${REP}.csv"
      LINE=$($BH --db "$DB" --workload "$WL" \
        --output "$OUT" --record-dir bench_records \
        --cold-advice dontneed --drop-caches-script ./cold_${DB_LABEL}.sh \
        $PCS 2>&1 | grep "^ops=" || echo "MISSING")
      # parse: ops=N avg_latency_us=X total_majflt=Y total_minflt=Z first_query_latency_us=W
      FQ=$(echo "$LINE"  | sed -n 's/.*first_query_latency_us=\([0-9.]*\).*/\1/p')
      AVG=$(echo "$LINE" | sed -n 's/.*avg_latency_us=\([0-9.]*\).*/\1/p')
      MAJ=$(echo "$LINE" | sed -n 's/.*total_majflt=\([0-9]*\).*/\1/p')
      MIN=$(echo "$LINE" | sed -n 's/.*total_minflt=\([0-9]*\).*/\1/p')
      echo "$DB_LABEL,$STRAT,$REP,$FQ,$AVG,$MAJ,$MIN"
    done
  done
done
