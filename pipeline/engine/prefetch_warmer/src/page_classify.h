/*
 * page_classify — O(1), byte-signature-only SQLite page classifier.
 *
 * Shared by the runtime VFS (shadow tagging) and offline tooling. Looks ONLY at
 * the b-tree page-type flag byte; does NO I/O and does NOT walk the freelist
 * (red lines F2). It is a heuristic: a non-b-tree page whose flag byte happens
 * to equal a b-tree value is a false positive — callers must not assume it is
 * exact (Phase A3 quantifies precision/recall against classify_pages.c oracle).
 */
#ifndef PAGE_CLASSIFY_H
#define PAGE_CLASSIFY_H

typedef enum {
    PAGE_OTHER = 0,
    PAGE_INTERNAL = 1,
    PAGE_LEAF = 2
} page_class_t;

/* buf points at the start of a page image. is_page1 != 0 when this is page 1
 * (iOfst == 0), whose b-tree header sits AFTER the 100-byte file header. */
int is_internal_node(const unsigned char *buf, int is_page1);
int is_leaf_node(const unsigned char *buf, int is_page1);
page_class_t classify_page(const unsigned char *buf, int is_page1);

/* Page size from the file header: offset 16, big-endian 2-byte. The special
 * value 1 means 65536. buf must be page 1 (contains the 100-byte header). */
unsigned int read_page_size_from_header(const unsigned char *buf);

#endif /* PAGE_CLASSIFY_H */
