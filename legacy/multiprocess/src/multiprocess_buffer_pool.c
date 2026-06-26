#include <stdio.h>
#include <stdlib.h>
#include <sys/wait.h>
#include <sys/resource.h>
#include <unistd.h>
#include <sqlite3.h>

void get_rss(const char *label) {
    struct rusage usage;
    getrusage(RUSAGE_SELF, &usage);
    printf("[%s] pid=%d RSS=%ld KB\n",
           label, getpid(), usage.ru_maxrss);
}

int main(int argc, char *argv[]) {
    if (argc != 3) {
        fprintf(stderr, "Usage: %s <database.db> <num_processes>\n", argv[0]);
        return 1;
    }
    const char *db_path = argv[1];
    int num_procs = atoi(argv[2]);

    printf("=== Multi-process private buffer pool test ===\n");
    printf("db=%s num_processes=%d\n\n", db_path, num_procs);

    for (int i = 0; i < num_procs; i++) {
        pid_t pid = fork();
        if (pid == 0) {
            sqlite3 *db;
            sqlite3_open(db_path, &db);
            /* 使用私有 buffer pool，不用 mmap */
            sqlite3_exec(db, "PRAGMA mmap_size=0;", NULL, NULL, NULL);
            sqlite3_exec(db, "PRAGMA cache_size=2000;", NULL, NULL, NULL);

            /* 跑一些查詢把 buffer pool 填滿 */
            sqlite3_stmt *stmt;
            sqlite3_prepare_v2(db,
                "SELECT id FROM items WHERE id = ?", -1, &stmt, NULL);
            srand(getpid());
            for (int q = 0; q < 5000; q++) {
                sqlite3_bind_int(stmt, 1, (rand() % 600000) + 1);
                sqlite3_step(stmt);
                sqlite3_reset(stmt);
            }
            sqlite3_finalize(stmt);

            get_rss("after_queries");
            sqlite3_close(db);
            exit(0);
        }
    }

    for (int i = 0; i < num_procs; i++)
        wait(NULL);

    printf("\nWith private buffer pool: each process holds its own copy.\n");
    printf("Total RSS = sum of all processes (no sharing).\n");
    return 0;
}
