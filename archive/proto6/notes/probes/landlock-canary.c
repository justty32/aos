/* Disposable, single-threaded probe. Never run this as root.
 * API: https://docs.kernel.org/userspace-api/landlock.html
 * Build/run via run.py; only accesses runner-created canaries. */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <linux/landlock.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/prctl.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include <unistd.h>

static void fail(const char *msg) { perror(msg); exit(2); }
static int checks(const char *role, const char *allowed, const char *denied) {
    int bad = 0;
    for (int which = 0; which < 2; which++) {
        const char *path = which ? denied : allowed;
        for (int write = 0; write < 2; write++) {
            errno = 0;
            int fd = open(path, write ? O_WRONLY | O_APPEND : O_RDONLY);
            int err = errno;
            int good = which ? fd == -1 && err == EACCES : fd >= 0;
            if (fd >= 0) {
                char c;
                if (write) { if (dprintf(fd, "%s\n", role) < 0) good = 0; }
                else if (read(fd, &c, 1) != 1) good = 0;
                close(fd);
            }
            printf("%s %s %s: %s errno=%d\n", role,
                   which ? "denied" : "allowed", write ? "write" : "read",
                   good ? "PASS" : "FAIL", err);
            bad += !good;
        }
    }
    return bad;
}
int main(int argc, char **argv) {
    if (getuid() == 0 || argc != 4) return 2;
    setbuf(stdout, NULL);
    int abi = syscall(SYS_landlock_create_ruleset, NULL, 0,
                      LANDLOCK_CREATE_RULESET_VERSION);
    printf("Landlock ABI=%d\n", abi);
    if (abi < 1) fail("ABI probe");
    /* Handle filesystem rights through ABI 3; intentionally no network rules. */
    struct landlock_ruleset_attr attr = {.handled_access_fs = (1ULL << 13) - 1};
    if (abi >= 2) attr.handled_access_fs |= LANDLOCK_ACCESS_FS_REFER;
    if (abi >= 3) attr.handled_access_fs |= LANDLOCK_ACCESS_FS_TRUNCATE;
    int rules = syscall(SYS_landlock_create_ruleset, &attr, sizeof(attr), 0);
    if (rules < 0) fail("create ruleset");
    int dir = open(argv[1], O_PATH | O_CLOEXEC);
    if (dir < 0) fail("allowed directory");
    struct landlock_path_beneath_attr path = {
        .allowed_access = attr.handled_access_fs, .parent_fd = dir};
    if (syscall(SYS_landlock_add_rule, rules, LANDLOCK_RULE_PATH_BENEATH,
                &path, 0)) fail("add rule");
    close(dir);
    if (prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0)) fail("NNP");
    if (syscall(SYS_landlock_restrict_self, rules, 0)) fail("restrict");
    close(rules);
    int bad = checks("parent", argv[2], argv[3]);
    pid_t child = fork();
    if (child < 0) fail("fork");
    if (!child) _exit(checks("child", argv[2], argv[3]) ? 1 : 0);
    int status;
    if (waitpid(child, &status, 0) < 0) fail("waitpid");
    return bad || !WIFEXITED(status) || WEXITSTATUS(status) ? 1 : 0;
}
