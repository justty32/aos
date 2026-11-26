// spawn.cpp：起一隻 proc（fork 出來的子行程進原本那一層拿來源、根從零組天空、換根、上鎖、exec）與跑的時候掛、卸。
#include "common.hpp"

#include <cerrno>
#include <csignal>
#include <cstring>
#include <fcntl.h>
#include <grp.h>
#include <linux/capability.h>
#include <linux/landlock.h>
#include <linux/openat2.h>
#include <net/if.h>
#include <poll.h>
#include <sched.h>
#include <sys/mount.h>
#include <sys/ioctl.h>
#include <sys/prctl.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include <unistd.h>

namespace d2 {

namespace {

// 子行程自己那份 mount namespace 裡，新的根先掛在這裡。來源在掛之前都拿好了，蓋住外面的 /tmp 也沒關係。
const char* STAGE = "/tmp";
// securebits：noroot、no_setuid_fixup、keep_caps_locked、no_cap_ambient_raise，全部鎖住
const unsigned long SECBITS = 0x01 | 0x02 | 0x04 | 0x08 | 0x20 | 0x40 | 0x80;

int report_fd = -1;

[[noreturn]] void die(const std::string& step, int e) {
    std::string m = "E" + step + ": " + errstr(e) + "\n";
    if (write(report_fd, m.data(), m.size()) < 0) {}
    _exit(127);
}

void say(int fd, const std::string& m) {
    if (write(fd, m.data(), m.size()) < 0) {}
}

int openat2_in(int root, const std::string& rel, int flags) {
    open_how how{};
    how.flags = static_cast<unsigned long long>(flags | O_CLOEXEC);
    how.resolve = RESOLVE_IN_ROOT;
    return static_cast<int>(syscall(SYS_openat2, root, rel.empty() ? "." : rel.c_str(), &how, sizeof how));
}

// 天空裡的路徑 → 相對於根的相對路徑（"/a/b" → "a/b"）
std::string rel_of(const std::string& p) { return p.size() > 1 ? p.substr(1) : ""; }

// 在 root（天空的根）底下 mkdir -p 到 path 的上一層，回上一層的 fd；last 是最後一段。
// 每一段都用 RESOLVE_IN_ROOT 從根開：天空裡的 symlink（含絕對路徑的）都只在天空裡解，不會碰到外面。
int parent_dir(int root, const std::string& path, std::string& last) {
    std::string rel = rel_of(path);
    size_t slash = rel.rfind('/');
    last = slash == std::string::npos ? rel : rel.substr(slash + 1);
    std::string up = slash == std::string::npos ? "" : rel.substr(0, slash);
    for (size_t i = 0; i <= up.size(); ++i) {
        if (i != up.size() && up[i] != '/') continue;
        std::string pre = up.substr(0, i);
        size_t s2 = pre.rfind('/');
        std::string pp = s2 == std::string::npos ? "" : pre.substr(0, s2);
        std::string name = s2 == std::string::npos ? pre : pre.substr(s2 + 1);
        if (name.empty()) continue;
        int pfd = openat2_in(root, pp, O_PATH | O_DIRECTORY);
        if (pfd < 0) return -1;
        int r = mkdirat(pfd, name.c_str(), 0755);
        int e = errno;
        close(pfd);
        if (r != 0 && e != EEXIST) {
            errno = e;
            return -1;
        }
    }
    return openat2_in(root, up, O_PATH | O_DIRECTORY);
}

// 建掛載點（夾或空檔），回它的 O_PATH fd；已經在就直接用（唯讀的地方也行）
int mkpoint(int root, const std::string& path, bool dir) {
    int have = openat2_in(root, rel_of(path), O_PATH | (dir ? O_DIRECTORY : 0));
    if (have >= 0) return have;
    std::string last;
    int pfd = parent_dir(root, path, last);
    if (pfd < 0) return -1;
    int r = dir ? mkdirat(pfd, last.c_str(), 0755) : openat(pfd, last.c_str(), O_CREAT | O_WRONLY | O_CLOEXEC | O_NOFOLLOW, 0644);
    int e = errno;
    if (!dir && r >= 0) close(r);
    close(pfd);
    if (r < 0 && e != EEXIST) {
        errno = e;
        return -1;
    }
    return openat2_in(root, rel_of(path), O_PATH | (dir ? O_DIRECTORY : 0));
}

int set_attr(int dfd, const char* path, unsigned flags, uint64_t set, uint64_t clr = 0) {
    mount_attr a{};
    a.attr_set = set;
    a.attr_clr = clr;
    return mount_setattr(dfd, path, flags, &a, sizeof a);
}

// 外面的一個路徑複製成一個還沒掛上的掛載；底下有鎖住的子掛載時只能連它們一起帶（sky-1125 坑 5）
int clone_src(const std::string& src) {
    int fd = open_tree(AT_FDCWD, src.c_str(), OPEN_TREE_CLONE | OPEN_TREE_CLOEXEC);
    if (fd < 0 && errno == EINVAL) fd = open_tree(AT_FDCWD, src.c_str(), OPEN_TREE_CLONE | OPEN_TREE_CLOEXEC | AT_RECURSIVE);
    return fd;
}

bool is_dir_fd(int fd) {
    struct stat st;
    return fstat(fd, &st) == 0 && S_ISDIR(st.st_mode);
}

void attach(int clone, int root, const std::string& dst, bool rw, bool nodev, const std::string& what) {
    int t = mkpoint(root, dst, is_dir_fd(clone));
    if (t < 0) die("mount point " + dst, errno);
    uint64_t set = MOUNT_ATTR_NOSUID | (nodev ? MOUNT_ATTR_NODEV : 0) | (rw ? 0 : MOUNT_ATTR_RDONLY);
    if (set_attr(clone, "", AT_EMPTY_PATH | AT_RECURSIVE, set) != 0) die("set flags on " + what, errno);
    if (move_mount(clone, "", t, "", MOVE_MOUNT_F_EMPTY_PATH | MOVE_MOUNT_T_EMPTY_PATH) != 0) die("attach " + what, errno);
    close(t);
    close(clone);
}

void mount_fs(int root, const std::string& dst, const char* type, unsigned long flags, const char* data) {
    int t = mkpoint(root, dst, true);
    if (t < 0) die("mount point " + dst, errno);
    std::string at = "/proc/self/fd/" + std::to_string(t);
    if (mount(type, at.c_str(), type, flags, data) != 0) die(std::string("mount ") + type + " at " + dst, errno);
    close(t);
}

void set_caps(uint64_t caps) {
    __user_cap_header_struct h{_LINUX_CAPABILITY_VERSION_3, 0};
    __user_cap_data_struct d[2]{};
    d[0].effective = d[0].permitted = d[0].inheritable = static_cast<uint32_t>(caps);
    d[1].effective = d[1].permitted = d[1].inheritable = static_cast<uint32_t>(caps >> 32);
    if (syscall(SYS_capset, &h, d) != 0) die("capset", errno);
}

struct LandlockAttr {
    uint64_t fs, net, scoped;
};

// net none：剛開的 network namespace 裡只有 lo、而且是關的；打開它（127.0.0.1、::1 由核心自己加上）。要 CAP_NET_ADMIN，所以在丟 caps 之前做
void loopback_up() {
    int s = socket(AF_INET, SOCK_DGRAM | SOCK_CLOEXEC, 0);
    if (s < 0) die("socket for lo", errno);
    ifreq r{};
    strncpy(r.ifr_name, "lo", IFNAMSIZ - 1);
    if (ioctl(s, SIOCGIFFLAGS, &r) != 0) die("get lo flags", errno);
    r.ifr_flags = static_cast<short>(r.ifr_flags | IFF_UP | IFF_RUNNING);
    if (ioctl(s, SIOCSIFFLAGS, &r) != 0) die("bring lo up", errno);
    close(s);
}

// 子行程：exec 之前全部在這裡做；失敗就把原因寫回 report_fd、_exit(127)
[[noreturn]] void child(const ProcConfig& cfg, bool init, const std::vector<Mount>& mounts,
                        const std::string& cgroup, std::vector<char*>& argv, std::vector<char*>& envp, int go) {
    sigset_t none;
    sigemptyset(&none);
    sigprocmask(SIG_SETMASK, &none, nullptr);
    for (int s = 1; s < 32; ++s)
        if (s != SIGKILL && s != SIGSTOP) signal(s, SIG_DFL);
    setsid();
    // init（mount 模式）：daemon 的目錄（與 cgroup 夾）只在 daemon 的小世界裡（/aos、/cgroup），趁還在這裡先複製成還沒掛上的掛載
    bool give_aos = init && init_mounts(cfg);
    int aos_clone = -1, cg_clone = -1;
    if (give_aos) {
        aos_clone = open_tree(AT_FDCWD, "/aos", OPEN_TREE_CLONE | OPEN_TREE_CLOEXEC);
        if (aos_clone < 0) die("clone the daemon's directory", errno);
        if (W.cgfd >= 0 && (cg_clone = open_tree(AT_FDCWD, "/cgroup", OPEN_TREE_CLONE | OPEN_TREE_CLOEXEC)) < 0)
            die("clone the cgroup directory", errno);
    }

    // 1. 進原本那一層（daemon 換根之前的世界）：設定裡的路徑都照那一層解
    if (setns(W.orignsfd, CLONE_NEWNS) != 0) die("setns", errno);
    char hp[32] = {0};
    if (readlinkat(W.hostprocfd, "self", hp, sizeof hp - 1) < 0) die("read host pid", errno);
    int fin = open("/dev/null", O_RDONLY | O_CLOEXEC);
    auto out_fd = [](const std::string& p) {
        // 沒設＝/dev/null（使用者 11-26 定；不再跟 daemon 的 stderr）
        int fd = p.empty() ? open("/dev/null", O_WRONLY | O_CLOEXEC) : open(p.c_str(), O_WRONLY | O_CREAT | O_APPEND | O_CLOEXEC, 0644);
        if (fd < 0) die("open " + (p.empty() ? std::string("/dev/null") : p), errno);
        return fd;
    };
    int fout = out_fd(cfg.stdout_path), ferr = out_fd(cfg.stderr_path);
    if (fin < 0) die("open /dev/null", errno);

    // 2. 來源先全部拿好（複製成還沒掛上的掛載）
    std::vector<int> clones(mounts.size(), -1);
    for (size_t i = 0; i < mounts.size(); ++i)
        if (mounts[i].kind == "bind" && (clones[i] = clone_src(mounts[i].src)) < 0) die("bind source " + mounts[i].src, errno);

    // 3. 自己一份 mount namespace，根從一塊新的 tmpfs 組起；net none 時順便開自己的 network namespace、打開 lo
    if (unshare(CLONE_NEWNS) != 0) die("unshare mount namespace", errno);
    if (cfg.net == "none") {
        if (unshare(CLONE_NEWNET) != 0) die("unshare network namespace", errno);
        loopback_up();
    }
    if (mount("tmpfs", STAGE, "tmpfs", MS_NOSUID | MS_NODEV, "mode=0755") != 0) die("mount root tmpfs", errno);
    int root = open(STAGE, O_PATH | O_DIRECTORY | O_CLOEXEC);
    if (root < 0) die("open root", errno);
    size_t mi = 1;
    for (const auto& e : cfg.ns) {
        if (e.kind == "bind") {
            attach(clones[mi], root, e.dst, e.rw, true, e.src);
            ++mi;
        } else if (e.kind == "tmpfs") {
            mount_fs(root, e.dst, "tmpfs", MS_NOSUID | MS_NODEV, "mode=1777");
            ++mi;
        } else if (e.kind == "proc") {
            mount_fs(root, e.dst, "proc", MS_NOSUID | MS_NODEV | MS_NOEXEC, nullptr);
            ++mi;
        } else if (e.kind == "dev") {
            mount_fs(root, e.dst, "tmpfs", MS_NOSUID | MS_NOEXEC, "mode=0755");
            ++mi;
            for (const char* n : DEV_NODES) {
                attach(clones[mi], root, e.dst + "/" + n, true, false, std::string("/dev/") + n);
                ++mi;
            }
            const char* links[][2] = {{"fd", "/proc/self/fd"}, {"stdin", "/proc/self/fd/0"},
                                      {"stdout", "/proc/self/fd/1"}, {"stderr", "/proc/self/fd/2"}};
            int d = openat2_in(root, rel_of(e.dst), O_PATH | O_DIRECTORY);
            if (d < 0) die("open " + e.dst, errno);
            for (auto& l : links)
                if (symlinkat(l[1], d, l[0]) != 0) die("symlink " + e.dst + "/" + l[0], errno);
            if (set_attr(d, "", AT_EMPTY_PATH, MOUNT_ATTR_RDONLY) != 0) die("make " + e.dst + " read-only", errno);
            close(d);
        } else if (e.kind == "symlink") {
            std::string last;
            int pfd = parent_dir(root, e.dst, last);
            if (pfd < 0 || symlinkat(e.src.c_str(), pfd, last.c_str()) != 0) die("symlink " + e.dst, errno);
            close(pfd);
        }
    }
    if (give_aos) {
        // 天空裡的位置：daemon_path（預設 /aos）＝daemon 的目錄（可寫：ctl 要寫），旁邊的 cgroup＝cgroup 夾（procs/<名>/cgroup 的相對連結才通）
        attach(aos_clone, root, init_daemon_path(cfg), true, true, "the daemon's directory");
        if (cg_clone >= 0) attach(cg_clone, root, init_cgroup_path(cfg), true, true, "the cgroup directory");
    }
    if (set_attr(root, "", AT_EMPTY_PATH, MOUNT_ATTR_RDONLY) != 0) die("make root read-only", errno);

    // 4. 換根，舊的根整片卸掉
    if (fchdir(root) != 0) die("chdir root", errno);
    if (syscall(SYS_pivot_root, ".", ".") != 0) die("pivot_root", errno);
    if (umount2(".", MNT_DETACH) != 0) die("detach old root", errno);
    if (chdir("/") != 0) die("chdir /", errno);
    close(root);

    // 5. 進自己的 cgroup（改 uid 之前：cgroup 檔屬於天空裡的 0 號）
    if (!cgroup.empty()) {
        int fd = openat(W.cgfd, (cgroup + "/cgroup.procs").c_str(), O_WRONLY | O_CLOEXEC);
        if (fd < 0 || write(fd, "0", 1) != 1) die("join cgroup " + cgroup, errno);
        close(fd);
    }

    // 6. 告訴 daemon 天空組好了（daemon 趁這時讀 mountinfo），等它說可以走
    say(report_fd, std::string("B") + hp + "\n");
    char g = 0;
    if (read(go, &g, 1) != 1 || g != 'G') _exit(1);

    // 7. 上鎖
    if (W.setgroups_ok && setgroups(0, nullptr) != 0) die("setgroups", errno);
    bool ptrace = init && !give_aos;
    if (ptrace) {
        // ptrace 模式：init 留 CAP_SYS_PTRACE 一個——daemon 的 caps 比它多，沒有這個就讀不到 /proc/1/cwd
        __user_cap_header_struct h{_LINUX_CAPABILITY_VERSION_3, 0};
        __user_cap_data_struct d[2]{};
        if (syscall(SYS_capget, &h, d) != 0) die("capget", errno);
        d[0].inheritable |= 1u << CAP_SYS_PTRACE;
        if (syscall(SYS_capset, &h, d) != 0) die("capset inheritable", errno);
        if (prctl(PR_CAP_AMBIENT, PR_CAP_AMBIENT_RAISE, CAP_SYS_PTRACE, 0, 0) != 0) die("ambient cap_sys_ptrace", errno);
    } else if (prctl(PR_CAP_AMBIENT, PR_CAP_AMBIENT_CLEAR_ALL, 0, 0, 0) != 0) {
        die("clear ambient caps", errno);
    }
    if (prctl(PR_SET_SECUREBITS, SECBITS, 0, 0, 0) != 0) die("securebits", errno);
    for (int c = 0; c < 64; ++c) {
        if (ptrace && c == CAP_SYS_PTRACE) continue;
        if (prctl(PR_CAPBSET_DROP, c, 0, 0, 0) != 0) {
            if (errno == EINVAL) break;
            die("drop bounding cap " + std::to_string(c), errno);
        }
    }
    uid_t u = static_cast<uid_t>(cfg.uid);
    if (setresgid(u, u, u) != 0) die("setresgid", errno);
    if (setresuid(u, u, u) != 0) die("setresuid", errno);
    set_caps(ptrace ? 1ull << CAP_SYS_PTRACE : 0);
    if (prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0) die("no_new_privs", errno);
    if (!init || cfg.landlock) {
        LandlockAttr a{LANDLOCK_ACCESS_FS_MAKE_BLOCK, 0, 0};
        size_t sz = sizeof(uint64_t);
        if (W.landlock_abi >= 6) {
            a.scoped = 0x3;   // LANDLOCK_SCOPE_ABSTRACT_UNIX_SOCKET | LANDLOCK_SCOPE_SIGNAL
            sz = sizeof a;
        }
        int rfd = static_cast<int>(syscall(SYS_landlock_create_ruleset, &a, sz, 0));
        if (rfd < 0) die("landlock ruleset", errno);
        if (syscall(SYS_landlock_restrict_self, rfd, 0) != 0) die("landlock restrict", errno);
        close(rfd);
    }

    // 8. exec
    if (chdir(cfg.cwd.c_str()) != 0) die("chdir " + cfg.cwd, errno);
    if (dup2(fin, 0) < 0 || dup2(fout, 1) < 0 || dup2(ferr, 2) < 0) die("dup2", errno);
    close_range(3, ~0u, CLOSE_RANGE_CLOEXEC);
    execve(argv[0], argv.data(), envp.data());
    die("exec " + cfg.argv[0], errno);
}

// 讀一行（到 \n 或 EOF）；timeout 秒內沒讀完回 false
bool read_msg(int fd, double timeout, std::string& out, bool& eof) {
    out.clear();
    eof = false;
    double end = mono_now() + timeout;
    for (;;) {
        double left = end - mono_now();
        if (left <= 0) return false;
        pollfd p{fd, POLLIN, 0};
        int r = poll(&p, 1, static_cast<int>(left * 1000) + 1);
        if (r < 0 && errno == EINTR) continue;
        if (r <= 0) continue;
        char c;
        ssize_t n = read(fd, &c, 1);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) {
            eof = true;
            return true;
        }
        if (c == '\n') return true;
        out += c;
    }
}

void reap(pid_t pid) {
    int st;
    while (waitpid(pid, &st, 0) < 0 && errno == EINTR) {}
}

std::vector<std::string> locks_of(const ProcConfig& cfg, bool init) {
    std::vector<std::string> l;
    if (!init || cfg.landlock) {
        std::string s = "landlock: own domain (ABI " + std::to_string(W.landlock_abi) + "); fs: make_block handled, no other fs rule; ";
        s += W.landlock_abi >= 6 ? "scoped: signal, abstract unix socket"
                                 : "signal and abstract unix socket scoping not available (needs ABI 6)";
        if (init) s += "; init asked for it (locks.landlock true)";
        l.push_back(s);
    } else {
        l.push_back("landlock: none (init)");
    }
    if (init && init_mounts(cfg)) {
        l.push_back("capabilities: none (bounding set empty)");
        l.push_back("daemon directory: " + init_daemon_path(cfg) + " in its ns (daemon_access mount)" +
                    (W.cgfd >= 0 ? ", cgroup directory at " + init_cgroup_path(cfg) : std::string()));
    } else if (init) {
        l.push_back("capabilities: cap_sys_ptrace only (bounding set: cap_sys_ptrace)");
        l.push_back("daemon directory: /proc/1/cwd (daemon_access ptrace)");
    } else {
        l.push_back("capabilities: none (bounding set empty)");
    }
    l.push_back(cfg.net == "none" ? "net: none (own netns, loopback only)" : "net: host (the daemon's network namespace)");
    l.push_back("securebits: noroot, no_setuid_fixup, keep_caps_locked, no_cap_ambient_raise (all locked)");
    l.push_back("no_new_privs");
    l.push_back(W.setgroups_ok ? "groups: cleared" : "groups: kept (setgroups is denied without newgidmap)");
    l.push_back("ns: root built from zero, read-only root, mount and umount need capabilities it does not have");
    for (const auto& [k, v] : cfg.cgroup) l.push_back("cgroup: " + k + "=" + v);
    return l;
}

// 全部預備好的子行程（跑的時候掛／卸）：進 pid 那隻的天空，fn 在裡面做事；回 "" 或錯誤
template <class F>
std::string in_ns_helper(pid_t pid, const std::string& what, F fn) {
    int st[2];
    if (pipe2(st, O_CLOEXEC) != 0) return "Internal pipe: " + errstr(errno);
    pid_t h = fork();
    if (h < 0) {
        close(st[0]);
        close(st[1]);
        return "Internal fork: " + errstr(errno);
    }
    if (h == 0) {
        close(st[0]);
        report_fd = st[1];
        std::string base = std::to_string(pid);
        int rootfd = openat(W.procfd, (base + "/root").c_str(), O_PATH | O_DIRECTORY | O_CLOEXEC);
        int nsfd = openat(W.procfd, (base + "/ns/mnt").c_str(), O_RDONLY | O_CLOEXEC);
        if (rootfd < 0 || nsfd < 0) die("open the proc's root", errno);
        if (setns(W.orignsfd, CLONE_NEWNS) != 0) die("setns", errno);
        fn(rootfd, nsfd);
        _exit(0);
    }
    close(st[1]);
    std::string msg;
    bool eof;
    bool ok = read_msg(st[0], 10, msg, eof);
    close(st[0]);
    if (!ok) kill(h, SIGKILL);
    reap(h);
    if (!ok) return "Timeout " + what + " took more than 10 s";
    return msg.empty() ? "" : msg.substr(1);
}

void enter_ns(int rootfd, int nsfd) {
    if (setns(nsfd, CLONE_NEWNS) != 0) die("setns into the ns", errno);
    if (fchdir(rootfd) != 0 || chroot(".") != 0 || chdir("/") != 0) die("chroot into the ns", errno);
}

}  // namespace

std::string spawn(const ProcConfig& cfg, bool init, long seq, Spawned& out) {
    if ((!init || cfg.landlock) && W.landlock_abi < 1)
        return std::string("LandlockUnavailable this kernel has no Landlock; ") +
               (init ? "init asked for it (locks.landlock true)" : "only init may run without it");
    if (cfg.uid > 0 && cfg.uid > W.subuid_count)
        return "UidUnavailable uid " + std::to_string(cfg.uid) + " needs a subuid range of at least that size (have " +
               std::to_string(W.subuid_count) + ")";
    out = Spawned{};
    out.mounts = plan_mounts(cfg.ns);
    if (init && init_mounts(cfg)) {
        std::string bad = init_ns_conflict(cfg, W.cgfd >= 0);
        if (!bad.empty()) return bad;
        out.mounts.push_back({"aos", "-", init_daemon_path(cfg), true});
        if (W.cgfd >= 0) out.mounts.push_back({"cgroup", W.cg_host, init_cgroup_path(cfg), true});
    }
    out.locks = locks_of(cfg, init);

    // cgroup：起動前開好、寫好上限
    if (W.cgfd >= 0) {
        out.cgroup = "p-" + cfg.name + "-" + std::to_string(seq);
        if (mkdirat(W.cgfd, out.cgroup.c_str(), 0755) != 0)
            return "CgroupFailed mkdir " + out.cgroup + ": " + errstr(errno);
        for (const auto& [k, v] : cfg.cgroup) {
            int fd = openat(W.cgfd, (out.cgroup + "/" + k).c_str(), O_WRONLY | O_CLOEXEC);
            bool ok = fd >= 0 && write(fd, v.data(), v.size()) == static_cast<ssize_t>(v.size());
            int e = errno;
            if (fd >= 0) close(fd);
            if (!ok) {
                unlinkat(W.cgfd, out.cgroup.c_str(), AT_REMOVEDIR);
                return "CgroupLimitFailed " + k + "=" + v + ": " + errstr(e) +
                       (e == ENOENT ? " (that controller is not delegated here)" : "");
            }
        }
    } else if (!cfg.cgroup.empty()) {
        return "CgroupUnavailable " + W.cg_note;
    }

    // exec 要的東西 fork 之前備好
    std::vector<std::string> env = cfg.env;
    if (env.empty()) env = {"PATH=/usr/local/bin:/usr/bin:/bin", "HOME=/"};
    std::erase_if(env, [](const std::string& e) { return e.rfind("AOS_DAEMON=", 0) == 0 || e.rfind("AOS_NAME=", 0) == 0; });
    // AOS_DAEMON 只給 init：其他 proc 讀不到 daemon 的目錄，給了反而誤導【擬】
    if (init) env.push_back("AOS_DAEMON=" + (init_mounts(cfg) ? init_daemon_path(cfg) : std::string("/proc/1/cwd")));
    env.push_back("AOS_NAME=" + cfg.name);
    std::vector<std::string> args = cfg.argv;
    std::vector<char*> argv, envp;
    for (auto& a : args) argv.push_back(a.data());
    argv.push_back(nullptr);
    for (auto& e : env) envp.push_back(e.data());
    envp.push_back(nullptr);

    int st[2], go[2];
    if (pipe2(st, O_CLOEXEC) != 0) return "Internal pipe: " + errstr(errno);
    if (pipe2(go, O_CLOEXEC) != 0) {
        close(st[0]);
        close(st[1]);
        return "Internal pipe: " + errstr(errno);
    }
    pid_t pid = fork();
    if (pid == 0) {
        close(st[0]);
        close(go[1]);
        report_fd = st[1];
        child(cfg, init, out.mounts, out.cgroup, argv, envp, go[0]);
    }
    close(st[1]);
    close(go[0]);
    auto fail = [&](const std::string& why) {
        close(st[0]);
        close(go[1]);
        if (pid > 0) {
            kill(pid, SIGKILL);
            reap(pid);
        }
        if (!out.cgroup.empty()) unlinkat(W.cgfd, out.cgroup.c_str(), AT_REMOVEDIR);
        return why;
    };
    if (pid < 0) return fail("Internal fork: " + errstr(errno));
    std::string msg;
    bool eof;
    if (!read_msg(st[0], 10, msg, eof)) return fail("Timeout building the ns took more than 10 s");
    if (msg.empty() || msg[0] != 'B') return fail("StartFailed " + (msg.empty() ? "child exited" : msg.substr(1)));
    out.pid = pid;
    out.host_pid = std::atol(msg.c_str() + 1);
    out.ns = ns_table(pid, out.mounts, out.ns_check, out.ns_json);
    if (write(go[1], "G", 1) != 1) return fail("StartFailed child went away");
    close(go[1]);
    go[1] = -1;
    if (!read_msg(st[0], 10, msg, eof)) return fail("Timeout exec took more than 10 s");
    if (!msg.empty()) return fail("StartFailed " + msg.substr(1));
    close(st[0]);
    return "";
}

std::string live_mount(pid_t pid, const std::string& src, const std::string& dst, bool rw) {
    return in_ns_helper(pid, "mount", [&](int rootfd, int nsfd) {
        int c = clone_src(src);
        if (c < 0) die("bind source " + src, errno);
        enter_ns(rootfd, nsfd);
        int root = open("/", O_PATH | O_DIRECTORY | O_CLOEXEC);
        // 掛載點不在而根是唯讀時：暫時把根改成可寫、建好再改回（sky-1125 的做法）
        int t = mkpoint(root, dst, is_dir_fd(c));
        if (t < 0 && errno == EROFS) {
            if (set_attr(root, "", AT_EMPTY_PATH, 0, MOUNT_ATTR_RDONLY) != 0) die("make root writable", errno);
            t = mkpoint(root, dst, is_dir_fd(c));
            int e = errno;
            set_attr(root, "", AT_EMPTY_PATH, MOUNT_ATTR_RDONLY);
            errno = e;
        }
        if (t < 0) die("mount point " + dst, errno);
        close(t);
        attach(c, root, dst, rw, true, src);
    });
}

std::string live_umount(pid_t pid, const std::string& dst) {
    return in_ns_helper(pid, "umount", [&](int rootfd, int nsfd) {
        enter_ns(rootfd, nsfd);
        if (umount2(dst.c_str(), MNT_DETACH | UMOUNT_NOFOLLOW) != 0) die("umount " + dst, errno);
    });
}

}  // namespace d2
