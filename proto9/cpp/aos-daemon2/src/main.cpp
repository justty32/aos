// main.cpp：aos-daemon2 的入口與起動那一層——讀參數、備好 cgroup（需要時經 systemd-run 進一個 scope）、開 user／PID／mount namespace、寫 uid/gid 對照表、轉送訊號、收尾。
#include "common.hpp"

#include <cerrno>
#include <dirent.h>
#include <climits>
#include <csignal>
#include <cstring>
#include <fcntl.h>
#include <fstream>
#include <iostream>
#include <sched.h>
#include <sstream>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include <unistd.h>

using namespace d2;

namespace {

const char* HELP = R"(aos-daemon2 - the daemon gives facts and tools; all judgement belongs to one main kernel.

usage: aos-daemon2 --kernel CONFIG [flags]

Starts without root: a new user namespace (you are uid 0 inside, plus your subuid range),
a new PID namespace (the daemon is PID 1 there) and a new mount namespace. The daemon serves
one directory and stands in it; once ready it prints
    export AOS_DAEMON=/proc/<PID>/cwd
on stdout. Only the main kernel gets AOS_DAEMON in its environment; other procs do not.
The daemon itself then lives in a small world that holds only that directory (and the cgroup
switches): /proc/<PID>/root shows nothing else.

The main kernel (CONFIG, same JSON format as `start`) is started first. It is the only proc
without a Landlock domain, and it must run as uid 0 in its ns (any other "uid" in its
config: the daemon refuses to start, exit 2). By default ("daemon_access": "mount") the
directory is mounted in its ns at /aos (cgroup directory at /cgroup, when there is one), AOS_DAEMON=/aos,
and it has no capabilities; with "daemon_access": "ptrace" it keeps cap_sys_ptrace and
reads /proc/1/cwd. In mount mode its own ns config may not use /aos or /cgroup (exit 2).

Directory:
  status           daemon facts and the feedback of the last ctl command
  ctl              tools, one command per write:
                     start CONFIG_PATH            (a JSON file, path as seen where the daemon started)
                     kill NAME SIGNAL             (no graceful stop: send TERM, wait, send KILL yourself)
                     mount NAME [-w] SRC DST      (bind SRC into a running proc's ns; read-only unless -w)
                     umount NAME DST
                     forget NAME                  (remove a dead proc from the table)
  procs/NAME/      a real folder per proc, with the files
                     name pid state exit started_at ended_at ns ns_check uid locks config
                   and, when there is a cgroup, cgroup -> its cgroup directory
                   (cpu.max, memory.max, cgroup.freeze, ...)

flags:
  --kernel CONFIG          main kernel config (required)
  --on-kernel-exit MODE    restart (default) or exit
  --restart-limit N        stop restarting (and exit) after more than N deaths ... (default 5)
  --restart-window S       ... within S seconds (default 60)
  --cgroup auto|off        auto (default): use a delegated cgroup; re-run itself under
                           `systemd-run --user --scope -p Delegate=yes` if needed and possible
  --subuid auto|off        auto (default): map the /etc/subuid range with newuidmap/newgidmap
  -h, --help               show this help

Exit code: 0 after SIGTERM/SIGINT/SIGHUP; the main kernel's code (128+signal) with
--on-kernel-exit exit; 1 when the restart limit is reached; 2 on startup errors.
)";

int usage_error(const std::string& why) {
    std::cerr << "aos-daemon2: error: " << why << " (see aos-daemon2 --help)\n";
    return 2;
}

std::string find_in_path(const std::string& prog) {
    const char* path = getenv("PATH");
    std::istringstream in(path ? path : "/usr/bin:/bin");
    for (std::string dir; std::getline(in, dir, ':');) {
        std::string p = (dir.empty() ? "." : dir) + "/" + prog;
        if (access(p.c_str(), X_OK) == 0) return p;
    }
    return "";
}

int run(const std::vector<std::string>& args, bool quiet) {
    pid_t pid = fork();
    if (pid == 0) {
        sigset_t none;
        sigemptyset(&none);
        sigprocmask(SIG_SETMASK, &none, nullptr);
        if (quiet) {
            int fd = open("/dev/null", O_WRONLY);
            dup2(fd, 1);
            dup2(fd, 2);
        }
        std::vector<char*> av;
        for (const auto& a : args) av.push_back(const_cast<char*>(a.c_str()));
        av.push_back(nullptr);
        execv(av[0], av.data());
        _exit(127);
    }
    if (pid < 0) return -1;
    int st = 0;
    while (waitpid(pid, &st, 0) < 0 && errno == EINTR) {}
    return WIFEXITED(st) ? WEXITSTATUS(st) : 128 + WTERMSIG(st);
}

bool write_file(const std::string& path, const std::string& s) {
    int fd = open(path.c_str(), O_WRONLY | O_CLOEXEC);
    if (fd < 0) return false;
    bool ok = write(fd, s.data(), s.size()) == static_cast<ssize_t>(s.size());
    close(fd);
    return ok;
}

std::string read_text(const std::string& path) {
    std::ifstream f(path);
    return std::string((std::istreambuf_iterator<char>(f)), {});
}

// /etc/subuid 的一行 name:start:count 或 uid:start:count
bool subid_range(const char* file, const std::string& user, long uid, long& start, long& count) {
    std::istringstream in(read_text(file));
    for (std::string line; std::getline(in, line);) {
        std::istringstream ls(line);
        std::string who, s, c;
        if (!std::getline(ls, who, ':') || !std::getline(ls, s, ':') || !std::getline(ls, c)) continue;
        if (who == user || who == std::to_string(uid)) {
            start = std::atol(s.c_str());
            count = std::atol(c.c_str());
            return count > 0;
        }
    }
    return false;
}

std::string user_name() {
    std::istringstream in(read_text("/etc/passwd"));
    for (std::string line; std::getline(in, line);) {
        std::istringstream ls(line);
        std::string name, x, uid;
        if (std::getline(ls, name, ':') && std::getline(ls, x, ':') && std::getline(ls, uid, ':') &&
            uid == std::to_string(getuid()))
            return name;
    }
    const char* u = getenv("USER");
    return u ? u : "";
}

std::string own_cgroup() {
    std::istringstream in(read_text("/proc/self/cgroup"));
    for (std::string line; std::getline(in, line);)
        if (line.rfind("0::", 0) == 0) return line.substr(3);
    return "";
}

struct Cgroup {
    std::string dir;                  // 交給 daemon 的夾（scope），空＝沒有
    std::string note;
    std::vector<std::string> enabled;
};

// 在 scope 裡：自己搬進 scope/daemon（v2 規定開了 controller 的夾不能直接放行程），再把 controller 開給底下
Cgroup prepare_cgroup(const Options& o, char** argv) {
    Cgroup c;
    if (!o.cgroup_auto) {
        c.note = "--cgroup off";
        return c;
    }
    if (!getenv("AOS_DAEMON2_IN_SCOPE")) {
        std::string sr = find_in_path("systemd-run"), sc = find_in_path("systemctl");
        if (sr.empty() || sc.empty() || run({sc, "--user", "show", "-p", "Version"}, true) != 0) {
            c.note = "no systemd --user to give a delegated cgroup";
            return c;
        }
        char self[PATH_MAX];
        ssize_t n = readlink("/proc/self/exe", self, sizeof self - 1);
        if (n <= 0) {
            c.note = "cannot find own executable";
            return c;
        }
        self[n] = 0;
        setenv("AOS_DAEMON2_IN_SCOPE", "1", 1);
        std::vector<std::string> args = {sr, "--user", "--scope", "--quiet", "--collect", "-p", "Delegate=yes",
                                         "--unit=aos-daemon2-" + std::to_string(getpid()), "--", self};
        for (char** a = argv + 1; *a; ++a) args.push_back(*a);
        std::vector<char*> av;
        for (auto& a : args) av.push_back(a.data());
        av.push_back(nullptr);
        execv(av[0], av.data());
        unsetenv("AOS_DAEMON2_IN_SCOPE");
        c.note = "systemd-run: " + errstr(errno);
        return c;
    }
    std::string rel = own_cgroup();
    std::string dir = "/sys/fs/cgroup" + rel;
    if (rel.find("/aos-daemon2-") == std::string::npos || access((dir + "/cgroup.subtree_control").c_str(), W_OK) != 0) {
        c.note = "not in a delegated aos-daemon2 scope (" + rel + ")";
        return c;
    }
    if (mkdir((dir + "/daemon").c_str(), 0755) != 0 && errno != EEXIST) {
        c.note = "mkdir " + dir + "/daemon: " + errstr(errno);
        return c;
    }
    if (!write_file(dir + "/daemon/cgroup.procs", "0")) {
        c.note = "move into " + dir + "/daemon: " + errstr(errno);
        return c;
    }
    std::istringstream ctrls(read_text(dir + "/cgroup.controllers"));
    for (std::string x; ctrls >> x;)
        if (write_file(dir + "/cgroup.subtree_control", "+" + x)) c.enabled.push_back(x);
    c.dir = dir;
    return c;
}

// daemon 結束後：清掉它開的 p-* 夾，自己搬回 scope、拿掉 daemon/，scope 由 systemd 收
void cleanup_cgroup(const Cgroup& c) {
    if (c.dir.empty()) return;
    for (int round = 0; round < 100; ++round) {
        bool left = false;
        if (auto* d = opendir(c.dir.c_str())) {
            while (auto* e = readdir(d)) {
                std::string n = e->d_name;
                if (n.rfind("p-", 0) == 0 && e->d_type == DT_DIR && rmdir((c.dir + "/" + n).c_str()) != 0) left = true;
            }
            closedir(d);
        }
        if (!left) break;
        usleep(20000);
    }
    for (auto it = c.enabled.rbegin(); it != c.enabled.rend(); ++it) write_file(c.dir + "/cgroup.subtree_control", "-" + *it);
    if (write_file(c.dir + "/cgroup.procs", "0")) rmdir((c.dir + "/daemon").c_str());
}

}  // namespace

int main(int argc, char** argv) {
    Options o;
    for (int i = 1; i < argc; ++i) {
        std::string a = argv[i];
        auto val = [&]() -> std::string {
            if (i + 1 >= argc) throw std::invalid_argument(a + " needs a value");
            return argv[++i];
        };
        try {
            if (a == "-h" || a == "--help") {
                std::cout << HELP;
                return 0;
            } else if (a == "--kernel") {
                o.kernel_path = val();
            } else if (a == "--on-kernel-exit") {
                std::string v = val();
                if (v != "restart" && v != "exit") return usage_error("--on-kernel-exit is restart or exit");
                o.restart = v == "restart";
            } else if (a == "--restart-limit") {
                o.restart_limit = std::stoi(val());
                if (o.restart_limit < 0) return usage_error("--restart-limit must be >= 0");
            } else if (a == "--restart-window") {
                o.restart_window = std::stod(val());
                if (!(o.restart_window > 0)) return usage_error("--restart-window must be > 0");
            } else if (a == "--cgroup" || a == "--subuid") {
                std::string v = val();
                if (v != "auto" && v != "off") return usage_error(a + " is auto or off");
                (a == "--cgroup" ? o.cgroup_auto : o.subuid_auto) = v == "auto";
            } else {
                return usage_error("unknown argument " + a);
            }
        } catch (const std::exception& e) {
            return usage_error(std::string("bad value: ") + e.what());
        }
    }
    if (o.kernel_path.empty()) return usage_error("--kernel CONFIG is required");
    if (o.kernel_path[0] != '/') {
        char cwd[PATH_MAX];
        if (!getcwd(cwd, sizeof cwd)) return usage_error("getcwd failed");
        o.kernel_path = std::string(cwd) + "/" + o.kernel_path;
    }
    if (access(o.kernel_path.c_str(), R_OK) != 0)
        return usage_error("cannot read " + o.kernel_path + ": " + errstr(errno));

    Cgroup cg = prepare_cgroup(o, argv);   // 可能 exec systemd-run 再回到這裡（在 scope 裡）
    if (!cg.dir.empty()) setenv("AOS_DAEMON2_CGROUP", cg.dir.c_str(), 1);
    else setenv("AOS_DAEMON2_CGROUP_NOTE", cg.note.c_str(), 1);

    long uid = getuid(), gid = getgid(), sub_start = 0, sub_count = 0, gsub_start = 0, gsub_count = 0;
    std::string user = user_name();
    std::string nuid = find_in_path("newuidmap"), ngid = find_in_path("newgidmap");
    bool sub = o.subuid_auto && !nuid.empty() && !ngid.empty() &&
               subid_range("/etc/subuid", user, uid, sub_start, sub_count) &&
               subid_range("/etc/subgid", user, uid, gsub_start, gsub_count);
    if (sub) sub_count = std::min(std::min(sub_count, gsub_count), 65535L);

    sigset_t sigs;
    sigemptyset(&sigs);
    for (int s : {SIGCHLD, SIGTERM, SIGINT, SIGHUP}) sigaddset(&sigs, s);
    sigprocmask(SIG_BLOCK, &sigs, nullptr);

    int sync[2];
    if (pipe2(sync, O_CLOEXEC) != 0) return usage_error("pipe failed");
    std::cout.flush();
    std::cerr.flush();
    pid_t pid = static_cast<pid_t>(syscall(SYS_clone, CLONE_NEWUSER | CLONE_NEWPID | CLONE_NEWNS | SIGCHLD, nullptr, nullptr, nullptr, 0));
    if (pid < 0) return usage_error(std::string("clone with new namespaces: ") + errstr(errno));
    if (pid == 0) {
        close(sync[1]);
        daemon_main(o, sync[0]);
    }
    close(sync[0]);

    // uid/gid 對照表：自己＝裡面的 0 號；有 subuid 就接在 1 號起
    bool ok;
    std::string p = std::to_string(pid);
    if (sub) {
        ok = run({nuid, p, "0", std::to_string(uid), "1", "1", std::to_string(sub_start), std::to_string(sub_count)}, false) == 0 &&
             run({ngid, p, "0", std::to_string(gid), "1", "1", std::to_string(gsub_start), std::to_string(sub_count)}, false) == 0;
    } else {
        ok = write_file("/proc/" + p + "/uid_map", "0 " + std::to_string(uid) + " 1\n") &&
             write_file("/proc/" + p + "/setgroups", "deny") &&
             write_file("/proc/" + p + "/gid_map", "0 " + std::to_string(gid) + " 1\n");
    }
    if (!ok) {
        kill(pid, SIGKILL);
        waitpid(pid, nullptr, 0);
        cleanup_cgroup(cg);
        return usage_error("could not write the uid/gid maps of the daemon");
    }
    long info[6] = {pid, sub ? 1L : 0L, sub ? sub_start : 0, sub ? sub_count : 0, uid, gid};
    if (write(sync[1], info, sizeof info) != static_cast<ssize_t>(sizeof info)) {}
    close(sync[1]);

    // 轉送訊號給 daemon，等它結束
    int status = 0;
    for (;;) {
        siginfo_t si;
        int s = sigwaitinfo(&sigs, &si);
        if (s < 0) continue;
        if (s == SIGCHLD) {
            pid_t r = waitpid(pid, &status, WNOHANG);
            if (r == pid) break;
            continue;
        }
        kill(pid, s);
    }
    cleanup_cgroup(cg);
    return WIFEXITED(status) ? WEXITSTATUS(status) : 128 + WTERMSIG(status);
}
