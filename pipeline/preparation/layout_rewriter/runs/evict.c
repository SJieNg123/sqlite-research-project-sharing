/* evict <file>... — drop each file from the OS page cache via posix_fadvise. */
#define _GNU_SOURCE
#include <fcntl.h>
#include <stdio.h>
#include <unistd.h>
int main(int argc, char **argv) {
    int rc = 0;
    for (int i = 1; i < argc; i++) {
        int fd = open(argv[i], O_RDONLY);
        if (fd < 0) { perror(argv[i]); rc = 1; continue; }
        fsync(fd);
        if (posix_fadvise(fd, 0, 0, POSIX_FADV_DONTNEED) != 0) {
            perror("posix_fadvise");
            rc = 1;
        }
        close(fd);
    }
    return rc;
}
