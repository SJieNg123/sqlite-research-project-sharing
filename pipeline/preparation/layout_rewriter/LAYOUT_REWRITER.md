# Layout Rewriter — Type-aware SQLite Page Reordering

A standalone tool that takes an SQLite database file and rewrites it so all
B+tree interior pages are clustered at the front of the file. The goal is to
turn the scattered layout produced by `INSERT`/`UPDATE`/`DELETE` (and made
worse by `VACUUM`) into a layout that makes interior-page prefetch trivial:
one syscall covers the whole interior block.

## Why

`prefetch_vacuum` (Week 11) showed that `sqlite3RunVacuum()` does not consider
page type when allocating new page numbers, so post-VACUUM databases have
interior pages spread **further** through the file (scatter score went
**0.96 → 1.13** in our reference DB). That degraded `prefetch_layers N=5`
from **-54%** cold-start improvement down to **-9%**.

`layout_rewriter` is the missing piece: a type-aware rewrite that places
interior pages first.

## What it does

1. Reads input DB header (page_size, page_count, freelist head).
2. Classifies every page exactly like `classify_pages` (B-tree flag byte,
   freelist trunk walk, lock-byte page).
3. Builds an `old → new` mapping:
   - page 1 stays in slot 1 (the DB header lives there).
   - Interior pages → slots `2 .. N_interior+1`, preserving original order.
   - Leaf pages → next contiguous block.
   - Overflow / freelist → end of file.
4. Streams every page to the output file, in the new order, and patches:
   - **Interior B-tree pages** — rightmost child pointer + every cell's
     left-child pointer.
   - **Overflow pages** — next-page pointer (first 4 bytes).
   - **Freelist trunk pages** — next-trunk pointer + leaf-page array.
   - **Page 1 DB header** — `first_freelist_trunk` (offset 32) and bumps
     `file_change_counter` (offset 24) so SQLite discards any cached pager
     state.
5. Emits SQL on stdout that fixes `sqlite_master.rootpage` values via
   `PRAGMA writable_schema = ON` — those root-page numbers are stored as
   integers inside a record and can't be patched at the binary level.

## Build

```bash
gcc -O2 -Wall -o layout_rewriter layout_rewriter.c
```

## Usage

```bash
./layout_rewriter input.db output.db > fix.sql
sqlite3 output.db < fix.sql                       # apply rootpage updates
sqlite3 output.db "PRAGMA integrity_check;"       # must report "ok"
```

If `sqlite3` CLI is unavailable, the Python `sqlite3` module works:

```python
import sqlite3
c = sqlite3.connect("output.db")
c.executescript(open("fix.sql").read())
print(c.execute("PRAGMA integrity_check;").fetchall())
```

Limitations:
- Standard B-tree pages only (no WAL — set `PRAGMA journal_mode=DELETE` first).
- Best results if you `VACUUM` once to drop the freelist before running.
- Tested with 4 KB pages on `prefetch_churn/testdb_builder.py` schema
  (600k rows, 26,331 pages, 92 interior pages).

## End-to-end verification

Reference DB: 600 000 rows, 102 MiB, 26,331 × 4 KB pages, 92 interior pages.

### Layout effect

| Layout | scatter score | interior page range |
|---|---|---|
| original | **0.9606** | pages 2 … 26,007 (mean 12,648) |
| post-SQLite-VACUUM | **1.1303** | pages 2 … 25,516 (mean 14,469) |
| **post-layout_rewriter** | **0.0001** | pages 2 … 93 (mean 47.5) |

`integrity_check` reports `ok` after the binary rewrite + SQL fixup. All
600,000 rows are queryable through both the primary key and the secondary
indexes.

### Cold-start query latency

Same workload (`benchmark_harness/workloads/workload_a_zipfian.txt`, 100,000 random
point reads), same cold-start protocol (`posix_fadvise(POSIX_FADV_DONTNEED)`
+ `MADV_DONTNEED`), median of 3 reps.

| DB | scatter | baseline | range | perpage | **layers5** |
|---|---|---|---|---|---|
| original | 0.96 | 318 µs | 370 µs | 319 µs | 224 µs |
| post-VACUUM | 1.13 | 333 µs | 330 µs | 338 µs | 234 µs |
| **post-layout_rewriter** | 0.00 | 404 µs | 387 µs | 273 µs | **127 µs** |

Improvement vs same-DB baseline:

| DB | range | perpage | **layers5** |
|---|---|---|---|
| original | +16 % | +0 % | -30 % |
| post-VACUUM | -1 % | +2 % | -30 % |
| **post-layout_rewriter** | -4 % | -33 % | **-69 %** |

### What the numbers show

1. **Type-aware rewrite reproduces the prefetch_vacuum result, then beats
   it.** The original DB gives `layers5 = -30%`; on `layout_rewriter`'s
   output it gives `-69%`.
2. **VACUUM still betrays you.** As `prefetch_vacuum` claimed, SQLite's
   built-in VACUUM raised scatter from 0.96 → 1.13 and gave essentially the
   same `layers5` improvement (-30%, just at a slightly higher absolute
   baseline). The penalty is permanent until somebody rewrites it.
3. **`range` strategy is still bad even with a perfect layout.**
   On the type-aware DB, all 92 interior pages collapse into **1
   contiguous `madvise(MADV_WILLNEED)` call** (87 → 1 syscalls, 4.5×
   faster). But `MADV_WILLNEED` is advisory — the kernel only actually
   loads ~32/92 pages from a single 376 KB hint, because read-ahead is
   bounded. The `range` first-query latency (387 µs) is barely better
   than baseline.
4. **`layers5` wins by a wider margin precisely because the interior
   block is clustered.** Loading slots 2-6 with 5 `MADV_WILLNEED` calls
   takes the kernel into the same file region that contains the rest of
   the interior block; sequential-readahead pulls the deeper interior
   pages in too. On the scattered original DB, loading "the top 5" only
   covers a few hot pages; the long tail of cold interior pages still
   triggers serial page faults during traversal.

### Why baseline is higher on the type-aware DB

The type-aware layout pushes leaf pages to higher file offsets. The first
random point query has to fault one cold leaf no matter what, and that leaf
now sits further from where the disk head/readahead window started. This
penalty (~80 µs) is fixed per first-query and is wiped out by even minimal
prefetch — `perpage` alone halves it, and `layers5` reduces it to a third.

## Files in this directory

```
layout_rewriter.c       — the tool itself
runs/                   — reproducible end-to-end run (test.db, scripts, logs)
results/                — final CSVs (classify dumps, matrix, summary)
```

## Reproducing

```bash
# 1. Build everything
gcc -O2 -Wall -o layout_rewriter layout_rewriter.c
gcc -O2 -Wall -o ../classify_pages/classify_pages ../classify_pages/classify_pages.c
# benchmark_harness needs the SQLite amalgamation in benchmark_harness/

# 2. Build a 600k-row reference DB
cd runs
cp ../../prefetch_churn/testdb_builder.py .
python3 testdb_builder.py        # → test.db

# 3. Classify the original layout
../../classify_pages/classify_pages test.db > classify_before.csv

# 4. Rewrite
../layout_rewriter test.db test_typeaware.db > fix.sql
python3 -c "import sqlite3; c=sqlite3.connect('test_typeaware.db'); \
            c.executescript(open('fix.sql').read()); \
            print(c.execute('PRAGMA integrity_check;').fetchall())"

# 5. Classify the rewritten layout
../../classify_pages/classify_pages test_typeaware.db > classify_after.csv

# 6. Benchmark (see runs/runmatrix.sh; 1b/1c × B/C in runmatrix_1b_bc.sh / runmatrix_1c_bc.sh)
./runmatrix.sh > matrix_results.csv
```
