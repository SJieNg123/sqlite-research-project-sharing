# Linux Kernel madvise.c — Key Function Notes (Week 12)

Source: `mm/madvise.c` (latest mainline kernel)

This document covers what actually happens inside the Linux kernel when you
call `madvise()` with `MADV_WILLNEED`, `MADV_COLD`, or `MADV_PAGEOUT`. These
three are the most relevant to the cold-start prefetch experiments in this
project.

---

## MADV_WILLNEED — `madvise_willneed()` (line 281)

### What it does

When your program calls `madvise(addr, len, MADV_WILLNEED)`, the kernel runs
`madvise_willneed()`. It does one main thing:

```c
vfs_fadvise(file, offset, end - start, POSIX_FADV_WILLNEED);
```

It passes the request down to the filesystem layer (VFS), which then schedules
an asynchronous read of the corresponding file data into the page cache.

### Key points

**It does not wait for the read to finish.**
The function unlocks the mmap lock, fires off the fadvise call, then returns
immediately. By the time your program runs the next line of code, the pages
may or may not have been loaded yet — it depends on how busy the I/O system
is.

This is why prefetching too many pages in our experiment made things worse.
With 92 pages to prefetch, the OS could not finish loading all of them before
the benchmark started. The first query ran into pages that were still being
loaded and had to wait anyway.

**It is just a hint.**
The kernel is not required to honour the request. If the system is under
memory pressure, it may ignore or partially complete the prefetch.

**It does not work on DAX devices.**
DAX (Direct Access) storage bypasses the page cache entirely, so
`MADV_WILLNEED` has no effect and the kernel ignores it silently.

### Why this matters for our experiments

`madvise(MADV_WILLNEED)` is asynchronous. The sweet spot of 5 pages works
because 5 pages takes ~94 μs to prefetch — fast enough that the OS finishes
loading them before the benchmark's first query runs. Prefetching 92 pages
takes ~2229 μs, so the benchmark starts before loading is complete.

---

## MADV_COLD — `madvise_cold()` (line 596)

### What it does

When your program calls `madvise(addr, len, MADV_COLD)`, the kernel runs
`madvise_cold()`, which walks through every page in the given range and does
two things to each resident page:

1. Clears the `PG_young` flag — marks the page as "not recently used"
2. Calls `folio_deactivate()` — moves the page from the **active LRU list**
   to the **inactive LRU list**

The Linux kernel keeps two LRU lists to decide which pages to evict when
memory is needed. Pages on the active list are considered important and are
kept longer. Pages on the inactive list are considered lower priority and will
be evicted first.

### Key points

**It does not immediately remove pages from memory.**
`MADV_COLD` only changes the priority of pages — it moves them closer to the
front of the eviction queue. The actual eviction happens later, when the kernel
decides it needs to free memory (handled by `kswapd` in the background).

This is why in our experiments, the resident page count did not drop to zero
immediately after calling `MADV_COLD`. The pages were still in memory — just
marked as low priority.

**It respects locked and special pages.**
The function checks `can_madv_lru_vma()` first. Pages that are locked in
memory (`VM_LOCKED`), huge pages (`VM_HUGETLB`), or special mappings
(`VM_PFNMAP`) are skipped entirely.

**It is also just a hint.**
If memory pressure never happens after the call, the pages may stay in memory
indefinitely. The kernel reclaim process decides when to actually evict them.

### Why this matters for our experiments

`MADV_COLD` simulates what Android's `ActivityManagerService` does to
background apps — it marks their pages as low priority so the OS can reclaim
them when memory is needed. In our experiments, we combined `MADV_COLD` with
`drop_caches` to get a reliable cold-start baseline, because `MADV_COLD` alone
does not guarantee pages are evicted.

---

## MADV_PAGEOUT — `madvise_pageout()` (line 627)

### What it does

`MADV_PAGEOUT` uses the same page-walking logic as `MADV_COLD`
(`madvise_cold_or_pageout_pte_range`), but with `pageout = true`. Instead of
just moving pages to the inactive list, it adds them directly to a reclaim
list and calls `reclaim_pages()` — triggering immediate eviction.

### Difference from MADV_COLD

| | MADV_COLD | MADV_PAGEOUT |
|--|-----------|--------------|
| Effect | Moves pages to inactive LRU | Forces immediate eviction |
| Speed | Page stays in memory for now | Page is removed right away |
| Strength | Hint — OS may ignore | Much more aggressive |

`MADV_PAGEOUT` is more forceful but also more disruptive. It is used in the
benchmark harness (`--cold-advice pageout` and `--cold-advice dontneed`) to
simulate a stronger cold-start condition than `MADV_COLD` alone.

---

## Summary

| advice | Kernel action | Immediate effect | Guaranteed? |
|--------|--------------|-----------------|-------------|
| `MADV_WILLNEED` | Schedules async read via VFS fadvise | Pages start loading in background | No — just a hint |
| `MADV_COLD` | Moves pages to inactive LRU list | Pages stay in memory, lower priority | No — eviction happens later |
| `MADV_PAGEOUT` | Immediately isolates and reclaims pages | Pages removed from memory | More reliable, but still not absolute |

All three are **hints to the kernel**, not hard commands. The kernel reserves
the right to ignore or partially honour them depending on system conditions.
Understanding this is essential for interpreting cold-start experiment results —
especially cases where residency does not drop to zero after a cold advice call.
