// LD_PRELOAD 攔截器：strace 不在這台機器上，用它記錄 §D-5 關心的 syscall 順序。
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>
#include <stdarg.h>
#include <string.h>

static FILE *log_file(void) {
    static FILE *f;
    if (!f) {
        const char *p = getenv("AOS_TRACE_LOG");
        f = p ? fopen(p, "a") : stderr;
        if (!f) f = stderr;
    }
    return f;
}

// 只記我們關心的路徑，濾掉 vcpkg/so/locale 之類雜訊
static int interesting(const char *p) {
    if (!p) return 0;
    return strstr(p, ".aos") || strstr(p, "inst") || strstr(p, "turn") ||
           strstr(p, "version") || strstr(p, "tempd") || strstr(p, "head");
}

#define MAXFD 4096
static char fdpath[MAXFD][256];

int open(const char *path, int flags, ...) {
    static int (*real)(const char *, int, ...);
    if (!real) real = dlsym(RTLD_NEXT, "open");
    va_list ap; va_start(ap, flags); mode_t m = va_arg(ap, mode_t); va_end(ap);
    int fd = real(path, flags, m);
    if (fd >= 0 && fd < MAXFD) {
        snprintf(fdpath[fd], sizeof fdpath[fd], "%s", path ? path : "?");
        if (interesting(path))
            fprintf(log_file(), "open(%s)%s = %d\n", path,
                    (flags & O_DIRECTORY) ? " [DIR]" : "", fd);
    }
    return fd;
}

int openat(int dirfd, const char *path, int flags, ...) {
    static int (*real)(int, const char *, int, ...);
    if (!real) real = dlsym(RTLD_NEXT, "openat");
    va_list ap; va_start(ap, flags); mode_t m = va_arg(ap, mode_t); va_end(ap);
    int fd = real(dirfd, path, flags, m);
    if (fd >= 0 && fd < MAXFD) {
        snprintf(fdpath[fd], sizeof fdpath[fd], "%s", path ? path : "?");
        if (interesting(path))
            fprintf(log_file(), "openat(%s)%s = %d\n", path,
                    (flags & O_DIRECTORY) ? " [DIR]" : "", fd);
    }
    return fd;
}

int fsync(int fd) {
    static int (*real)(int);
    if (!real) real = dlsym(RTLD_NEXT, "fsync");
    int rc = real(fd);
    const char *p = (fd >= 0 && fd < MAXFD) ? fdpath[fd] : "?";
    if (interesting(p)) fprintf(log_file(), "  FSYNC(%s) = %d\n", p, rc);
    return rc;
}

int rename(const char *a, const char *b) {
    static int (*real)(const char *, const char *);
    if (!real) real = dlsym(RTLD_NEXT, "rename");
    int rc = real(a, b);
    if (interesting(a) || interesting(b))
        fprintf(log_file(), "RENAME(%s -> %s) = %d\n", a, b, rc);
    return rc;
}

int renameat2(int od, const char *a, int nd, const char *b, unsigned int fl) {
    static int (*real)(int, const char *, int, const char *, unsigned int);
    if (!real) real = dlsym(RTLD_NEXT, "renameat2");
    int rc = real(od, a, nd, b, fl);
    if (interesting(a) || interesting(b))
        fprintf(log_file(), "RENAMEAT2(%s -> %s, flags=%u) = %d\n", a, b, fl, rc);
    return rc;
}

int unlink(const char *p) {
    static int (*real)(const char *);
    if (!real) real = dlsym(RTLD_NEXT, "unlink");
    int rc = real(p);
    if (interesting(p)) fprintf(log_file(), "UNLINK(%s) = %d\n", p, rc);
    return rc;
}

int link(const char *a, const char *b) {
    static int (*real)(const char *, const char *);
    if (!real) real = dlsym(RTLD_NEXT, "link");
    int rc = real(a, b);
    if (interesting(a) || interesting(b))
        fprintf(log_file(), "LINK(%s -> %s) = %d\n", a, b, rc);
    return rc;
}
