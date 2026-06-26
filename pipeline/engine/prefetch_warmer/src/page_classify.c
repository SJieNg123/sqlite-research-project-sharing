/* page_classify — see page_classify.h. O(1), no I/O, no freelist walk (F2). */
#include "page_classify.h"

/* SQLite b-tree page-type flag byte values:
 *   0x05 interior table, 0x02 interior index  -> INTERNAL
 *   0x0D leaf table,     0x0A leaf index       -> LEAF
 * On page 1 the b-tree header follows the 100-byte file header, so the flag is
 * at buf[100]; on every other page it is at buf[0]. */
static unsigned char flag_byte(const unsigned char *buf, int is_page1) {
    return is_page1 ? buf[100] : buf[0];
}

int is_internal_node(const unsigned char *buf, int is_page1) {
    unsigned char f = flag_byte(buf, is_page1);
    return (f == 0x05 || f == 0x02);
}

int is_leaf_node(const unsigned char *buf, int is_page1) {
    unsigned char f = flag_byte(buf, is_page1);
    return (f == 0x0D || f == 0x0A);
}

page_class_t classify_page(const unsigned char *buf, int is_page1) {
    if (is_internal_node(buf, is_page1)) return PAGE_INTERNAL;
    if (is_leaf_node(buf, is_page1)) return PAGE_LEAF;
    return PAGE_OTHER;
}

unsigned int read_page_size_from_header(const unsigned char *buf) {
    unsigned int v = ((unsigned int)buf[16] << 8) | (unsigned int)buf[17];
    return (v == 1) ? 65536u : v;
}
