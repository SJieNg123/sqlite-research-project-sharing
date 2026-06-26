#define _GNU_SOURCE
#include <fcntl.h>
#include <stdio.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>
int main(int argc, char **argv) {
    int fd = open(argv[1], O_RDONLY);
    struct stat st; fstat(fd, &st);
    size_t n = st.st_size;
    void *m = mmap(NULL, n, PROT_READ, MAP_SHARED, fd, 0);
    size_t pages = (n + 4095) / 4096;
    unsigned char *vec = malloc(pages);
    mincore(m, n, vec);
    size_t r = 0;
    for (size_t i = 0; i < pages; i++) if (vec[i] & 1) r++;
    printf("%s: %zu/%zu resident\n", argv[1], r, pages);
    munmap(m, n); close(fd); return 0;
}
