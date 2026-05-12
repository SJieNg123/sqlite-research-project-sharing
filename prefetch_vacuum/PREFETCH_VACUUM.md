# Prefetch & VACUUM Experiments (Week 9–11)

These tools investigate whether prefetching SQLite interior pages before a
cold-start workload reduces first-query latency, and whether VACUUM improves
the spatial layout of interior pages.

---

## Background

SQLite uses a B+tree structure stored as a flat array of 4 KB pages on disk.
When an app is killed and restarted (cold start), the OS page cache is empty.
Every query must walk from the root down through **interior pages** before
reaching leaf pages that hold actual data. Each interior page that is not
resident in the page cache triggers a page fault (disk I/O), making the first
query significantly slower than subsequent ones.

Key observation: interior pages represent only ~0.35% of all pages, but every
single query must pass through them. If we can prefetch just those pages back
into the page cache before the first query runs, we can reduce cold-start
latency substantially.

---

## Tools

### `prefetch.c` — Strategy comparison (Week 9)

Reads `classify_pages.csv` to find all interior page offsets, then prefetches
them using one of two strategies:

| Strategy | Behaviour |
|----------|-----------|
| `range` | Merges contiguous interior pages into ranges; calls `madvise(MADV_WILLNEED)` once per range |
| `perpage` | Calls `madvise(MADV_WILLNEED)` once per interior page individually |

**Build:**
```bash
gcc -O2 -Wall -o prefetch prefetch.c
```

**Usage:**
```bash
./prefetch <database.db> <classify_pages.csv> <strategy>
# strategy: range | perpage
```

**Example:**
```bash
./prefetch test.db classify_pages.csv range
./prefetch test.db classify_pages.csv perpage
```

**Output (stdout):** CSV row with strategy, interior page count, syscall count,
prefetch time, resident pages before prefetch, resident pages after prefetch,
and residency percentage.

**Output (stderr):** Human-readable summary including interior pages found,
strategy, syscall count, prefetch time, and interior page residency before and
after a 500 ms wait for async I/O to complete.

> The tool waits 500 ms after calling `madvise()` before checking residency.
> This gives the OS time to finish the async I/O so the residency check
> reflects the actual result of the prefetch, not just the state immediately
> after the syscall returns.

---

### `prefetch_layers.c` — Layer sweep / sweet spot search (Week 10)

Instead of prefetching all interior pages, this tool prefetches only the first
`N` interior pages sorted by file offset (i.e. pages closest to the start of
the file, which correspond to the upper layers of the B+tree).

The goal is to find the **sweet spot**: the minimum number of pages to prefetch
that yields the best first-query latency improvement.

**Build:**
```bash
gcc -O2 -Wall -o prefetch_layers prefetch_layers.c
```

**Usage:**
```bash
./prefetch_layers <database.db> <classify_pages.csv> <n_pages> <page_size>
```

**Example:**
```bash
./prefetch_layers test.db classify_pages.csv 5 4096
```

**Output:** Single line reporting `n_prefetch`, `syscalls`, and `time_us`.

---

## Recommended Workflow

### Full cold-start experiment with prefetch

```bash
# 1. Build the test database
python3 testdb_builder.py

# 2. Classify all pages
./classify_pages test.db > classify_pages.csv 2> stats.txt

# 3. Run baseline (no prefetch)
sync && echo 3 | sudo tee /proc/sys/vm/drop_caches > /dev/null
./benchmark_harness \
  --db test.db \
  --workload workloadc.txt \
  --output ops_baseline.csv \
  --record-dir benchmark_harness_runs \
  --cold-advice cold

# 4. Run with prefetch (range strategy)
sync && echo 3 | sudo tee /proc/sys/vm/drop_caches > /dev/null
./prefetch test.db classify_pages.csv range
./benchmark_harness \
  --db test.db \
  --workload workloadc.txt \
  --output ops_prefetch_range.csv \
  --record-dir benchmark_harness_runs \
  --cold-advice cold

# 5. Run with prefetch (perpage strategy)
sync && echo 3 | sudo tee /proc/sys/vm/drop_caches > /dev/null
./prefetch test.db classify_pages.csv perpage
./benchmark_harness \
  --db test.db \
  --workload workloadc.txt \
  --output ops_prefetch_perpage.csv \
  --record-dir benchmark_harness_runs \
  --cold-advice cold
```

### Layer sweep (find sweet spot)

```bash
for N in 1 5 10 20 46 92; do
    echo "=== prefetch $N pages ==="
    sync && echo 3 | sudo tee /proc/sys/vm/drop_caches > /dev/null
    ./prefetch_layers test.db classify_pages.csv $N 4096
    ./benchmark_harness \
      --db test.db \
      --workload workloadc.txt \
      --output ops_layers_${N}.csv \
      --record-dir benchmark_harness_runs \
      --cold-advice cold 2>&1 | grep "first_query_latency"
done
```

### VACUUM comparison (Week 11)

```bash
# Save pre-VACUUM classifier output
cp classify_pages.csv classify_pages_before_vacuum.csv

# Run VACUUM
sqlite3 test.db "VACUUM;"

# Reclassify after VACUUM
./classify_pages test.db > classify_pages_after_vacuum.csv 2> stats_after_vacuum.txt

# Compare scatter scores
python3 plot_pages.py classify_pages_before_vacuum.csv  page_layout_before_vacuum.png
python3 plot_pages.py classify_pages_after_vacuum.csv   page_layout_after_vacuum.png

# Benchmark with prefetch on post-VACUUM database
sync && echo 3 | sudo tee /proc/sys/vm/drop_caches > /dev/null
./prefetch_layers test.db classify_pages_after_vacuum.csv 5 4096
./benchmark_harness \
  --db test.db \
  --workload workloadc.txt \
  --output ops_after_vacuum_prefetch5.csv \
  --record-dir benchmark_harness_runs \
  --cold-advice cold 2>&1 | grep "first_query_latency"
```

---

## Experimental Results

Database: `test.db` — 600k rows, 26331 pages (4 KB each), 92 interior pages (0.35%)

Workload: `workloadc.txt` — 100% random point reads, 100000 operations

### Week 9: Strategy Comparison

| Strategy | Syscalls | Prefetch time | Interior resident after 500ms | First query latency | Improvement |
|----------|----------|--------------|-------------------------------|-------------------|-------------|
| Baseline (no prefetch) | 0 | 0 μs | 0/92 (0%) | 73.06 μs | — |
| `range` | 87 | 3068 μs | 91/92 (98.9%) | 53.59 μs | -26.6% |
| `perpage` | 92 | 2569 μs | 91/92 (98.9%) | 47.97 μs | -34.3% |

**Syscall count:** `range` merges 92 interior pages into only 87 ranges,
saving 5 syscalls. The saving is tiny because interior pages have a scatter
score of 0.96 — almost completely non-contiguous. There are barely any
adjacent interior pages to merge.

**Prefetch time:** `perpage` is faster (2569 μs vs 3068 μs) despite more
syscalls. `range` covers large contiguous byte spans that include many leaf
pages between interior pages, causing the kernel to read unnecessary data.
`perpage` only touches the exact 92 pages needed.

**Page residency:** After waiting 500 ms for async I/O to finish, both
strategies successfully load 91/92 (98.9%) of interior pages. The residency
outcome is the same — the difference is only in how fast each strategy
completes the load. `perpage` finishes faster, which is why it produces lower
first-query latency when the benchmark starts immediately after prefetch.

**Why file layout matters:** If interior pages were clustered at the start of
the file, `range` would merge all of them into 1–2 syscalls covering a small
contiguous region. The kernel's sequential readahead would load them all in a
single efficient I/O pass. With the current scattered layout, this advantage
disappears entirely. A type-aware VACUUM that places interior pages together
would make `range` significantly more effective than `perpage`.

### Week 10: Layer Sweep

| N pages prefetched | Syscalls | Prefetch time | First query latency | Improvement |
|--------------------|----------|--------------|-------------------|-------------|
| 0 (baseline) | 0 | 0 μs | 73.06 μs | — |
| 1 | 1 | 35 μs | 38.12 μs | -47.8% |
| **5 ← sweet spot** | **5** | **94 μs** | **33.44 μs** | **-54.2%** |
| 10 | 10 | 273 μs | 44.36 μs | -39.3% |
| 20 | 20 | 607 μs | 34.63 μs | -52.6% |
| 46 | 46 | 1173 μs | 40.52 μs | -44.6% |
| 92 | 92 | 2229 μs | 50.24 μs | -31.3% |

The sweet spot is **5 pages**. `madvise(MADV_WILLNEED)` is asynchronous — it
signals the OS to load pages but does not wait for completion. Prefetching too
many pages means the OS cannot finish loading them before the benchmark starts,
so later queries still page fault. 5 pages is fast enough (~94 μs) that the OS
completes the load before the first query runs.

### Week 11: VACUUM Effect

| Condition | Scatter score | First query latency | Improvement vs baseline |
|-----------|--------------|-------------------|------------------------|
| Before VACUUM + prefetch 5 | 0.96 | 33.44 μs | -54.2% |
| After VACUUM + prefetch 5 | 1.13 | 66.19 μs | -9.4% |

VACUUM made things worse. The scatter score increased from 0.96 to 1.13,
meaning interior pages became *more* scattered after VACUUM — spread further
toward the end of the file. This is because `sqlite3RunVacuum()` in
`src/vacuum.c` allocates pages strictly by insertion order and does not
consider page type. New interior pages end up placed after large runs of leaf
pages, degrading prefetch effectiveness.

This is a concrete improvement opportunity for SQLite: a type-aware VACUUM
that places interior pages at the beginning of the file would allow a single
contiguous `madvise(MADV_WILLNEED)` call to prefetch all of them efficiently.

---

## Key Takeaways

- Prefetching only the **top 5 interior pages** (by file offset) reduces
  cold-start first-query latency by **54%** with just 5 syscalls and ~94 μs
  of prefetch overhead.
- Interior pages are highly scattered throughout the file (scatter score ~1.0),
  so range merging provides no meaningful syscall reduction. Both strategies
  load 91/92 interior pages successfully after 500 ms — the difference is only
  in how fast the load completes.
- File layout directly determines which prefetch strategy is more efficient.
  With clustered interior pages, `range` would require only 1–2 syscalls and
  benefit from sequential readahead. With scattered pages, `perpage` wins
  because it avoids loading unnecessary leaf pages between interior pages.
- VACUUM does not improve interior page locality — it actively worsens it.
  `sqlite3RunVacuum()` is type-unaware and should be considered for improvement.
  A type-aware VACUUM would make `range` prefetch far more effective than it
  currently is.
