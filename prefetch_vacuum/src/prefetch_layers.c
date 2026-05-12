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

int cmp_ll(const void *a, const void *b) {
    long long x = *(long long *)a, y = *(long long *)b;
    return (x > y) - (x < y);
}

int main(int argc, char *argv[]) {
    if (argc != 5) {
        fprintf(stderr,
            "Usage: %s <database.db> <classify_pages.csv> <n_pages> <page_size>\n"
            "  n_pages: how many interior pages to prefetch (sorted by file offset)\n",
            argv[0]);
        return 1;
    }

    const char *db_path   = argv[1];
    const char *csv_path  = argv[2];
    int n_prefetch        = atoi(argv[3]);
    int page_size         = atoi(argv[4]);

    int fd = open(db_path, O_RDONLY);
    if (fd < 0) { perror("open"); return 1; }
    struct stat st;
    fstat(fd, &st);
    size_t db_size = st.st_size;
    void *map = mmap(NULL, db_size, PROT_READ, MAP_SHARED, fd, 0);
    if (map == MAP_FAILED) { perror("mmap"); return 1; }

    FILE *f = fopen(csv_path, "r");
    if (!f) { perror("fopen"); return 1; }

    long long offsets[MAX_INTERIOR];
    int n_interior = 0;
    char line[256];
    int header = 1;
    while (fgets(line, sizeof(line), f)) {
        if (header) { header = 0; continue; }
        int pnum; char ptype[64]; long long off;
        if (sscanf(line, "%d,%63[^,],%lld", &pnum, ptype, &off) != 3) continue;
        if (strncmp(ptype, "interior", 8) == 0)
            if (n_interior < MAX_INTERIOR) offsets[n_interior++] = off;
    }
    fclose(f);

    /* sort by file offset (= layer order, root first) */
    qsort(offsets, n_interior, sizeof(long long), cmp_ll);

    if (n_prefetch > n_interior) n_prefetch = n_interior;

    long long t0 = now_ns();
    for (int i = 0; i < n_prefetch; i++)
        madvise((char *)map + offsets[i], page_size, MADV_WILLNEED);
    long long t1 = now_ns();

    printf("n_prefetch=%d syscalls=%d time_us=%.2f\n",
           n_prefetch, n_prefetch, (t1 - t0) / 1000.0);

    munmap(map, db_size);
    close(fd);
    return 0;
}
