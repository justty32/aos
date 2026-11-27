// fakeabi.c：LD_PRELOAD 用的小墊片，讓 aos-daemon 問 Landlock 版本時拿到 3（在家機 6.18 上模擬公司 WSL 6.6 那種舊 Linux：不加擋訊號與 abstract socket）。
// Build: gcc -shared -fPIC -O1 -o fakeabi.so fakeabi.c -ldl
// Only the version query (landlock_create_ruleset(NULL, 0, LANDLOCK_CREATE_RULESET_VERSION)) is changed; every other call goes to libc.
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdarg.h>
#include <sys/syscall.h>

#ifndef SYS_landlock_create_ruleset
#define SYS_landlock_create_ruleset 444
#endif

long syscall(long n, ...) {
    va_list ap;
    va_start(ap, n);
    long a[6];
    for (int i = 0; i < 6; ++i) a[i] = va_arg(ap, long);
    va_end(ap);
    if (n == SYS_landlock_create_ruleset && a[0] == 0 && a[1] == 0 && a[2] == 1) return 3;
    static long (*real)(long, ...);
    if (!real) real = (long (*)(long, ...))dlsym(RTLD_NEXT, "syscall");
    return real(n, a[0], a[1], a[2], a[3], a[4], a[5]);
}
