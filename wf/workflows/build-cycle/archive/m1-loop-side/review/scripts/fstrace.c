/* strace 替身：LD_PRELOAD 攔截 libc 的檔案系統呼叫，把序列寫到 $FSTRACE_LOG。
 * 本機沒有 strace，用這個做鏡頭 2 的對抗驗證。 */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

static int log_fd = -1;
static __thread int guard = 0;

static int (*r_open)(const char *, int, ...);
static int (*r_openat)(int, const char *, int, ...);
static int (*r_close)(int);
static int (*r_fsync)(int);
static int (*r_fdatasync)(int);
static int (*r_rename)(const char *, const char *);
static int (*r_renameat2)(int, const char *, int, const char *, unsigned int);
static int (*r_link)(const char *, const char *);
static int (*r_unlink)(const char *);
static int (*r_unlinkat)(int, const char *, int);
static int (*r_mkdirat)(int, const char *, mode_t);

static void init(void) {
    if (r_open) return;
    r_open = dlsym(RTLD_NEXT, "open");
    r_openat = dlsym(RTLD_NEXT, "openat");
    r_close = dlsym(RTLD_NEXT, "close");
    r_fsync = dlsym(RTLD_NEXT, "fsync");
    r_fdatasync = dlsym(RTLD_NEXT, "fdatasync");
    r_rename = dlsym(RTLD_NEXT, "rename");
    r_renameat2 = dlsym(RTLD_NEXT, "renameat2");
    r_link = dlsym(RTLD_NEXT, "link");
    r_unlink = dlsym(RTLD_NEXT, "unlink");
    r_unlinkat = dlsym(RTLD_NEXT, "unlinkat");
    r_mkdirat = dlsym(RTLD_NEXT, "mkdirat");
    const char *path = getenv("FSTRACE_LOG");
    if (path && r_open)
        log_fd = r_open(path, O_WRONLY | O_CREAT | O_APPEND | O_CLOEXEC, 0666);
}

/* 只記我們關心的路徑（世界資料夾），避免動態連結器的雜訊淹掉序列。 */
static int interesting(const char *p) {
    if (!p) return 0;
    const char *filter = getenv("FSTRACE_FILTER");
    if (!filter) return 1;
    return strstr(p, filter) != NULL;
}

static void emit(const char *fmt, ...) {
    if (log_fd < 0) return;
    char buf[1024];
    int n = snprintf(buf, sizeof(buf), "[%d] ", (int)getpid());
    va_list ap;
    va_start(ap, fmt);
    n += vsnprintf(buf + n, sizeof(buf) - (size_t)n, fmt, ap);
    va_end(ap);
    if (n > 0 && (size_t)n < sizeof(buf) - 1) { buf[n] = '\n'; n++; }
    ssize_t ignored = write(log_fd, buf, (size_t)n);
    (void)ignored;
}

/* fd -> 路徑，供 fsync 顯示對象 */
#define FDMAX 4096
static char *fdpath[FDMAX];

static void note_fd(int fd, const char *path) {
    if (fd < 0 || fd >= FDMAX) return;
    free(fdpath[fd]);
    fdpath[fd] = path ? strdup(path) : NULL;
}

int open(const char *path, int flags, ...) {
    init();
    mode_t mode = 0;
    if (flags & (O_CREAT | O_TMPFILE)) {
        va_list ap; va_start(ap, flags); mode = va_arg(ap, mode_t); va_end(ap);
    }
    int fd = r_open(path, flags, mode);
    if (!guard) {
        guard = 1;
        if (interesting(path)) {
            note_fd(fd, path);
            emit("open(\"%s\", 0x%x) = %d", path, flags, fd);
        }
        guard = 0;
    }
    return fd;
}

int openat(int dirfd, const char *path, int flags, ...) {
    init();
    mode_t mode = 0;
    if (flags & (O_CREAT | O_TMPFILE)) {
        va_list ap; va_start(ap, flags); mode = va_arg(ap, mode_t); va_end(ap);
    }
    int fd = r_openat(dirfd, path, flags, mode);
    if (!guard) {
        guard = 1;
        const char *dp = (dirfd >= 0 && dirfd < FDMAX && fdpath[dirfd]) ? fdpath[dirfd] : NULL;
        if (interesting(path) || (dp && interesting(dp))) {
            char full[512];
            if (dp) snprintf(full, sizeof(full), "%s/%s", dp, path);
            else snprintf(full, sizeof(full), "%s", path);
            note_fd(fd, full);
            emit("openat(%s, \"%s\", 0x%x) = %d", dp ? dp : "AT_FDCWD", path, flags, fd);
        }
        guard = 0;
    }
    return fd;
}

int close(int fd) {
    init();
    char *p = (fd >= 0 && fd < FDMAX) ? fdpath[fd] : NULL;
    if (p && !guard) { guard = 1; emit("close(%d) [%s]", fd, p); guard = 0; }
    if (fd >= 0 && fd < FDMAX) { free(fdpath[fd]); fdpath[fd] = NULL; }
    return r_close(fd);
}

int fsync(int fd) {
    init();
    int rc = r_fsync(fd);
    if (!guard) {
        guard = 1;
        const char *p = (fd >= 0 && fd < FDMAX) ? fdpath[fd] : NULL;
        if (p) emit("FSYNC(%d) [%s] = %d", fd, p, rc);
        guard = 0;
    }
    return rc;
}

int fdatasync(int fd) {
    init();
    int rc = r_fdatasync(fd);
    if (!guard) {
        guard = 1;
        const char *p = (fd >= 0 && fd < FDMAX) ? fdpath[fd] : NULL;
        if (p) emit("FDATASYNC(%d) [%s] = %d", fd, p, rc);
        guard = 0;
    }
    return rc;
}

int rename(const char *from, const char *to) {
    init();
    int rc = r_rename(from, to);
    if (!guard) { guard = 1; if (interesting(from)) emit("RENAME(\"%s\", \"%s\") = %d", from, to, rc); guard = 0; }
    return rc;
}

int renameat2(int od, const char *from, int nd, const char *to, unsigned int flags) {
    init();
    int rc = r_renameat2(od, from, nd, to, flags);
    if (!guard) { guard = 1; if (interesting(from)) emit("RENAMEAT2(\"%s\", \"%s\", flags=0x%x) = %d", from, to, flags, rc); guard = 0; }
    return rc;
}

int link(const char *from, const char *to) {
    init();
    int rc = r_link(from, to);
    if (!guard) { guard = 1; if (interesting(from)) emit("LINK(\"%s\", \"%s\") = %d", from, to, rc); guard = 0; }
    return rc;
}

int unlink(const char *path) {
    init();
    int rc = r_unlink(path);
    if (!guard) { guard = 1; if (interesting(path)) emit("UNLINK(\"%s\") = %d", path, rc); guard = 0; }
    return rc;
}

int unlinkat(int dirfd, const char *path, int flags) {
    init();
    int rc = r_unlinkat(dirfd, path, flags);
    if (!guard) { guard = 1; if (interesting(path)) emit("UNLINKAT(\"%s\", 0x%x) = %d", path, flags, rc); guard = 0; }
    return rc;
}

int mkdirat(int dirfd, const char *path, mode_t mode) {
    init();
    int rc = r_mkdirat(dirfd, path, mode);
    if (!guard) { guard = 1; emit("MKDIRAT(\"%s\") = %d", path, rc); guard = 0; }
    return rc;
}
