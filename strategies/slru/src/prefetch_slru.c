/*
 * prefetch_slru.c
 *
 * Strategy 4 — SLRU-approximated prefetch.
 *
 * Reads a residency CSV produced by residency_checker (after a warmup
 * workload pass) and madvise(MADV_WILLNEED) every page that was resident.
 * The resident set approximates the SLRU "protected" segment — pages that
 * were actually touched by the workload, regardless of access frequency.
 *
 * Usage:
 *   prefetch_slru <database.db> <residency.csv> <page_size>
 *
 * Output (stderr): "n_prefetch=<K> syscalls=<K> time_us=<...>"
 */

#define _GNU_SOURCE

#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

static long long now_ns(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (long long)ts.tv_sec * 1000000000LL + ts.tv_nsec;
}

int main(int argc, char *argv[]) {
    if (argc != 4) {
        fprintf(stderr,
            "Usage: %s <database.db> <residency.csv> <page_size>\n",
            argv[0]);
        return 1;
    }

    const char *db_path  = argv[1];
    const char *csv_path = argv[2];
    int page_size        = atoi(argv[3]);

    int fd = open(db_path, O_RDONLY);
    if (fd < 0) { perror("open"); return 1; }
    struct stat st;
    if (fstat(fd, &st) != 0) { perror("fstat"); close(fd); return 1; }
    size_t db_size = (size_t)st.st_size;
    void *map = mmap(NULL, db_size, PROT_READ, MAP_SHARED, fd, 0);
    if (map == MAP_FAILED) { perror("mmap"); close(fd); return 1; }

    FILE *f = fopen(csv_path, "r");
    if (!f) { perror("fopen"); munmap(map, db_size); close(fd); return 1; }

    char line[256];
    int header_skipped = 0;
    int n_hot = 0;
    long long t0 = now_ns();
    while (fgets(line, sizeof(line), f)) {
        if (!header_skipped) { header_skipped = 1; continue; }
        int pnum, resident;
        if (sscanf(line, "%d,%d", &pnum, &resident) != 2) continue;
        if (!resident) continue;
        long long off = (long long)(pnum - 1) * page_size;
        if ((size_t)off + page_size > db_size) continue;
        if (madvise((char *)map + off, page_size, MADV_WILLNEED) == 0) {
            n_hot++;
        }
    }
    long long t1 = now_ns();
    fclose(f);

    fprintf(stderr, "n_prefetch=%d syscalls=%d time_us=%.2f\n",
            n_hot, n_hot, (t1 - t0) / 1000.0);

    munmap(map, db_size);
    close(fd);
    return 0;
}
