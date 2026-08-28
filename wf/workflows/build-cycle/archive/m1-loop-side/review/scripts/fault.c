/* 故障注入：
 *  FAULT_NO_RENAMEAT2=1  → renameat2 一律回 EINVAL，逼 publish_exclusive 走 link+unlink 退路
 *  FAULT_UNLINK_TEMP=1   → 對結尾是 .json.temp 的 unlink 回 EPERM
 */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <stdlib.h>
#include <string.h>

static int (*r_renameat2)(int, const char *, int, const char *, unsigned int);
static int (*r_unlink)(const char *);

int renameat2(int od, const char *from, int nd, const char *to, unsigned int flags) {
    if (getenv("FAULT_NO_RENAMEAT2")) { errno = EINVAL; return -1; }
    if (!r_renameat2) r_renameat2 = dlsym(RTLD_NEXT, "renameat2");
    return r_renameat2(od, from, nd, to, flags);
}

int unlink(const char *path) {
    size_t n = strlen(path);
    if (getenv("FAULT_UNLINK_TEMP") && n >= 10 &&
        strcmp(path + n - 10, ".json.temp") == 0) {
        errno = EPERM;
        return -1;
    }
    if (!r_unlink) r_unlink = dlsym(RTLD_NEXT, "unlink");
    return r_unlink(path);
}
