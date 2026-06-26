#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

#define MAX_INTERIOR 4096

static long long now_ns() {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (long long)ts.tv_sec * 1000000000LL + ts.tv_nsec;
}

/* qsort comparator for long long; matches prefetch_layers.c:18 cmp_ll. */
static int cmp_ll(const void *a, const void *b) {
    long long x = *(long long *)a, y = *(long long *)b;
    return (x > y) - (x < y);
}

/* Check how many of the given offsets are resident using mincore() */
static int count_resident(void *map, size_t db_size,
                           long long *offsets, int n, int page_size) {
    size_t n_os_pages = (db_size + page_size - 1) / page_size;
    unsigned char *vec = calloc(n_os_pages, 1);
    if (!vec) return -1;

    mincore(map, db_size, vec);

    int resident = 0;
    for (int i = 0; i < n; i++) {
        size_t os_page_idx = offsets[i] / page_size;
        if (os_page_idx < n_os_pages && (vec[os_page_idx] & 1))
            resident++;
    }
    free(vec);
    return resident;
}

int main(int argc, char *argv[]) {
    if (argc != 4) {
        fprintf(stderr,
            "Usage: %s <database.db> <classify_pages.csv> <strategy>\n"
            "  strategy: range   = one madvise per contiguous range\n"
            "            perpage = one madvise per interior page\n",
            argv[0]);
        return 1;
    }

    const char *db_path  = argv[1];
    const char *csv_path = argv[2];
    const char *strategy = argv[3];

    int use_range   = strcmp(strategy, "range")   == 0;
    int use_perpage = strcmp(strategy, "perpage") == 0;
    if (!use_range && !use_perpage) {
        fprintf(stderr, "error: strategy must be 'range' or 'perpage'\n");
        return 1;
    }

    int page_size = sysconf(_SC_PAGESIZE);

    /* --- 1. mmap the database --- */
    int fd = open(db_path, O_RDONLY);
    if (fd < 0) { perror("open"); return 1; }

    struct stat st;
    fstat(fd, &st);
    size_t db_size = st.st_size;

    void *map = mmap(NULL, db_size, PROT_READ, MAP_SHARED, fd, 0);
    if (map == MAP_FAILED) { perror("mmap"); return 1; }

    /* --- 2. read interior page offsets from CSV --- */
    FILE *f = fopen(csv_path, "r");
    if (!f) { perror("fopen csv"); return 1; }

    long long offsets[MAX_INTERIOR];
    int n_interior = 0;
    char line[256];
    int header = 1;

    while (fgets(line, sizeof(line), f)) {
        if (header) { header = 0; continue; }
        int page_number;
        char page_type[64];
        long long file_offset;
        if (sscanf(line, "%d,%63[^,],%lld",
                   &page_number, page_type, &file_offset) != 3)
            continue;
        if (strncmp(page_type, "interior", 8) == 0) {
            if (n_interior < MAX_INTERIOR)
                offsets[n_interior++] = file_offset;
        }
    }
    fclose(f);

    fprintf(stderr, "interior_pages_found: %d\n", n_interior);
    fprintf(stderr, "strategy: %s\n", strategy);

    /* --- 3. check residency BEFORE prefetch --- */
    int before = count_resident(map, db_size, offsets, n_interior, page_size);
    fprintf(stderr, "interior_resident_before_prefetch: %d/%d\n",
            before, n_interior);

    /* --- 4. execute prefetch, measure time and syscall count --- */
    long long t0 = now_ns();
    int syscall_count = 0;
    int sqlite_page_size = 4096;

    if (use_perpage) {
        for (int i = 0; i < n_interior; i++) {
            void *addr = (char *)map + offsets[i];
            madvise(addr, sqlite_page_size, MADV_WILLNEED);
            syscall_count++;
        }
    } else {
        /* sort offsets first (match prefetch_layers.c:62 — qsort, not O(n^2)) */
        qsort(offsets, n_interior, sizeof(long long), cmp_ll);

        long long range_start = offsets[0];
        long long range_end   = offsets[0] + sqlite_page_size;

        for (int i = 1; i < n_interior; i++) {
            if (offsets[i] == range_end) {
                range_end += sqlite_page_size;
            } else {
                madvise((char *)map + range_start,
                        range_end - range_start, MADV_WILLNEED);
                syscall_count++;
                range_start = offsets[i];
                range_end   = offsets[i] + sqlite_page_size;
            }
        }
        madvise((char *)map + range_start,
                range_end - range_start, MADV_WILLNEED);
        syscall_count++;
    }

    long long t1 = now_ns();

    fprintf(stderr, "syscall_count: %d\n", syscall_count);
    fprintf(stderr, "prefetch_time_us: %.2f\n", (t1 - t0) / 1000.0);

    /* --- 5. wait for async I/O to complete, then check residency --- */
    fprintf(stderr, "waiting 500ms for async I/O...\n");
    usleep(500000);  /* 500 ms */

    int after = count_resident(map, db_size, offsets, n_interior, page_size);
    fprintf(stderr, "interior_resident_after_prefetch: %d/%d (%.1f%%)\n",
            after, n_interior, 100.0 * after / n_interior);

    /* stdout: machine-readable */
    printf("strategy,interior_pages,syscall_count,prefetch_time_us,"
           "resident_before,resident_after,resident_pct\n");
    printf("%s,%d,%d,%.2f,%d,%d,%.1f\n",
           strategy, n_interior, syscall_count, (t1 - t0) / 1000.0,
           before, after, 100.0 * after / n_interior);

    munmap(map, db_size);
    close(fd);
    return 0;
}
