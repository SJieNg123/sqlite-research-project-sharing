#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <time.h>
#include <unistd.h>

#define MAX_INTERIOR 4096

static long long now_ns() {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (long long)ts.tv_sec * 1000000000LL + ts.tv_nsec;
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
        if (header) { header = 0; continue; }  /* skip header */
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

    fprintf(stderr, "interior pages found: %d\n", n_interior);
    fprintf(stderr, "strategy: %s\n", strategy);

    /* --- 3. execute prefetch strategy, measure time and syscall count --- */
    long long t0 = now_ns();
    int syscall_count = 0;
    int page_size = 4096;  /* SQLite default */

    if (use_perpage) {
        /* Strategy B: one madvise per interior page */
        for (int i = 0; i < n_interior; i++) {
            void *addr = (char *)map + offsets[i];
            madvise(addr, page_size, MADV_WILLNEED);
            syscall_count++;
        }
    } else {
        /* Strategy A: merge contiguous pages into ranges */
        /* First sort offsets */
        for (int i = 0; i < n_interior - 1; i++)
            for (int j = i + 1; j < n_interior; j++)
                if (offsets[j] < offsets[i]) {
                    long long tmp = offsets[i];
                    offsets[i] = offsets[j];
                    offsets[j] = tmp;
                }

        /* Merge contiguous ranges and madvise each */
        long long range_start = offsets[0];
        long long range_end   = offsets[0] + page_size;

        for (int i = 1; i < n_interior; i++) {
            if (offsets[i] == range_end) {
                /* contiguous, extend range */
                range_end += page_size;
            } else {
                /* gap found, flush current range */
                void *addr = (char *)map + range_start;
                size_t len = range_end - range_start;
                madvise(addr, len, MADV_WILLNEED);
                syscall_count++;
                range_start = offsets[i];
                range_end   = offsets[i] + page_size;
            }
        }
        /* flush last range */
        void *addr = (char *)map + range_start;
        size_t len = range_end - range_start;
        madvise(addr, len, MADV_WILLNEED);
        syscall_count++;
    }

    long long t1 = now_ns();

    fprintf(stderr, "syscall_count: %d\n", syscall_count);
    fprintf(stderr, "prefetch_time_us: %.2f\n", (t1 - t0) / 1000.0);

    /* stdout: machine-readable summary */
    printf("strategy,interior_pages,syscall_count,prefetch_time_us\n");
    printf("%s,%d,%d,%.2f\n",
           strategy, n_interior, syscall_count, (t1 - t0) / 1000.0);

    munmap(map, db_size);
    close(fd);
    return 0;
}
