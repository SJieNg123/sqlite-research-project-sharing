/*
 * trav_bench — L3/L4 online (during-traversal) prefetch measurement.
 *
 * A SQLite VFS shim wrapping the default unix VFS. Its xRead, after reading an
 * INTERIOR b-tree page, parses that page's child page pointers and prefetches
 * them — "pointer-ahead": kick off the next level's I/O while SQLite is still
 * parsing the current page. Two modes:
 *   ahead  (L3): posix_fadvise(WILLNEED) each child  — async hint, non-blocking
 *   fanout (L4): pread each child into scratch        — batch, forces residency
 *
 * This is the *online* counterpart to the pre-open warmer (warmer.c): instead of
 * a fixed pre-loaded hotset, it follows the actual tree pointers as the query
 * descends. Still F4-safe (scratch read-and-discard, only warms OS page cache)
 * and F1-safe (one read-only prefetch fd opened at startup, never closed mid-run).
 *
 *   trav_bench <db> <key> <reps>
 * env WARM_MODE = off (default) | ahead | fanout
 *
 * Each rep: fadvise(DONTNEED) the whole file (cold) -> open via shim VFS ->
 * SELECT payload FROM items WHERE id=<key> -> print first-query latency (us).
 */
#define _GNU_SOURCE
#include "sqlite3.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <time.h>

static sqlite3_vfs *g_parent;
static int  g_pagesize = 4096;
static int  g_prefetch_fd = -1;
static int  g_mode = 0;          /* 0 off, 1 ahead(fadvise), 2 fanout(pread) */
static long g_prefetched = 0;

static long long now_ns(void){
    struct timespec ts; clock_gettime(CLOCK_MONOTONIC,&ts);
    return (long long)ts.tv_sec*1000000000LL+ts.tv_nsec;
}

/* Parse an interior page's children and prefetch them. buf is a g_pagesize image
 * read from file offset ofst. (Interior flag 0x05 table / 0x02 index.) */
static void prefetch_children(const unsigned char *buf, sqlite3_int64 ofst){
    int is_page1 = (ofst==0);
    const unsigned char *hdr = is_page1 ? buf+100 : buf;
    unsigned char type = hdr[0];
    if(type!=0x05 && type!=0x02) return;               /* only interior pages */
    int ncell = (hdr[3]<<8)|hdr[4];
    unsigned int right = ((unsigned)hdr[8]<<24)|((unsigned)hdr[9]<<16)|((unsigned)hdr[10]<<8)|hdr[11];
    /* cell pointer array: starts right after the 12-byte interior header */
    int cpa = (is_page1?100:0) + 12;
    static unsigned char scratch[65536];
    /* rightmost child first */
    unsigned int kids[2049]; int nk=0;
    if(right) kids[nk++]=right;
    for(int i=0;i<ncell && nk<2048;i++){
        int o = cpa + 2*i;
        if(o+1 >= g_pagesize) break;
        int cpo = (buf[o]<<8)|buf[o+1];
        if(cpo<0 || cpo+4 > g_pagesize) continue;
        unsigned int ch = ((unsigned)buf[cpo]<<24)|((unsigned)buf[cpo+1]<<16)|((unsigned)buf[cpo+2]<<8)|buf[cpo+3];
        if(ch) kids[nk++]=ch;
    }
    for(int i=0;i<nk;i++){
        sqlite3_int64 off = (sqlite3_int64)(kids[i]-1) * g_pagesize;
        if(off<0) continue;
        if(g_mode==1) posix_fadvise(g_prefetch_fd, off, g_pagesize, POSIX_FADV_WILLNEED);
        else if(g_mode==2) { if(pread(g_prefetch_fd, scratch, g_pagesize, off) < 0) {} }
        g_prefetched++;
    }
}

/* ---- shim file: wraps the real unix file, overrides only xRead ---- */
typedef struct ShimFile { sqlite3_file base; sqlite3_file *real; } ShimFile;
#define REAL(f) (((ShimFile*)(f))->real)

static int shRead(sqlite3_file *f,void *b,int n,sqlite3_int64 o){
    int rc = REAL(f)->pMethods->xRead(REAL(f),b,n,o);
    if(rc==SQLITE_OK && n==g_pagesize && g_mode!=0) prefetch_children((const unsigned char*)b,o);
    return rc;
}
static int shClose(sqlite3_file *f){
    int rc=REAL(f)->pMethods->xClose(REAL(f));
    sqlite3_free(REAL(f)); return rc;
}
static int shWrite(sqlite3_file *f,const void*b,int n,sqlite3_int64 o){return REAL(f)->pMethods->xWrite(REAL(f),b,n,o);}
static int shTrunc(sqlite3_file *f,sqlite3_int64 s){return REAL(f)->pMethods->xTruncate(REAL(f),s);}
static int shSync(sqlite3_file *f,int g){return REAL(f)->pMethods->xSync(REAL(f),g);}
static int shFsize(sqlite3_file *f,sqlite3_int64*s){return REAL(f)->pMethods->xFileSize(REAL(f),s);}
static int shLock(sqlite3_file *f,int l){return REAL(f)->pMethods->xLock(REAL(f),l);}
static int shUnlock(sqlite3_file *f,int l){return REAL(f)->pMethods->xUnlock(REAL(f),l);}
static int shCheck(sqlite3_file *f,int*r){return REAL(f)->pMethods->xCheckReservedLock(REAL(f),r);}
static int shFctl(sqlite3_file *f,int op,void*a){return REAL(f)->pMethods->xFileControl(REAL(f),op,a);}
static int shSector(sqlite3_file *f){return REAL(f)->pMethods->xSectorSize(REAL(f));}
static int shDevc(sqlite3_file *f){return REAL(f)->pMethods->xDeviceCharacteristics(REAL(f));}

static sqlite3_io_methods g_methods;   /* filled in main (version 1: no shm/mmap) */

static int shOpen(sqlite3_vfs *v,sqlite3_filename name,sqlite3_file *f,int flags,int *out){
    ShimFile *s=(ShimFile*)f;
    s->real=(sqlite3_file*)sqlite3_malloc(g_parent->szOsFile);
    if(!s->real) return SQLITE_NOMEM;
    memset(s->real,0,g_parent->szOsFile);
    int rc=g_parent->xOpen(g_parent,name,s->real,flags,out);
    if(rc!=SQLITE_OK){ sqlite3_free(s->real); return rc; }
    s->base.pMethods = REAL(f)->pMethods ? &g_methods : NULL;
    return SQLITE_OK;
}
/* all other vfs methods delegate straight to parent */
static int shDelete(sqlite3_vfs*v,const char*z,int s){return g_parent->xDelete(g_parent,z,s);}
static int shAccess(sqlite3_vfs*v,const char*z,int f,int*r){return g_parent->xAccess(g_parent,z,f,r);}
static int shFullPath(sqlite3_vfs*v,const char*z,int n,char*o){return g_parent->xFullPathname(g_parent,z,n,o);}

int main(int argc,char**argv){
    if(argc!=4){ fprintf(stderr,"usage: %s <db> <key> <reps>\n",argv[0]); return 2; }
    const char *db=argv[1]; long key=atol(argv[2]); int reps=atoi(argv[3]);
    const char *m=getenv("WARM_MODE");
    g_mode = (m&&!strcmp(m,"ahead"))?1 : (m&&!strcmp(m,"fanout"))?2 : 0;

    g_parent = sqlite3_vfs_find(NULL);
    g_pagesize = 4096;
    g_prefetch_fd = open(db,O_RDONLY);
    if(g_prefetch_fd<0){ perror("open db"); return 1; }

    g_methods.iVersion=1;
    g_methods.xClose=shClose; g_methods.xRead=shRead; g_methods.xWrite=shWrite;
    g_methods.xTruncate=shTrunc; g_methods.xSync=shSync; g_methods.xFileSize=shFsize;
    g_methods.xLock=shLock; g_methods.xUnlock=shUnlock; g_methods.xCheckReservedLock=shCheck;
    g_methods.xFileControl=shFctl; g_methods.xSectorSize=shSector; g_methods.xDeviceCharacteristics=shDevc;

    static sqlite3_vfs vfs;
    vfs = *g_parent;
    vfs.zName="trav_shim";
    vfs.szOsFile=sizeof(ShimFile);
    vfs.pNext=NULL;
    vfs.xOpen=shOpen; vfs.xDelete=shDelete; vfs.xAccess=shAccess; vfs.xFullPathname=shFullPath;
    sqlite3_vfs_register(&vfs,0);

    char sql[128];
    snprintf(sql,sizeof sql,"SELECT payload FROM items WHERE id=%ld",key);

    for(int r=0;r<reps;r++){
        /* cold: drop the whole file from page cache (clean pages, no root needed) */
        posix_fadvise(g_prefetch_fd,0,0,POSIX_FADV_DONTNEED);
        g_prefetched=0;
        sqlite3 *dbh;
        if(sqlite3_open_v2(db,&dbh,SQLITE_OPEN_READONLY,"trav_shim")!=SQLITE_OK){
            fprintf(stderr,"open fail: %s\n",sqlite3_errmsg(dbh)); return 1;
        }
        sqlite3_stmt *st;
        sqlite3_prepare_v2(dbh,sql,-1,&st,NULL);   /* prepare reads schema (page1) */
        long long t0=now_ns();
        int sc=sqlite3_step(st);                    /* THE first query */
        long long t1=now_ns();
        (void)sc;
        sqlite3_finalize(st);
        sqlite3_close(dbh);
        printf("%s,%d,%.2f,%ld\n", m?m:"off", r+1, (t1-t0)/1000.0, g_prefetched);
    }
    close(g_prefetch_fd);
    return 0;
}
