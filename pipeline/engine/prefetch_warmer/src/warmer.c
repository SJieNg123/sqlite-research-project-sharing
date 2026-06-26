/*
 * warmer — stateless cold-start prefetch warmer (Level 1).
 *
 * Reads a hotset CSV (page_number,file_offset) and pulls those pages into the
 * OS page cache BEFORE SQLite opens the DB. Run as the harness post-cold-script
 * (separate process, its own fd) so there is no lock conflict (F1) and no second
 * data copy (F4): the scratch buffer is read-and-discard, only the OS page cache
 * is warmed; SQLite's later reads hit it naturally.
 *
 *   warmer <db> <hotset.csv> <page_size>
 *
 * env:
 *   WARM_MODE   = warm (default) | off          (off = baseline; same binary)
 *   WARM_METHOD = pread (default) | fadvise      (pread guarantees residency;
 *                                                 fadvise is best-effort hint)
 *
 * Prints to stderr:  warmer_us=<f> warmed_pages=<n> method=<m> mode=<m>
 */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <time.h>

static long long now_ns(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (long long)ts.tv_sec * 1000000000LL + ts.tv_nsec;
}

int main(int argc, char *argv[]) {
    if (argc != 4) {
        fprintf(stderr, "usage: %s <db> <hotset.csv> <page_size>\n", argv[0]);
        return 2;
    }
    const char *db = argv[1];
    const char *hotset = argv[2];
    int page_size = atoi(argv[3]);
    if (page_size <= 0) page_size = 4096;

    const char *mode = getenv("WARM_MODE");
    const char *method = getenv("WARM_METHOD");
    int do_warm = !(mode && strcmp(mode, "off") == 0);
    int use_pread = !(method && strcmp(method, "fadvise") == 0);

    long long t0 = now_ns();
    int warmed = 0;
    /* Split the preprocessing wall-clock into two terms so e2e can be reported under
     * both deployment models:
     *   open_us    = cold open(db)+fopen(hotset)+malloc setup. A warm / in-app process
     *                does NOT re-pay this (its DB handle is already open) -> exclude it
     *                for the "warm process, cold data" model.
     *   deliver_us = page-list iterate + per-page pread/fadvise loop = what an integrated
     *                prefetch actually costs (~ static prefetch_elapsed).
     *   warmer_us  = open_us + deliver_us = the standalone-warmer total (unchanged).
     * Measurement semantics are unchanged; we only add two timestamps + two stderr fields. */
    long long t_open_done = t0;

    if (do_warm) {
        int fd = open(db, O_RDONLY);
        if (fd < 0) { perror("open db"); return 1; }
        FILE *f = fopen(hotset, "r");
        if (!f) { perror("fopen hotset"); close(fd); return 1; }

        /* read-and-discard scratch (F4: not a data cache) */
        unsigned char *scratch = malloc(page_size);
        if (!scratch) { fclose(f); close(fd); return 1; }

        t_open_done = now_ns();                            /* end of open/setup term */

        char line[256];
        int header = 1;
        while (fgets(line, sizeof line, f)) {
            if (header) { header = 0; continue; }          /* skip CSV header */
            long long pn; long long off;
            if (sscanf(line, "%lld,%lld", &pn, &off) != 2) continue;
            if (use_pread) {
                if (pread(fd, scratch, page_size, off) >= 0) warmed++;
            } else {
                if (posix_fadvise(fd, off, page_size, POSIX_FADV_WILLNEED) == 0) warmed++;
            }
        }
        free(scratch);
        fclose(f);
        close(fd);
    }

    long long t1 = now_ns();
    fprintf(stderr, "warmer_us=%.2f open_us=%.2f deliver_us=%.2f warmed_pages=%d method=%s mode=%s\n",
            (t1 - t0) / 1000.0, (t_open_done - t0) / 1000.0, (t1 - t_open_done) / 1000.0, warmed,
            use_pread ? "pread" : "fadvise",
            do_warm ? "warm" : "off");
    return 0;
}
