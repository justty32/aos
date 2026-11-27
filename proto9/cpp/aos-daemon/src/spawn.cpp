// spawn.cpp：起一隻 proc（fork 出來的子行程進原本那一層拿來源、根從零組天空、換根、上鎖、exec）與跑的時候掛、卸。
#include "common.hpp"

#include <cerrno>
#include <csignal>
#include <cstring>
#include <fcntl.h>
#include <grp.h>
#include <linux/capability.h>
#include <linux/landlock.h>
#include <linux/seccomp.h>
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

int set_attr(int dfd, const char* path, unsigned flags, uint64_t set, uint64_t clr = 0, uint64_t propagation = 0) {
    mount_attr a{};
    a.attr_set = set;
    a.attr_clr = clr;
    a.propagation = propagation;
    return mount_setattr(dfd, path, flags, &a, sizeof a);
}

// fd 指到的真實位置（照這個行程的根看：子行程進了 daemon 握著的那一層之後，就是那一層看到的路徑）；讀不到回空
std::string fd_path(int fd) {
    char buf[4096];
    ssize_t n = readlinkat(W.procfd, ("self/fd/" + std::to_string(fd)).c_str(), buf, sizeof buf - 1);
    return n > 0 ? std::string(buf, static_cast<size_t>(n)) : std::string();
}

// 外面的一個路徑先 O_PATH 開（beneath 非空：從那個夾往下開，openat2 的 RESOLVE_BENEATH＋RESOLVE_NO_MAGICLINKS，.. 或 symlink
// 帶出那個夾就失敗），讀出真實位置（real），再從這個 fd 複製成一個還沒掛上的掛載；底下有鎖住的子掛載時只能連它們一起帶
// （sky-1125 坑 5）。失敗回 -1、errno 是那一步的，step 說是哪一步
int clone_src(const std::string& src, const std::string& beneath, std::string& real, std::string& step) {
    int fd;
    if (beneath.empty()) {
        fd = open(src.c_str(), O_PATH | O_CLOEXEC);
        if (fd < 0) step = "bind source " + src;
    } else {
        int b = open(beneath.c_str(), O_PATH | O_DIRECTORY | O_CLOEXEC);
        if (b < 0) {
            step = "bind beneath " + beneath;
            return -1;
        }
        std::string rel = src == beneath ? "." : src.substr(beneath == "/" ? 1 : beneath.size() + 1);
        open_how how{};
        how.flags = O_PATH | O_CLOEXEC;
        how.resolve = RESOLVE_BENEATH | RESOLVE_NO_MAGICLINKS;
        fd = static_cast<int>(syscall(SYS_openat2, b, rel.c_str(), &how, sizeof how));
        int e = errno;
        close(b);
        errno = e;
        if (fd < 0)
            step = "bind source " + src + " beneath " + beneath +
                   (e == EXDEV ? " (a .. or a symlink leads out of " + beneath + ")"
                               : e == ELOOP ? " (a /proc magic link or too many symlinks)" : "");
    }
    if (fd < 0) return -1;
    real = fd_path(fd);
    int c = open_tree(fd, "", OPEN_TREE_CLONE | OPEN_TREE_CLOEXEC | AT_EMPTY_PATH);
    if (c < 0 && errno == EINVAL) c = open_tree(fd, "", OPEN_TREE_CLONE | OPEN_TREE_CLOEXEC | AT_EMPTY_PATH | AT_RECURSIVE);
    int e = errno;
    close(fd);
    errno = e;
    if (c < 0) step = "bind source " + src;
    return c;
}

// 新開一塊檔案系統（tmpfs、proc）成還沒掛上的掛載：fsopen／fsconfig／fsmount（不經路徑）。失敗回 -1，step 說是哪一步
int new_fs(const char* type, uint64_t attrs, const std::vector<std::pair<std::string, std::string>>& opts, std::string& step) {
    int fs = fsopen(type, FSOPEN_CLOEXEC);
    if (fs < 0) {
        step = std::string("fsopen ") + type;
        return -1;
    }
    int m = -1;
    for (const auto& [k, v] : opts)
        if (fsconfig(fs, FSCONFIG_SET_STRING, k.c_str(), v.c_str(), 0) != 0) {
            step = std::string(type) + " option " + k + "=" + v;
            break;
        }
    if (step.empty()) {
        if (fsconfig(fs, FSCONFIG_CMD_CREATE, nullptr, nullptr, 0) != 0) step = std::string("create ") + type;
        else if ((m = fsmount(fs, FSMOUNT_CLOEXEC, attrs)) < 0) step = std::string("fsmount ") + type;
    }
    int e = errno;
    close(fs);
    errno = e;
    return m;
}

// overlay（唯讀，沒有 upper）：用 fsopen／fsconfig／fsmount 疊成一個還沒掛上的掛載（跟 bind 的 clone 一樣之後再 attach）。
// 在原本那一層叫：lower 照外面的路徑解；路徑裡的 \ 與 : 照 overlayfs 的寫法加 \。失敗回 -1、errno 是那一步的，step 說是哪一步
int overlay_mount(const std::vector<std::string>& lower, std::string& step) {
    std::string spec;
    for (const auto& l : lower) {
        if (!spec.empty()) spec += ':';
        for (char c : l) {
            if (c == '\\' || c == ':') spec += '\\';
            spec += c;
        }
    }
    int fs = fsopen("overlay", FSOPEN_CLOEXEC);
    if (fs < 0) {
        step = "fsopen overlay";
        return -1;
    }
    int m = -1;
    if (fsconfig(fs, FSCONFIG_SET_STRING, "lowerdir", spec.c_str(), 0) != 0) step = "overlay lowerdir";
    else if (fsconfig(fs, FSCONFIG_SET_FLAG, "ro", nullptr, 0) != 0) step = "overlay ro";
    else if (fsconfig(fs, FSCONFIG_CMD_CREATE, nullptr, nullptr, 0) != 0) step = "create overlay";
    else if ((m = fsmount(fs, FSMOUNT_CLOEXEC, MOUNT_ATTR_RDONLY | MOUNT_ATTR_NOSUID | MOUNT_ATTR_NODEV)) < 0) step = "fsmount overlay";
    int e = errno;
    close(fs);
    errno = e;
    return m;
}

bool is_dir_fd(int fd) {
    struct stat st;
    return fstat(fd, &st) == 0 && S_ISDIR(st.st_mode);
}

// 複製來的掛載掛進天空：nosuid、（nodev）、唯讀與否；傳播設成 private（daemon 握著的那一層是 slave、會收外面的掛卸，
// 複製出來的那份要是不改，天空會在背後跟著外面變）
void attach(int clone, int root, const std::string& dst, bool rw, bool nodev, const std::string& what) {
    int t = mkpoint(root, dst, is_dir_fd(clone));
    if (t < 0) die("mount point " + dst, errno);
    uint64_t set = MOUNT_ATTR_NOSUID | (nodev ? MOUNT_ATTR_NODEV : 0) | (rw ? 0 : MOUNT_ATTR_RDONLY);
    if (set_attr(clone, "", AT_EMPTY_PATH | AT_RECURSIVE, set, 0, MS_PRIVATE) != 0) die("set flags on " + what, errno);
    if (move_mount(clone, "", t, "", MOVE_MOUNT_F_EMPTY_PATH | MOVE_MOUNT_T_EMPTY_PATH) != 0) die("attach " + what, errno);
    close(t);
    close(clone);
}

// 新開一塊檔案系統掛到天空的 dst（掛載點用 fd，不經 /proc/self/fd 的路徑）
void mount_fs(int root, const std::string& dst, const char* type, uint64_t attrs,
              const std::vector<std::pair<std::string, std::string>>& opts) {
    int t = mkpoint(root, dst, true);
    if (t < 0) die("mount point " + dst, errno);
    std::string step;
    int m = new_fs(type, attrs, opts, step);
    if (m < 0) die(step + " at " + dst, errno);
    if (move_mount(m, "", t, "", MOVE_MOUNT_F_EMPTY_PATH | MOVE_MOUNT_T_EMPTY_PATH) != 0)
        die(std::string("mount ") + type + " at " + dst, errno);
    close(m);
    close(t);
}

std::vector<std::pair<std::string, std::string>> tmpfs_opts(const char* mode, const std::string& size) {
    std::vector<std::pair<std::string, std::string>> o{{"mode", mode}};
    if (!size.empty()) o.emplace_back("size", size);
    return o;
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
                        const std::string& cgroup, std::vector<char*>& argv, std::vector<char*>& envp, int go,
                        std::vector<sock_filter>& filter) {
    sigset_t none;
    sigemptyset(&none);
    sigprocmask(SIG_SETMASK, &none, nullptr);
    for (int s = 1; s < 32; ++s)
        if (s != SIGKILL && s != SIGSTOP) signal(s, SIG_DFL);
    setsid();
    // init：daemon 的目錄（與 cgroup 夾）只在 daemon 的小世界裡（/aos、/cgroup），趁還在這裡先複製成還沒掛上的掛載
    int aos_clone = -1, cg_clone = -1;
    if (init) {
        aos_clone = open_tree(AT_FDCWD, "/aos", OPEN_TREE_CLONE | OPEN_TREE_CLOEXEC);
        if (aos_clone < 0) die("clone the daemon's directory", errno);
        if (W.cgfd >= 0 && (cg_clone = open_tree(AT_FDCWD, "/cgroup", OPEN_TREE_CLONE | OPEN_TREE_CLOEXEC)) < 0)
            die("clone the cgroup directory", errno);
    }

    // 1. 進原本那一層（daemon 換根之前的世界、daemon 握著的那一層）：設定裡的路徑都照那一層解
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

    // 2. 來源先全部拿好（bind 複製成還沒掛上的掛載；overlay 照外面的路徑疊好、也是還沒掛上的掛載），順便量出真實位置
    //    （ns.json 的 real），一條一行 "R<第幾個>\t<路徑>…" 先告訴 daemon（路徑照天空表的寫法跳脫，不會有 tab、換行）
    std::vector<int> clones(mounts.size(), -1);
    for (size_t i = 0; i < mounts.size(); ++i) {
        std::string step;
        std::vector<std::string> reals;
        if (mounts[i].kind == "bind") {
            std::string real;
            if ((clones[i] = clone_src(mounts[i].src, mounts[i].beneath, real, step)) < 0) die(step, errno);
            reals.push_back(real);
        } else if (mounts[i].kind == "overlay") {
            for (const auto& l : mounts[i].lower) {
                int fd = open(l.c_str(), O_PATH | O_DIRECTORY | O_CLOEXEC);
                if (fd < 0) die("overlay lower " + l, errno);
                reals.push_back(fd_path(fd));
                close(fd);
            }
            if ((clones[i] = overlay_mount(reals, step)) < 0) die(step + " (" + mounts[i].src + ")", errno);
        }
        if (reals.empty()) continue;
        std::string line = "R" + std::to_string(i);
        for (const auto& r : reals) line += "\t" + esc(r);
        say(report_fd, line + "\n");
    }

    // 3. 自己一份 mount namespace，根從一塊新的 tmpfs 組起；net none 時順便開自己的 network namespace、打開 lo。
    //    根那塊 tmpfs 掛在這份的 "/" 上面（不靠外面要有哪個夾當墊腳；以前墊在 /tmp），之後 pivot_root 換過去
    if (unshare(CLONE_NEWNS) != 0) die("unshare mount namespace", errno);
    // 每隻（含 init）自己一份 IPC namespace（最小方案第 5 節第 8 條：每隻都開、不做開關）：SysV 共享記憶體／號誌／訊息佇列與
    // POSIX mqueue 只在自己這份裡，外面、兄弟建的看不到，自己建的也出不去；新的這份屬於 daemon 的 user namespace
    if (unshare(CLONE_NEWIPC) != 0) die("unshare ipc namespace", errno);
    if (cfg.net == "none") {
        if (unshare(CLONE_NEWNET) != 0) die("unshare network namespace", errno);
        loopback_up();
    }
    std::string step;
    int root = new_fs("tmpfs", MOUNT_ATTR_NOSUID | MOUNT_ATTR_NODEV, tmpfs_opts("0755", cfg.root_size), step);
    if (root < 0) die(step + " (the root)", errno);
    if (move_mount(root, "", AT_FDCWD, "/", MOVE_MOUNT_F_EMPTY_PATH) != 0) die("attach the root tmpfs", errno);
    size_t mi = 1;
    for (const auto& e : cfg.ns) {
        if (e.kind == "bind") {
            attach(clones[mi], root, e.dst, e.rw, true, e.src);
            ++mi;
        } else if (e.kind == "tmpfs") {
            mount_fs(root, e.dst, "tmpfs", MOUNT_ATTR_NOSUID | MOUNT_ATTR_NODEV, tmpfs_opts("1777", e.size));
            ++mi;
        } else if (e.kind == "proc") {
            mount_fs(root, e.dst, "proc", MOUNT_ATTR_NOSUID | MOUNT_ATTR_NODEV | MOUNT_ATTR_NOEXEC, {});
            ++mi;
        } else if (e.kind == "overlay") {
            attach(clones[mi], root, e.dst, false, true, "overlay at " + e.dst);
            ++mi;
        } else if (e.kind == "dev") {
            mount_fs(root, e.dst, "tmpfs", MOUNT_ATTR_NOSUID | MOUNT_ATTR_NOEXEC, tmpfs_opts("0755", ""));
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
    if (init) {
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
    if (prctl(PR_CAP_AMBIENT, PR_CAP_AMBIENT_CLEAR_ALL, 0, 0, 0) != 0) die("clear ambient caps", errno);
    if (prctl(PR_SET_SECUREBITS, SECBITS, 0, 0, 0) != 0) die("securebits", errno);
    for (int c = 0; c < 64; ++c) {
        if (prctl(PR_CAPBSET_DROP, c, 0, 0, 0) != 0) {
            if (errno == EINVAL) break;
            die("drop bounding cap " + std::to_string(c), errno);
        }
    }
    uid_t u = static_cast<uid_t>(cfg.uid);
    if (setresgid(u, u, u) != 0) die("setresgid", errno);
    if (setresuid(u, u, u) != 0) die("setresuid", errno);
    set_caps(0);
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
    // seccomp：exec 前最後一步（no_new_privs、Landlock 之後），daemon 自己的預備不受影響；過濾器 fork 前就組好了
    if (!filter.empty()) {
        sock_fprog prog{static_cast<unsigned short>(filter.size()), filter.data()};
        if (syscall(SYS_seccomp, SECCOMP_SET_MODE_FILTER, 0, &prog) != 0) die("seccomp", errno);
    }
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

// 等 pid 結束最多 secs 秒（WNOHANG 輪詢，monotonic）；收到了回 true。沒收到（例如卡在不回應的檔案系統上，SIGKILL 也要等那個
// 請求回來）就回 false、不再等：那個 PID 留給主循環平常的 reap_all 收（它略過不認得的 PID）
bool reap_within(pid_t pid, double secs) {
    double end = mono_now() + secs;
    for (;;) {
        int st;
        pid_t r = waitpid(pid, &st, WNOHANG);
        if (r == pid || (r < 0 && errno != EINTR)) return true;
        if (mono_now() >= end) return false;
        usleep(2000);
    }
}

// 子行程（起 proc 的、跑的時候掛卸的幫手）失敗或逾時：SIGKILL，最多等 KILL_WAIT 秒，沒走就留給主循環收
const double KILL_WAIT = 0.5;
bool kill_and_leave(pid_t pid, const std::string& what) {
    kill(pid, SIGKILL);
    if (reap_within(pid, KILL_WAIT)) return true;
    log(what + ": pid " + std::to_string(pid) + " did not exit " + seconds_text(KILL_WAIT) +
        " s after SIGKILL (stuck in the kernel?); not waiting for it, the main loop reaps it when it goes");
    return false;
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
    l.push_back("capabilities: none (bounding set empty)");
    if (init)
        l.push_back("daemon directory: " + init_daemon_path(cfg) + " in its ns" +
                    (W.cgfd >= 0 ? ", cgroup directory at " + init_cgroup_path(cfg) : std::string()));
    // Landlock ABI 6 以前擋不住訊號：uid 0 的 proc（外面的使用者本人）送得到 init 與其他 uid 0 的 proc（daemon 自己不理它送的停止訊號）
    if (!init && cfg.uid == 0 && W.landlock_abi < 6)
        l.push_back("signals: can signal init and other uid-0 procs (Landlock ABI " + std::to_string(W.landlock_abi) +
                    " has no signal scoping; the daemon ignores stop signals from it)");
    l.push_back(cfg.net == "none" ? "net: none (own netns, loopback only)" : "net: host (the daemon's network namespace)");
    l.push_back("ipc: own ipc namespace (SysV shm, semaphores, message queues and POSIX mqueues are its own)");
    l.push_back("securebits: noroot, no_setuid_fixup, keep_caps_locked, no_cap_ambient_raise (all locked)");
    l.push_back("no_new_privs");
    l.push_back(seccomp_lock_line(cfg));
    l.push_back(W.setgroups_ok ? "groups: cleared" : "groups: kept (setgroups is denied without newgidmap)");
    l.push_back("ns: root built from zero, read-only root, mount and umount need capabilities it does not have");
    for (const auto& [k, v] : cfg.cgroup) l.push_back("cgroup: " + k + "=" + v);
    return l;
}

// 全部預備好的子行程（跑的時候掛／卸）：進 pid 那隻的天空，fn 在裡面做事；回 "" 或錯誤。
// 幫手成功時可以寫一行 "R<路徑>"（跳脫過的）回來，放進 real
template <class F>
std::string in_ns_helper(pid_t pid, const std::string& what, F fn, std::string* real = nullptr) {
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
    if (!ok) {
        // 卡住了（例如來源在不回應的 FUSE 上）：不等它，主循環之後收
        kill_and_leave(h, what + " helper");
        return "Timeout " + what + " took more than 10 s";
    }
    // 幫手寫完（或沒寫）就 _exit 了；照理馬上收得到，收不到也不等
    if (!reap_within(h, 1)) log(what + " helper: pid " + std::to_string(h) + " has not exited yet; the main loop reaps it");
    if (!msg.empty() && msg[0] == 'R') {
        if (real) *real = unesc(msg.substr(1));
        return "";
    }
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
    out.mounts = plan_mounts(cfg);
    if (init) {
        std::string bad = init_ns_conflict(cfg, W.cgfd >= 0);
        if (!bad.empty()) return bad;
        Mount a{"aos", "-", init_daemon_path(cfg), true};
        a.by = "daemon";   // daemon 自己加的（設定裡沒有）
        out.mounts.push_back(a);
        if (W.cgfd >= 0) {
            Mount c{"cgroup", W.cg_host, init_cgroup_path(cfg), true};
            c.by = "daemon";
            c.real = W.cg_host;   // daemon 起動時開的 cgroup 夾（小世界裡的 cgroup/ 就是它）
            out.mounts.push_back(c);
        }
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
    if (init) env.push_back("AOS_DAEMON=" + init_daemon_path(cfg));
    env.push_back("AOS_NAME=" + cfg.name);
    std::vector<std::string> args = cfg.argv;
    std::vector<char*> argv, envp;
    for (auto& a : args) argv.push_back(a.data());
    argv.push_back(nullptr);
    for (auto& e : env) envp.push_back(e.data());
    envp.push_back(nullptr);
    std::vector<sock_filter> filter = seccomp_filter(cfg);

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
        child(cfg, init, out.mounts, out.cgroup, argv, envp, go[0], filter);
    }
    close(st[1]);
    close(go[0]);
    auto fail = [&](const std::string& why) {
        close(st[0]);
        if (go[1] >= 0) close(go[1]);
        // 不用會一直等的 waitpid：卡在核心裡的子行程（bind 來源在不回應的檔案系統上）SIGKILL 也要等那個請求回來
        if (pid > 0) kill_and_leave(pid, "start " + cfg.name);
        // 卡在進 cgroup 之前的（例如拿 bind 來源時）夾是空的，照樣刪得掉；子行程還在夾裡（EBUSY）就記下來，主循環之後再刪
        if (!out.cgroup.empty() && unlinkat(W.cgfd, out.cgroup.c_str(), AT_REMOVEDIR) != 0 && errno != ENOENT)
            cgroup_remove_later(out.cgroup);
        return why;
    };
    if (pid < 0) return fail("Internal fork: " + errstr(errno));
    std::string msg;
    bool eof;
    // 先是每個來源的真實位置（R 行），再是「組好了」（B 行）；全部一起算 10 秒
    double build_end = mono_now() + 10;
    for (;;) {
        if (!read_msg(st[0], build_end - mono_now(), msg, eof)) return fail("Timeout building the ns took more than 10 s");
        if (msg.empty() || msg[0] != 'R') break;
        size_t tab = msg.find('\t');
        size_t i = static_cast<size_t>(std::atol(msg.c_str() + 1));
        if (tab == std::string::npos || i >= out.mounts.size()) continue;
        std::vector<std::string> reals;
        for (size_t at = tab; at != std::string::npos;) {
            size_t next = msg.find('\t', at + 1);
            reals.push_back(unesc(msg.substr(at + 1, next == std::string::npos ? std::string::npos : next - at - 1)));
            at = next;
        }
        if (out.mounts[i].kind == "overlay") out.mounts[i].real_lower = reals;
        else out.mounts[i].real = reals[0];
    }
    if (msg.empty() || msg[0] != 'B') return fail("StartFailed " + (msg.empty() ? "child exited" : msg.substr(1)));
    out.pid = pid;
    out.host_pid = std::atol(msg.c_str() + 1);
    std::string now = iso_now();   // ns.json 的 at：天空組好的時間
    for (auto& m : out.mounts) m.at = now;
    out.ns = ns_table(pid, out.mounts, out.ns_check, out.ns_json);
    if (write(go[1], "G", 1) != 1) return fail("StartFailed child went away");
    close(go[1]);
    go[1] = -1;
    if (!read_msg(st[0], 10, msg, eof)) return fail("Timeout exec took more than 10 s");
    if (!msg.empty()) return fail("StartFailed " + msg.substr(1));
    close(st[0]);
    return "";
}

std::string live_mount(pid_t pid, const std::string& src, const std::string& dst, bool rw, std::string& real) {
    return in_ns_helper(pid, "mount", [&](int rootfd, int nsfd) {
        std::string r, step;
        int c = clone_src(src, "", r, step);
        if (c < 0) die(step, errno);
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
        say(report_fd, "R" + esc(r) + "\n");
    }, &real);
}

std::string live_umount(pid_t pid, const std::string& dst) {
    return in_ns_helper(pid, "umount", [&](int rootfd, int nsfd) {
        enter_ns(rootfd, nsfd);
        if (umount2(dst.c_str(), MNT_DETACH | UMOUNT_NOFOLLOW) != 0) die("umount " + dst, errno);
    });
}

}  // namespace d2
