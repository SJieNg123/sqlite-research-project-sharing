#include <stdio.h>
#include <stdlib.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>
#include <time.h>

static long long now_ns() {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (long long)ts.tv_sec * 1000000000LL + ts.tv_nsec;
}

void check_residency(void *map, size_t file_size, int os_page_size,
                     int sqlite_page_size, const char *label) {
    size_t n_os_pages = (file_size + os_page_size - 1) / os_page_size;
    unsigned char *vec = calloc(n_os_pages, 1);
    mincore(map, file_size, vec);

    int resident = 0;
    for (size_t i = 0; i < n_os_pages; i++)
        if (vec[i] & 1) resident++;

    int total_sqlite = file_size / sqlite_page_size;
    printf("[%s] pid=%d resident_os_pages=%d/%zu sqlite_pages~=%d\n",
           label, getpid(), resident, n_os_pages, total_sqlite);
    free(vec);
}

int main(int argc, char *argv[]) {
    if (argc != 3) {
        fprintf(stderr, "Usage: %s <database.db> <num_processes>\n", argv[0]);
        return 1;
    }
    const char *db_path = argv[1];
    int num_procs = atoi(argv[2]);
    int os_page_size = sysconf(_SC_PAGESIZE);
    int sqlite_page_size = 4096;

    /* Parent: open and mmap with MAP_SHARED */
    int fd = open(db_path, O_RDONLY);
    if (fd < 0) { perror("open"); return 1; }
    struct stat st;
    fstat(fd, &st);
    size_t file_size = st.st_size;

    void *map = mmap(NULL, file_size, PROT_READ, MAP_SHARED, fd, 0);
    if (map == MAP_FAILED) { perror("mmap"); return 1; }

    printf("=== Multi-process mmap residency test ===\n");
    printf("db=%s file_size=%zu num_processes=%d\n\n",
           db_path, file_size, num_procs);

    /* Clear cache before starting */
    madvise(map, file_size, MADV_DONTNEED);

    /* Check residency before any process reads */
    check_residency(map, file_size, os_page_size,
                    sqlite_page_size, "before_read");

    /* Fork child processes, each reads a portion of the DB */
    for (int i = 0; i < num_procs; i++) {
        pid_t pid = fork();
        if (pid == 0) {
            /* Child: read 1/N of the file to bring pages into cache */
            size_t chunk = file_size / num_procs;
            size_t start = i * chunk;
            volatile char sum = 0;
            for (size_t j = start; j < start + chunk && j < file_size; j++)
                sum += ((char *)map)[j];
            (void)sum;

            check_residency(map, file_size, os_page_size,
                            sqlite_page_size, "after_child_read");
            munmap(map, file_size);
            close(fd);
            exit(0);
        }
    }

    /* Wait for all children */
    for (int i = 0; i < num_procs; i++)
        wait(NULL);

    /* Parent checks residency after all children have read */
    check_residency(map, file_size, os_page_size,
                    sqlite_page_size, "parent_after_children");

    printf("\nIf resident count in parent matches children's reads,\n");
    printf("page cache IS shared across processes (MAP_SHARED working).\n");

    munmap(map, file_size);
    close(fd);
    return 0;
}
