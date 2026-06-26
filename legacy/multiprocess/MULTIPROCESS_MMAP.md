# Multi-Process mmap Experiment (Week 12)

This experiment investigates whether SQLite's mmap-based I/O shares the OS
page cache across multiple processes, and how this compares to each process
maintaining its own private buffer pool.

---

## Background

When SQLite opens a database with `PRAGMA mmap_size > 0`, it maps the database
file into its address space using `mmap(MAP_SHARED)`. A key property of
`MAP_SHARED` is that all processes mapping the same file share the **same
physical pages** in the OS page cache. This means if one process brings a page
into memory, other processes can access it without triggering an additional
page fault.

The alternative is a private buffer pool (`PRAGMA mmap_size=0`,
`PRAGMA cache_size=N`), where each process independently caches pages in its
own heap memory. There is no sharing — every process must load the pages it
needs independently.

---

## Tools

### `multiprocess_residency.c` — MAP_SHARED page cache sharing test

Forks N child processes, each mapping the same database file with
`MAP_SHARED`. Each child reads a portion of the file to bring pages into the
cache. After all children exit, the parent calls `mincore()` to check how many
pages are resident — verifying whether the children's reads are visible to the
parent through the shared page cache.

**Build:**
```bash
gcc -O2 -Wall -o multiprocess_residency multiprocess_residency.c
```

**Usage:**
```bash
./multiprocess_residency <database.db> <num_processes>
```

**Example:**
```bash
sync && echo 3 | sudo tee /proc/sys/vm/drop_caches > /dev/null
./multiprocess_residency test.db 3
```

---

### `multiprocess_buffer_pool.c` — Private buffer pool RSS test

Forks N child processes, each opening the database with mmap disabled
(`PRAGMA mmap_size=0`) and a private buffer pool (`PRAGMA cache_size=2000`).
Each child runs 5000 random point queries to populate its buffer pool, then
reports its RSS via `getrusage()`.

**Build:**
```bash
gcc -O2 -Wall -o multiprocess_buffer_pool multiprocess_buffer_pool.c -lsqlite3
```

**Usage:**
```bash
./multiprocess_buffer_pool <database.db> <num_processes>
```

**Example:**
```bash
./multiprocess_buffer_pool test.db 3
```

---

## Workflow

```bash
# 1. Build both tools
gcc -O2 -Wall -o multiprocess_residency multiprocess_residency.c
gcc -O2 -Wall -o multiprocess_buffer_pool multiprocess_buffer_pool.c -lsqlite3

# 2. Run MAP_SHARED sharing test (clear cache first)
sync && echo 3 | sudo tee /proc/sys/vm/drop_caches > /dev/null
./multiprocess_residency test.db 3

# 3. Run private buffer pool test
./multiprocess_buffer_pool test.db 3
```

---

## Results

Database: `test.db` — 600k rows, 25613 pages (4 KB each), ~100 MB

### Experiment 1: MAP_SHARED page cache sharing

```
=== Multi-process mmap residency test ===
db=test.db  file_size=104910848  num_processes=3

[before_read]         pid=8050  resident_os_pages=0/25613
[after_child_read]    pid=8051  resident_os_pages=18765/25613
[after_child_read]    pid=8053  resident_os_pages=24584/25613
[after_child_read]    pid=8052  resident_os_pages=25613/25613
[parent_after_children] pid=8050  resident_os_pages=25613/25613
```

### Experiment 2: Private buffer pool RSS

```
=== Multi-process private buffer pool test ===
db=test.db  num_processes=3

[after_queries]  pid=8406  RSS=10440 KB
[after_queries]  pid=8407  RSS=10440 KB
[after_queries]  pid=8408  RSS=10440 KB
```

---

## Analysis

### Page cache IS shared across processes with MAP_SHARED

The parent process (pid 8050) never read any data itself, yet after all
children exited it saw **25613/25613 pages resident**. The children's reads
populated the OS page cache, and the parent could observe the result directly
through its own `MAP_SHARED` mapping. This confirms that `MAP_SHARED` mmap
causes all processes to share a single copy of the file's pages in the OS
page cache.

### Memory usage comparison

| Approach | Per-process memory | 3-process total | Scales with N processes? |
|----------|--------------------|-----------------|--------------------------|
| MAP_SHARED mmap | shared page cache | ~100 MB (fixed) | No — stays fixed |
| Private buffer pool | 10,440 KB each | ~30 MB | Yes — grows linearly |

At 3 processes, private buffer pools actually use less total memory because
each process only cached the pages it accessed (a subset of the full DB). But
as the number of processes grows, private buffer pools scale linearly while
`MAP_SHARED` stays fixed regardless of process count.

For example, with 10 processes accessing the full DB:
- `MAP_SHARED`: still ~100 MB total
- Private buffer pool: ~104 MB total (10 × 10.4 MB)

### Implication for cold-start prefetch

Because page cache is shared, if **one** process prefetches the interior pages
using `madvise(MADV_WILLNEED)`, all other processes benefit immediately —
their first queries will not page fault on those interior pages. This makes
prefetch an even more effective strategy in multi-process scenarios.

---

## Key Takeaways

- `MAP_SHARED` mmap causes all processes mapping the same file to share one
  copy of the page cache. A page loaded by any process is immediately visible
  to all others.
- Private buffer pools do not share memory across processes. Each process
  independently caches the pages it needs, and total RSS grows linearly with
  process count.
- In multi-process SQLite deployments, mmap's shared page cache is a
  significant advantage for memory efficiency at scale.
- Prefetching interior pages in one process benefits all processes sharing
  the same mmap mapping — making prefetch a worthwhile strategy even in
  multi-process workloads.
