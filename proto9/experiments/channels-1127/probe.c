// probe.c：channels-1127 的探測程式——hold（建好 SysV／mqueue／socket 等東西後等著）、probe（一條一條試能不能碰到外面與兄弟）、find（外面找裡面建的）、sleep（當 init）。
// Build: gcc -O1 -Wall -o probe probe.c   (x86_64 Linux only; output is English, one JSON object per line)
#define _GNU_SOURCE
#include <arpa/inet.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <linux/bpf.h>
#include <linux/io_uring.h>
#include <linux/kcmp.h>
#include <linux/keyctl.h>
#include <linux/perf_event.h>
#include <linux/userfaultfd.h>
#include <mqueue.h>
#include <netinet/in.h>
#include <poll.h>
#include <sched.h>
#include <signal.h>
#include <stdarg.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ipc.h>
#include <sys/mman.h>
#include <sys/mount.h>
#include <sys/msg.h>
#include <sys/ptrace.h>
#include <sys/resource.h>
#include <sys/sem.h>
#include <sys/shm.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/uio.h>
#include <sys/un.h>
#include <sys/utsname.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#define KEY_BASE 0x43481100   // "CH" + 11 + tag index: out=1, B=2, A=3
#define MAX_PID_SCAN 4096

static FILE *OUT;
static char MARKER[64];   // hold: the bytes process_vm_readv would see
static char INHERITED[256];   // probe: fds above 2 that were open when main started (before it opened its output file)
static int INHERITED_N;

static int tag_index(const char *tag) {
    if (!strcmp(tag, "out")) return 1;
    if (!strcmp(tag, "B")) return 2;
    return 3;
}
static key_t key_of(const char *tag) { return KEY_BASE + tag_index(tag); }
static void mq_name(const char *tag, char *buf, size_t n) { snprintf(buf, n, "/channels1127-%s", tag); }
static void abs_name(const char *tag, char *buf, size_t n) { snprintf(buf, n, "channels1127-%s", tag); }

static const char *ename(int e) {
    if (!e) return "";
    const char *s = strerrorname_np(e);
    return s ? s : "E?";
}

static void json_str(FILE *f, const char *s) {
    fputc('"', f);
    for (; *s; ++s) {
        unsigned char c = (unsigned char)*s;
        if (c == '"' || c == '\\') fprintf(f, "\\%c", c);
        else if (c < 0x20 || c >= 0x7f) fprintf(f, "\\u%04x", c);
        else fputc(c, f);
    }
    fputc('"', f);
}

// one result: ok = the operation went through (the channel is open); err = errno when it did not
static void rec(const char *id, int ok, int err, const char *fmt, ...) {
    char d[1024] = "";
    if (fmt) {
        va_list ap;
        va_start(ap, fmt);
        vsnprintf(d, sizeof d, fmt, ap);
        va_end(ap);
    }
    fputs("{\"id\": ", OUT);
    json_str(OUT, id);
    fprintf(OUT, ", \"ok\": %s, \"err\": ", ok ? "true" : "false");
    json_str(OUT, ok ? "" : ename(err));
    fputs(", \"detail\": ", OUT);
    json_str(OUT, d);
    fputs("}\n", OUT);
    fflush(OUT);
}

// ---------------------------------------------------------------- input file: "key value" lines

#define MAXKV 64
static char KK[MAXKV][64], VV[MAXKV][256];
static int NKV;
static void load_kv(const char *path) {
    FILE *f = fopen(path, "r");
    if (!f) return;
    char line[400];
    while (NKV < MAXKV && fgets(line, sizeof line, f)) {
        line[strcspn(line, "\n")] = 0;
        char *sp = strchr(line, ' ');
        if (!sp) continue;
        *sp = 0;
        snprintf(KK[NKV], 64, "%.63s", line);
        snprintf(VV[NKV], 256, "%.255s", sp + 1);
        NKV++;
    }
    fclose(f);
}
static const char *kv(const char *k) {
    for (int i = 0; i < NKV; ++i)
        if (!strcmp(KK[i], k)) return VV[i];
    return "";
}
static long kvl(const char *k) { const char *v = kv(k); return *v ? strtol(v, NULL, 0) : 0; }

static long read_file(const char *path, char *buf, size_t n) {
    int fd = open(path, O_RDONLY | O_CLOEXEC);
    if (fd < 0) return -errno;
    size_t got = 0;   // loop: /proc seq files hand out about one page per read
    for (;;) {
        ssize_t r = read(fd, buf + got, n - 1 - got);
        if (r < 0) {
            int e = errno;
            close(fd);
            return -e;
        }
        if (r == 0 || got + r >= n - 1) {
            got += r;
            break;
        }
        got += r;
    }
    close(fd);
    buf[got] = 0;
    return (long)got;
}

static int count_lines(const char *s) {
    int n = 0;
    for (; *s; ++s) n += *s == '\n';
    return n;
}

// ---------------------------------------------------------------- hold: create the things, wait for SIGTERM, clean up

static int hold(const char *tag, const char *info_path) {
    sigset_t ss;
    sigemptyset(&ss);
    sigaddset(&ss, SIGTERM);
    sigaddset(&ss, SIGINT);
    sigprocmask(SIG_BLOCK, &ss, NULL);
    snprintf(MARKER, sizeof MARKER, "marker-%s", tag);
    key_t key = key_of(tag);
    char mqn[64], an[64];
    mq_name(tag, mqn, sizeof mqn);
    abs_name(tag, an, sizeof an);

    int shmid = shmget(key, 4096, IPC_CREAT | IPC_EXCL | 0666);
    int shm_err = shmid < 0 ? errno : 0;
    if (shmid >= 0) {
        char *p = shmat(shmid, NULL, 0);
        if (p != (void *)-1) {
            strcpy(p, MARKER);
            shmdt(p);
        }
    }
    int msqid = msgget(key, IPC_CREAT | IPC_EXCL | 0666);
    int msg_err = msqid < 0 ? errno : 0;
    if (msqid >= 0) {
        struct { long t; char b[64]; } m = {1, ""};
        strcpy(m.b, MARKER);
        msgsnd(msqid, &m, strlen(MARKER) + 1, IPC_NOWAIT);
    }
    int semid = semget(key, 1, IPC_CREAT | IPC_EXCL | 0666);
    int sem_err = semid < 0 ? errno : 0;
    if (semid >= 0) semctl(semid, 0, SETVAL, 1100 + tag_index(tag));
    struct mq_attr ma = {.mq_maxmsg = 4, .mq_msgsize = 64};
    mqd_t mq = mq_open(mqn, O_CREAT | O_EXCL | O_WRONLY, 0666, &ma);
    int mq_err = mq == (mqd_t)-1 ? errno : 0;
    if (mq != (mqd_t)-1) mq_send(mq, MARKER, strlen(MARKER) + 1, 0);

    int as = socket(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC, 0);
    struct sockaddr_un ua = {.sun_family = AF_UNIX};
    memcpy(ua.sun_path + 1, an, strlen(an));
    socklen_t ul = offsetof(struct sockaddr_un, sun_path) + 1 + strlen(an);
    int as_err = 0;
    if (bind(as, (struct sockaddr *)&ua, ul) != 0 || listen(as, 16) != 0) as_err = errno;

    int ts = socket(AF_INET, SOCK_STREAM | SOCK_CLOEXEC, 0);
    struct sockaddr_in ta = {.sin_family = AF_INET, .sin_addr.s_addr = htonl(INADDR_LOOPBACK)};
    int tcp_err = 0, port = 0;
    if (bind(ts, (struct sockaddr *)&ta, sizeof ta) != 0 || listen(ts, 16) != 0) tcp_err = errno;
    else {
        socklen_t l = sizeof ta;
        getsockname(ts, (struct sockaddr *)&ta, &l);
        port = ntohs(ta.sin_port);
    }
    int shmfd = -1;
    char shmpath[128];
    snprintf(shmpath, sizeof shmpath, "/dev/shm/channels1127-%s", tag);
    shmfd = open(shmpath, O_CREAT | O_EXCL | O_RDWR | O_CLOEXEC, 0666);
    int devshm_err = shmfd < 0 ? errno : 0;

    setpriority(PRIO_PROCESS, 0, 7);   // a value a neighbour could read with getpriority
    long ses = syscall(SYS_keyctl, KEYCTL_GET_KEYRING_ID, KEY_SPEC_SESSION_KEYRING, 0);
    long ses_err = ses < 0 ? errno : 0;
    long usr = syscall(SYS_keyctl, KEYCTL_GET_KEYRING_ID, KEY_SPEC_USER_KEYRING, 0);
    struct utsname u;
    uname(&u);

    char tmp[512];
    snprintf(tmp, sizeof tmp, "%s.tmp", info_path);
    FILE *f = fopen(tmp, "w");
    if (!f) return 1;
    fprintf(f, "pid %d\nmarker_addr %p\ntcp_port %d\nshm_err %s\nmsg_err %s\nsem_err %s\nmq_err %s\nabs_err %s\ntcp_err %s\n"
               "devshm_err %s\nsession_keyring %ld\nsession_keyring_err %s\nuser_keyring %ld\nhostname %s\n",
            getpid(), (void *)MARKER, port, ename(shm_err), ename(msg_err), ename(sem_err), ename(mq_err), ename(as_err),
            ename(tcp_err), ename(devshm_err), ses, ename((int)ses_err), usr, u.nodename);
    fclose(f);
    rename(tmp, info_path);

    int sig;
    sigwait(&ss, &sig);
    if (shmid >= 0) shmctl(shmid, IPC_RMID, NULL);
    if (msqid >= 0) msgctl(msqid, IPC_RMID, NULL);
    if (semid >= 0) semctl(semid, 0, IPC_RMID);
    if (mq != (mqd_t)-1) mq_unlink(mqn);
    if (shmfd >= 0) unlink(shmpath);
    close(as);
    close(ts);
    return 0;
}

// ---------------------------------------------------------------- the SysV / mqueue / socket checks shared by probe and find

static void find_sysv(const char *prefix, const char *tag) {
    char id[64];
    key_t key = key_of(tag);
    snprintf(id, sizeof id, "%s.shm", prefix);
    int s = shmget(key, 0, 0);
    if (s < 0) rec(id, 0, errno, "shmget key 0x%x", key);
    else {
        char *p = shmat(s, NULL, SHM_RDONLY);
        if (p == (void *)-1) rec(id, 0, errno, "found id %d, shmat failed", s);
        else {
            rec(id, 1, 0, "found id %d, read \"%.30s\"", s, p);
            shmdt(p);
        }
    }
    snprintf(id, sizeof id, "%s.msg", prefix);
    int q = msgget(key, 0);
    if (q < 0) rec(id, 0, errno, "msgget key 0x%x", key);
    else {
        struct { long t; char b[64]; } m;
        ssize_t r = msgrcv(q, &m, sizeof m.b, 0, IPC_NOWAIT | MSG_NOERROR);
        if (r < 0) rec(id, 1, 0, "found id %d, msgrcv: %s", q, ename(errno));
        else rec(id, 1, 0, "found id %d, received \"%.30s\"", q, m.b);
    }
    snprintf(id, sizeof id, "%s.sem", prefix);
    int se = semget(key, 0, 0);
    if (se < 0) rec(id, 0, errno, "semget key 0x%x", key);
    else {
        int v = semctl(se, 0, GETVAL);
        rec(id, 1, 0, "found id %d, value %d", se, v);
    }
    snprintf(id, sizeof id, "%s.mq", prefix);
    char mqn[64];
    mq_name(tag, mqn, sizeof mqn);
    mqd_t mq = mq_open(mqn, O_RDONLY | O_NONBLOCK);
    if (mq == (mqd_t)-1) rec(id, 0, errno, "mq_open %s", mqn);
    else {
        char b[128] = "";
        ssize_t r = mq_receive(mq, b, sizeof b, NULL);
        rec(id, 1, 0, "opened %s, %s \"%.30s\"", mqn, r < 0 ? ename(errno) : "received", r < 0 ? "" : b);
        mq_close(mq);
    }
}

static int abs_connect(const char *tag) {
    char an[64];
    abs_name(tag, an, sizeof an);
    int s = socket(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC, 0);
    struct sockaddr_un ua = {.sun_family = AF_UNIX};
    memcpy(ua.sun_path + 1, an, strlen(an));
    socklen_t ul = offsetof(struct sockaddr_un, sun_path) + 1 + strlen(an);
    int r = connect(s, (struct sockaddr *)&ua, ul);
    int e = errno;
    close(s);
    return r == 0 ? 0 : e;
}

// connect only, no data. timeout in ms. returns 0 or errno (ETIMEDOUT on timeout)
static int tcp_connect(const char *ip, int port, int timeout_ms) {
    int s = socket(AF_INET, SOCK_STREAM | SOCK_CLOEXEC | SOCK_NONBLOCK, 0);
    struct sockaddr_in a = {.sin_family = AF_INET, .sin_port = htons(port)};
    inet_pton(AF_INET, ip, &a.sin_addr);
    int r = connect(s, (struct sockaddr *)&a, sizeof a), e = 0;
    if (r != 0) {
        e = errno;
        if (e == EINPROGRESS) {
            struct pollfd p = {s, POLLOUT, 0};
            int pr = poll(&p, 1, timeout_ms);
            if (pr == 0) e = ETIMEDOUT;
            else {
                socklen_t l = sizeof e;
                getsockopt(s, SOL_SOCKET, SO_ERROR, &e, &l);
            }
        }
    }
    close(s);
    return e;
}

static void find_sockets(const char *prefix, const char *tag, int port) {
    char id[64];
    snprintf(id, sizeof id, "%s.abstract", prefix);
    int e = abs_connect(tag);
    rec(id, !e, e, "connect @channels1127-%s", tag);
    snprintf(id, sizeof id, "%s.tcp", prefix);
    if (!port) rec(id, 0, ENOENT, "no port known");
    else {
        e = tcp_connect("127.0.0.1", port, 2000);
        rec(id, !e, e, "connect 127.0.0.1:%d", port);
    }
}

// ---------------------------------------------------------------- probe: everything a proc in the sky tries

static void proc_files(const char *who, int pid) {
    char path[128], id[64];
    static char buf[1 << 20];
    const char *files[] = {"cmdline", "environ", "status", "mountinfo", "net/tcp", "net/unix"};
    for (unsigned i = 0; i < sizeof files / sizeof *files; ++i) {
        snprintf(path, sizeof path, "/proc/%d/%s", pid, files[i]);
        snprintf(id, sizeof id, "proc.%s.%s", who, files[i]);
        long r = read_file(path, buf, sizeof buf);
        if (r < 0) {
            rec(id, 0, (int)-r, "%s", path);
            continue;
        }
        if (!strcmp(files[i], "cmdline")) {
            for (long k = 0; k < r; ++k)
                if (!buf[k]) buf[k] = ' ';
            rec(id, 1, 0, "%.80s", buf);
        } else if (!strcmp(files[i], "status")) {
            char *n = strstr(buf, "Name:");
            rec(id, 1, 0, "%.30s", n ? n : "");
        } else if (!strcmp(files[i], "net/unix")) {
            rec(id, 1, 0, "%d lines; mentions @channels1127-out: %s", count_lines(buf),
                strstr(buf, "@channels1127-out") ? "yes" : "no");
        } else rec(id, 1, 0, "%d lines", count_lines(buf));
    }
    snprintf(path, sizeof path, "/proc/%d/fd/0", pid);
    snprintf(id, sizeof id, "proc.%s.fd_link", who);
    char lk[256];
    ssize_t ln = readlink(path, lk, sizeof lk - 1);
    if (ln < 0) rec(id, 0, errno, "readlink %s", path);
    else {
        lk[ln] = 0;
        rec(id, 1, 0, "fd 0 -> %s", lk);
    }
    const char *dirs[] = {"root", "fd"};
    for (unsigned i = 0; i < 2; ++i) {
        snprintf(path, sizeof path, "/proc/%d/%s", pid, dirs[i]);
        snprintf(id, sizeof id, "proc.%s.%s", who, dirs[i]);
        DIR *d = opendir(path);
        if (!d) {
            rec(id, 0, errno, "%s", path);
            continue;
        }
        int n = 0;
        while (readdir(d)) n++;
        closedir(d);
        rec(id, 1, 0, "%d entries", n - 2);
    }
}

static void target_checks(const char *who, int pid) {
    char id[64];
    // signals: 0 only checks permission; SIGWINCH is ignored by default (harmless)
    snprintf(id, sizeof id, "signal.%s", who);
    int r0 = kill(pid, 0), e0 = errno;
    int r1 = kill(pid, SIGWINCH), e1 = errno;
    rec(id, r0 == 0 && r1 == 0, r0 ? e0 : e1, "kill(%d, 0) %s, kill(%d, SIGWINCH) %s", pid, r0 ? ename(e0) : "ok", pid,
        r1 ? ename(e1) : "ok");
    if (!strcmp(who, "outside")) return;
    snprintf(id, sizeof id, "pidfd_open.%s", who);
    int pfd = (int)syscall(SYS_pidfd_open, pid, 0);
    rec(id, pfd >= 0, errno, "pidfd_open(%d)", pid);
    if (pfd >= 0) {
        snprintf(id, sizeof id, "pidfd_send_signal.%s", who);
        int r = (int)syscall(SYS_pidfd_send_signal, pfd, 0, NULL, 0);
        rec(id, r == 0, errno, "signal 0");
        snprintf(id, sizeof id, "pidfd_getfd.%s", who);
        int g = (int)syscall(SYS_pidfd_getfd, pfd, 0, 0);
        rec(id, g >= 0, errno, "its fd 0");
        if (g >= 0) close(g);
        close(pfd);
    }
    snprintf(id, sizeof id, "ptrace.%s", who);
    long pr = ptrace(PTRACE_SEIZE, pid, 0, 0);
    rec(id, pr == 0, errno, "PTRACE_SEIZE");   // if it ever succeeds, exiting detaches
    snprintf(id, sizeof id, "kcmp.%s", who);
    long kr = syscall(SYS_kcmp, getpid(), pid, KCMP_VM, 0, 0);
    rec(id, kr >= 0, errno, "KCMP_VM -> %ld", kr);
    snprintf(id, sizeof id, "getpriority.%s", who);
    errno = 0;
    int nice = getpriority(PRIO_PROCESS, pid);
    int ge = errno;
    rec(id, !ge, ge, "nice %d", nice);
    snprintf(id, sizeof id, "setpriority.%s", who);
    if (!ge) {   // set the value it already has: shows the permission without changing anything
        int r = setpriority(PRIO_PROCESS, pid, nice);
        rec(id, r == 0, errno, "set nice %d (its current value)", nice);
    }
    snprintf(id, sizeof id, "prlimit.%s", who);
    struct rlimit old;
    if (prlimit(pid, RLIMIT_NOFILE, NULL, &old) != 0) rec(id, 0, errno, "read RLIMIT_NOFILE");
    else {
        int r = prlimit(pid, RLIMIT_NOFILE, &old, NULL);
        rec(id, r == 0, errno, "read RLIMIT_NOFILE %lu/%lu, write same: %s", (unsigned long)old.rlim_cur,
            (unsigned long)old.rlim_max, r == 0 ? "ok" : ename(errno));
    }
    snprintf(id, sizeof id, "sched_setaffinity.%s", who);
    cpu_set_t cs;
    if (sched_getaffinity(pid, sizeof cs, &cs) != 0) rec(id, 0, errno, "sched_getaffinity");
    else {
        int r = sched_setaffinity(pid, sizeof cs, &cs);
        rec(id, r == 0, errno, "read mask (%d cpus), write same: %s", CPU_COUNT(&cs), r == 0 ? "ok" : ename(errno));
    }
}

static void unshare_try(const char *name, int flags, int extra) {
    pid_t c = fork();
    if (c == 0) {
        if (unshare(flags) != 0) _exit(100 + errno);
        if (extra == 1) {   // own IPC namespace: the outside's key is gone
            int s = shmget(key_of("out"), 0, 0);
            _exit(s >= 0 ? 1 : 0);
        }
        if (extra == 2) {   // own mount namespace: try to mount over /tmp
            if (mount("none", "/tmp", "tmpfs", 0, NULL) != 0) _exit(100 + errno);
        }
        _exit(0);
    }
    int st = 0;
    waitpid(c, &st, 0);
    int code = WIFEXITED(st) ? WEXITSTATUS(st) : 255;
    char id[64];
    snprintf(id, sizeof id, "unshare.%s", name);
    if (code >= 100) rec(id, 0, code - 100, extra == 2 ? "unshare ok, mount" : "unshare");
    else if (extra == 1) rec(id, 1, 0, "own IPC ns; outside shm key %s", code ? "still visible" : "not visible");
    else if (extra == 2) rec(id, 1, 0, "unshare and mount tmpfs on /tmp ok");
    else rec(id, code == 0, 0, "exit %d", code);
}

static int probe(const char *in_path) {
    load_kv(in_path);
    int b = (int)kvl("b_pid"), init = (int)kvl("init_pid"), outpid = (int)kvl("out_host_pid");
    int has_proc = access("/proc/self", F_OK) == 0;
    rec("proc.mounted", has_proc, ENOENT, "/proc/self %s", has_proc ? "exists" : "missing");

    // --- SysV IPC, POSIX mqueue, /dev/shm
    find_sysv("ipc.out", "out");
    find_sysv("ipc.B", "B");
    {
        struct shm_info si;
        int maxidx = shmctl(0, SHM_INFO, (struct shmid_ds *)&si);
        int total = 0, statok = 0, foreign_ok = 0;
        for (int i = 0; i <= maxidx; ++i) {
            struct shmid_ds ds;
            int sid = shmctl(i, SHM_STAT_ANY, &ds);
            if (sid < 0) continue;
            total++;
            struct shmid_ds d2;
            if (shmctl(sid, IPC_STAT, &d2) == 0) {
                statok++;
                key_t k = ds.shm_perm.__key;
                if ((k & ~0xff) != KEY_BASE && (ds.shm_perm.mode & 0077) == 0) foreign_ok++;
            }
        }
        if (maxidx < 0) rec("ipc.enum_shm", 0, errno, "SHM_INFO");
        else
            rec("ipc.enum_shm", total > 0, 0, "%d segments listed, IPC_STAT allowed on %d, of which %d are private (mode ..00) and not ours",
                total, statok, foreign_ok);
    }
    struct stat st;
    int r = stat("/dev/shm", &st);
    rec("ipc.dev_shm", r == 0, errno, "/dev/shm");
    {
        static char buf[1 << 20];
        long n = read_file("/proc/sysvipc/shm", buf, sizeof buf);
        if (n < 0) rec("ipc.proc_sysvipc", 0, (int)-n, "/proc/sysvipc/shm");
        else rec("ipc.proc_sysvipc", 1, 0, "%d segments listed", count_lines(buf) - 1);
    }

    // --- sockets
    find_sockets("net.out", "out", (int)kvl("out_tcp"));
    find_sockets("net.B", "B", (int)kvl("b_tcp"));
    int e = tcp_connect("1.1.1.1", 53, 3000);
    rec("net.internet", !e, e, "connect 1.1.1.1:53 (no data sent)");

    // --- processes
    target_checks("B", b);
    target_checks("init", init);
    target_checks("daemon", 1);
    target_checks("outside", outpid);
    {
        int seen = 0, eperm = 0;
        char list[512] = "";
        for (int p = 1; p <= MAX_PID_SCAN; ++p) {
            int rc = kill(p, 0);
            if (rc == 0 || errno == EPERM) {
                if (rc != 0) eperm++;
                seen++;
                if (strlen(list) < 480) snprintf(list + strlen(list), sizeof list - strlen(list), "%d ", p);
            }
        }
        rec("pid_scan", seen > 1, 0, "kill(pid, 0) on 1..%d: %d exist (%d of them EPERM): %s", MAX_PID_SCAN, seen, eperm, list);
    }
    {
        long pos = (long)strtoul(kv("b_marker_addr"), NULL, 16);
        char buf[64] = "";
        struct iovec l = {buf, sizeof buf - 1}, rm = {(void *)pos, sizeof buf - 1};
        ssize_t n = process_vm_readv(b, &l, 1, &rm, 1, 0);
        rec("process_vm_readv.B", n > 0, errno, n > 0 ? "read \"%.30s\"" : "%s", n > 0 ? buf : "");
    }
    if (has_proc) {
        proc_files("B", b);
        proc_files("init", init);
        proc_files("daemon", 1);
    }

    // --- other kernel objects
    {
        struct io_uring_params p;
        memset(&p, 0, sizeof p);
        int fd = (int)syscall(SYS_io_uring_setup, 4, &p);
        rec("io_uring_setup", fd >= 0, errno, "4 entries");
        if (fd >= 0) close(fd);
    }
    {
        union bpf_attr a;
        memset(&a, 0, sizeof a);
        a.map_type = BPF_MAP_TYPE_ARRAY;
        a.key_size = 4;
        a.value_size = 4;
        a.max_entries = 1;
        int fd = (int)syscall(SYS_bpf, BPF_MAP_CREATE, &a, sizeof a);
        rec("bpf", fd >= 0, errno, "BPF_MAP_CREATE array");
        if (fd >= 0) close(fd);
    }
    {
        long ses = syscall(SYS_keyctl, KEYCTL_GET_KEYRING_ID, KEY_SPEC_SESSION_KEYRING, 0);
        int se = errno;
        if (ses < 0) rec("keyctl.session", 0, se, "KEYCTL_GET_KEYRING_ID session");
        else {
            char buf[4096];
            long n = syscall(SYS_keyctl, KEYCTL_READ, ses, buf, sizeof buf);
            rec("keyctl.session", 1, 0, "session keyring %ld; same as the launcher's (%s): %s; same as B's: %s; KEYCTL_READ %s",
                ses, kv("out_session_keyring"), ses == kvl("out_session_keyring") ? "yes" : "no",
                ses == kvl("b_session_keyring") ? "yes" : "no", n < 0 ? ename(errno) : "ok");
        }
        long usr = syscall(SYS_keyctl, KEYCTL_GET_KEYRING_ID, KEY_SPEC_USER_KEYRING, 0);
        int ue = errno;
        if (usr < 0) rec("keyctl.user", 0, ue, "KEYCTL_GET_KEYRING_ID user");
        else
            rec("keyctl.user", 1, 0, "user keyring %ld; same as the launcher's: %s; same as B's: %s", usr,
                usr == kvl("out_user_keyring") ? "yes" : "no", usr == kvl("b_user_keyring") ? "yes" : "no");
        long k = syscall(SYS_add_key, "user", "channels1127", "x", 1, KEY_SPEC_THREAD_KEYRING);
        rec("add_key", k >= 0, errno, "into its own thread keyring");
    }
    {
        struct perf_event_attr a;
        memset(&a, 0, sizeof a);
        a.type = PERF_TYPE_SOFTWARE;
        a.size = sizeof a;
        a.config = PERF_COUNT_SW_TASK_CLOCK;
        a.disabled = 1;
        a.exclude_kernel = 1;
        a.exclude_hv = 1;
        int fd = (int)syscall(SYS_perf_event_open, &a, 0, -1, -1, 0);
        rec("perf_event_open.self", fd >= 0, errno, "task clock of itself");
        if (fd >= 0) close(fd);
        fd = (int)syscall(SYS_perf_event_open, &a, b, -1, -1, 0);
        rec("perf_event_open.B", fd >= 0, errno, "task clock of B");
        if (fd >= 0) close(fd);
    }
    {
        int fd = (int)syscall(SYS_userfaultfd, O_CLOEXEC);
        int e1 = errno;
        if (fd >= 0) close(fd);
        int fd2 = (int)syscall(SYS_userfaultfd, O_CLOEXEC | UFFD_USER_MODE_ONLY);
        int e2 = errno;
        if (fd2 >= 0) close(fd2);
        rec("userfaultfd", fd >= 0 || fd2 >= 0, fd2 >= 0 ? 0 : e2, "plain: %s, user-mode-only: %s", fd >= 0 ? "ok" : ename(e1),
            fd2 >= 0 ? "ok" : ename(e2));
    }
    {
        struct file_handle *h = malloc(sizeof *h + MAX_HANDLE_SZ);
        h->handle_bytes = MAX_HANDLE_SZ;
        int mid;
        int rr = name_to_handle_at(AT_FDCWD, "/w", h, &mid, 0);
        rec("name_to_handle_at", rr == 0, errno, "/w");
        if (rr == 0) {
            int mfd = open("/w", O_RDONLY | O_DIRECTORY | O_CLOEXEC);
            int fd = open_by_handle_at(mfd, h, O_RDONLY | O_CLOEXEC);
            rec("open_by_handle_at", fd >= 0, errno, "handle of /w");
            if (fd >= 0) close(fd);
            close(mfd);
        } else {
            int fd = open_by_handle_at(AT_FDCWD, h, O_RDONLY);
            rec("open_by_handle_at", fd >= 0, errno, "(no handle; checks only the syscall gate)");
        }
        free(h);
    }
    {
        struct utsname u;
        uname(&u);
        rec("uname", 1, 0, "nodename %s; same as outside: %s", u.nodename, strcmp(u.nodename, kv("out_hostname")) ? "no" : "yes");
        int rr = sethostname(u.nodename, strlen(u.nodename));
        rec("sethostname", rr == 0, errno, "set to the same name");
    }
    {
        struct timespec ts;
        clock_gettime(CLOCK_REALTIME, &ts);
        int rr = clock_settime(CLOCK_REALTIME, &ts);
        rec("clock_settime", rr == 0, errno, "CLOCK_REALTIME to now");
    }
    unshare_try("user", CLONE_NEWUSER, 0);
    unshare_try("mnt_alone", CLONE_NEWNS, 0);
    unshare_try("ipc_alone", CLONE_NEWIPC, 0);
    unshare_try("user+mnt", CLONE_NEWUSER | CLONE_NEWNS, 0);
    unshare_try("user+net", CLONE_NEWUSER | CLONE_NEWNET, 0);
    unshare_try("user+ipc", CLONE_NEWUSER | CLONE_NEWIPC, 1);
    unshare_try("user+uts", CLONE_NEWUSER | CLONE_NEWUTS, 0);
    unshare_try("user+pid", CLONE_NEWUSER | CLONE_NEWPID, 0);
    unshare_try("user+cgroup", CLONE_NEWUSER | CLONE_NEWCGROUP, 0);
    unshare_try("user+time", CLONE_NEWUSER | CLONE_NEWTIME, 0);
    unshare_try("user+mnt_then_mount", CLONE_NEWUSER | CLONE_NEWNS, 2);
    {
        int fd = memfd_create("channels1127", MFD_CLOEXEC);
        rec("memfd_create", fd >= 0, errno, "anonymous file; only leaves the proc through a unix socket");
        if (fd >= 0) close(fd);
    }
    rec("inherited_fds", INHERITED_N > 0, 0, "%d open fds above 2 at start: %s", INHERITED_N, INHERITED);
    {
        char buf[4096];
        long n = read_file("/proc/self/cgroup", buf, sizeof buf);
        if (n < 0) rec("cgroup.self_path", 0, (int)-n, "/proc/self/cgroup");
        else {
            buf[strcspn(buf, "\n")] = 0;
            rec("cgroup.self_path", 1, 0, "%.200s", buf);
        }
        int rr = stat("/sys/fs/cgroup", &st);
        rec("cgroup.fs", rr == 0, errno, "/sys/fs/cgroup");
    }
    {
        static char buf[1 << 20];
        long n = read_file("/proc/self/mountinfo", buf, sizeof buf);
        if (n < 0) rec("mountinfo.self", 0, (int)-n, "/proc/self/mountinfo");
        else {
            int lines = count_lines(buf);
            char root[300] = "", r1[300], m1[300];   // fields: id parent dev root mountpoint ...; root of /w = outside path
            for (char *line = strtok(buf, "\n"); line; line = strtok(NULL, "\n"))
                if (sscanf(line, "%*d %*d %*s %299s %299s", r1, m1) == 2 && !strcmp(m1, "/w")) snprintf(root, sizeof root, "%s", r1);
            rec("mountinfo.self", 1, 0, "%d mounts; the bind at /w shows outside path %s", lines, root);
        }
    }
    return 0;
}

int main(int argc, char **argv) {
    OUT = stdout;
    for (int fd = 3; fd < 1024; ++fd)
        if (fcntl(fd, F_GETFD) >= 0) {
            INHERITED_N++;
            snprintf(INHERITED + strlen(INHERITED), sizeof INHERITED - strlen(INHERITED), "%d ", fd);
        }
    if (argc >= 2 && !strcmp(argv[1], "sleep")) {
        for (;;) pause();
    }
    if (argc == 4 && !strcmp(argv[1], "hold")) return hold(argv[2], argv[3]);
    if (argc == 4 && !strcmp(argv[1], "probe")) {
        OUT = fopen(argv[3], "w");
        if (!OUT) return 1;
        return probe(argv[2]);
    }
    if (argc == 5 && !strcmp(argv[1], "find")) {   // find TAG PORT OUTFILE (run outside)
        OUT = fopen(argv[4], "w");
        if (!OUT) return 1;
        find_sysv("ipc.B_from_outside", argv[2]);
        find_sockets("net.B_from_outside", argv[2], atoi(argv[3]));
        return 0;
    }
    fprintf(stderr, "usage: probe sleep | hold TAG INFO | probe IN OUT | find TAG PORT OUT\n");
    return 2;
}
