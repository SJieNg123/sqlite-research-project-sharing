/* Unit test for page_classify — hand-crafted page images with known signatures,
 * including the page-1 special case and false-positive boundaries. */
#include "page_classify.h"
#include <stdio.h>
#include <string.h>

static int fails = 0;
#define CHECK(cond, msg) do { \
    if (!(cond)) { printf("FAIL: %s\n", msg); fails++; } \
} while (0)

int main(void) {
    unsigned char p[65536];

    /* Non-page-1 pages: flag at buf[0]. */
    memset(p, 0, sizeof p);
    p[0] = 0x05; CHECK(classify_page(p, 0) == PAGE_INTERNAL, "0x05 interior table -> INTERNAL");
    p[0] = 0x02; CHECK(classify_page(p, 0) == PAGE_INTERNAL, "0x02 interior index -> INTERNAL");
    p[0] = 0x0D; CHECK(classify_page(p, 0) == PAGE_LEAF,     "0x0D leaf table -> LEAF");
    p[0] = 0x0A; CHECK(classify_page(p, 0) == PAGE_LEAF,     "0x0A leaf index -> LEAF");
    p[0] = 0x00; CHECK(classify_page(p, 0) == PAGE_OTHER,    "0x00 -> OTHER");
    p[0] = 0xFF; CHECK(classify_page(p, 0) == PAGE_OTHER,    "0xFF -> OTHER");

    /* Page 1: real flag lives at buf[100], buf[0] is the 'S' of "SQLite...". */
    memset(p, 0, sizeof p);
    memcpy(p, "SQLite format 3", 15);   /* buf[0]=='S' (0x53) must be ignored */
    p[100] = 0x05; CHECK(classify_page(p, 1) == PAGE_INTERNAL, "page1: flag@100=0x05 -> INTERNAL");
    p[100] = 0x0D; CHECK(classify_page(p, 1) == PAGE_LEAF,     "page1: flag@100=0x0D -> LEAF");
    CHECK(classify_page(p, 1) != PAGE_OTHER, "page1: must read buf[100] not buf[0]");

    /* page_size from header: offset 16-17 big-endian; 1 => 65536. */
    memset(p, 0, sizeof p);
    p[16] = 0x10; p[17] = 0x00; CHECK(read_page_size_from_header(p) == 4096,  "page_size 0x1000 = 4096");
    p[16] = 0x00; p[17] = 0x01; CHECK(read_page_size_from_header(p) == 65536, "page_size 1 = 65536 special");
    p[16] = 0x40; p[17] = 0x00; CHECK(read_page_size_from_header(p) == 16384, "page_size 0x4000 = 16384");

    if (fails == 0) { printf("page_classify: ALL TESTS PASSED\n"); return 0; }
    printf("page_classify: %d FAILED\n", fails); return 1;
}
