// main.cpp：aos-daemon 的入口與起動那一層——讀 daemon 設定檔與參數（參數蓋過檔）、備好 cgroup（需要時經 systemd-run 進一個 scope）、開 user／PID／mount namespace、寫 uid/gid 對照表、轉送訊號、收尾。
#include "common.hpp"

#include "nlohmann/json.hpp"

#include <algorithm>
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

const char* HELP = R"(aos-daemon - the daemon gives facts and tools; all judgement belongs to init.

usage: aos-daemon DAEMON_CONFIG [flags]
       aos-daemon --init CONFIG [flags]

Starts without root: a new user namespace (you are uid 0 inside, plus your subuid range),
a new PID namespace (the daemon is PID 1 there) and a new mount namespace. The daemon serves
one directory and stands in it; once ready it prints
    export AOS_DAEMON=/proc/<PID>/cwd
on stdout. Only init gets AOS_DAEMON in its environment; other procs do not.
The daemon itself then lives in a small world that holds only that directory (and the cgroup
switches): /proc/<PID>/root shows nothing else.

init (CONFIG, same JSON format as `start`) is the first proc the daemon starts (like PID 1 on
Linux). It runs without a Landlock domain unless its config says "locks": {"landlock": true},
and it must run as uid 0 in its ns (any other "uid": the daemon refuses to start, exit 2).
By default ("daemon_access": "mount") the directory is mounted in its ns at "daemon_path"
(default /aos; the cgroup directory, when there is one, at dirname(daemon_path)/cgroup),
AOS_DAEMON=daemon_path, and it has no capabilities; with "daemon_access": "ptrace" it keeps
cap_sys_ptrace and reads /proc/1/cwd. In mount mode its own ns config may not use those two
places (exit 2). A daemon config without "init" runs the daemon with no init: nobody gets
AOS_DAEMON, and only the outside reaches the directory through /proc/<PID>/cwd.

Every proc's config may say "net": "none" (default: its own network namespace with only a
loopback that is up) or "host" (the daemon's network namespace, i.e. the outside network).

Daemon config (DAEMON_CONFIG, a JSON object; every key optional):
  {"init": "init.json",              path (relative to the daemon config's folder) or an
                                     inline object in the same format as a `start` config;
                                     leave it out for a daemon with no init
   "on_init_exit": "restart",        restart | exit
   "restart_limit": 5, "restart_window": 60,
   "on_restart_limit": "exit",       exit | stay (keep running without init)
   "exit_code": "init",              init | own (with on_init_exit exit: init's code, or 3)
   "exit_grace": 0,                  seconds
   "on_parent_death": "exit",        exit | stay
   "cgroup": "auto", "subuid": "auto"}
Flags override the file (aos-daemon daemon.json --exit-grace 10); --init beats "init".
Unknown keys, wrong types or bad values: refuse to start, exit 2.

Directory:
  status           daemon facts and the feedback of the last ctl command
  ctl              tools, one command per write:
                     start CONFIG_PATH            (a JSON file, path as seen where the daemon started)
                     kill NAME SIGNAL             (no graceful stop: send TERM, wait, send KILL yourself)
                     mount NAME [-w] SRC DST      (bind SRC into a running proc's ns; read-only unless -w)
                     umount NAME DST
                     forget NAME                  (remove a dead proc from the table)
                     forget -k NAME               (same, but first clear what it left in its cgroup:
                                                   write cgroup.kill, wait until empty, up to 5 s)
  procs/NAME/      a real folder per proc, with the files
                     name pid state exit started_at ended_at ns ns.json ns_check uid locks config
                   and, when there is a cgroup, cgroup -> its cgroup directory
                   (cpu.max, memory.max, cgroup.freeze, ...)

flags:
  --init CONFIG            init's config (here or as "init" in DAEMON_CONFIG; without a
                           DAEMON_CONFIG it is required)
  --on-init-exit MODE      restart (default) or exit
  --restart-limit N        stop restarting init after more than N deaths ... (default 5)
  --restart-window S       ... within S seconds (default 60)
  --on-restart-limit MODE  exit (default): the daemon exits 1 at the restart limit;
                           stay: it keeps running without init (other procs and ctl go on)
  --exit-code MODE         init (default): with on_init_exit exit the daemon exits with init's
                           code; own: it exits 3
  --exit-grace S           on SIGTERM/SIGINT/SIGHUP send SIGTERM to init only, wait up to S
                           seconds for it to exit (not restarted meanwhile; ctl keeps working),
                           then SIGKILL every proc (default 0: at once; no init: at once)
  --on-parent-death MODE   exit (default): the daemon dies when the launching process dies;
                           stay: it keeps running (stop it with SIGTERM to the daemon's PID)
  --cgroup auto|off        auto (default): use a delegated cgroup; re-run itself under
                           `systemd-run --user --scope -p Delegate=yes` if needed and possible
  --subuid auto|off        auto (default): map the /etc/subuid range with newuidmap/newgidmap
  -h, --help               show this help

Exit code: 0 after SIGTERM/SIGINT/SIGHUP; with on_init_exit exit, init's code (128+signal)
or 3 with --exit-code own; 1 when the restart limit is reached (on_restart_limit exit);
2 on startup errors.
)";

int usage_error(const std::string& why) {
    std::cerr << "aos-daemon: error: " << why << " (see aos-daemon --help)\n";
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
// reexec：重跑自己時的參數（daemon 設定檔與 --init 的路徑已換成絕對路徑，其他照原樣，蓋過設定檔的參數也一起帶過去）
Cgroup prepare_cgroup(const Options& o, const std::vector<std::string>& reexec) {
    Cgroup c;
    if (!o.cgroup_auto) {
        c.note = o.cgroup_off_note;
        return c;
    }
    if (!getenv("AOS_DAEMON_IN_SCOPE")) {
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
        setenv("AOS_DAEMON_IN_SCOPE", "1", 1);
        std::vector<std::string> args = {sr, "--user", "--scope", "--quiet", "--collect", "-p", "Delegate=yes",
                                         "--unit=aos-daemon-" + std::to_string(getpid()), "--", self};
        for (const auto& a : reexec) args.push_back(a);
        std::vector<char*> av;
        for (auto& a : args) av.push_back(a.data());
        av.push_back(nullptr);
        execv(av[0], av.data());
        unsetenv("AOS_DAEMON_IN_SCOPE");
        c.note = "systemd-run: " + errstr(errno);
        return c;
    }
    std::string rel = own_cgroup();
    std::string dir = "/sys/fs/cgroup" + rel;
    if (rel.find("/aos-daemon-") == std::string::npos || access((dir + "/cgroup.subtree_control").c_str(), W_OK) != 0) {
        c.note = "not in a delegated aos-daemon scope (" + rel + ")";
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

std::string cwd_dir() {
    char cwd[PATH_MAX];
    return getcwd(cwd, sizeof cwd) ? cwd : "";
}

std::string absolute(const std::string& p, const std::string& base) { return p.empty() || p[0] == '/' ? p : base + "/" + p; }

const char* const DCONF_KEYS =
    "init, on_init_exit, restart_limit, restart_window, on_restart_limit, exit_code, exit_grace, on_parent_death, cgroup, subuid";

// daemon 設定檔（json 物件）蓋到 o 上；回 "" 或錯誤（起不來，退出碼 2）。path 已是絕對路徑。
std::string load_daemon_config(const std::string& path, Options& o) {
    std::ifstream f(path);
    if (!f) return "cannot read the daemon config " + path + ": " + errstr(errno);
    std::string text((std::istreambuf_iterator<char>(f)), {});
    nlohmann::json j;
    try {
        j = nlohmann::json::parse(text);
    } catch (const std::exception& e) {
        return "the daemon config " + path + " is not JSON: " + e.what();
    }
    std::string where = "in the daemon config " + path + ": ";
    if (!j.is_object()) return where + "the top level must be an object";
    std::string dir = path.substr(0, path.rfind('/'));
    if (dir.empty()) dir = "/";
    auto choice = [&](const std::string& k, const nlohmann::json& v, const char* a, const char* b, bool& out) {
        if (!v.is_string() || (v.get<std::string>() != a && v.get<std::string>() != b))
            return where + "\"" + k + "\" must be \"" + a + "\" or \"" + b + "\", not " + v.dump();
        out = v.get<std::string>() == a;
        return std::string();
    };
    auto finite = [](double x) { return x == x && x < 1e300 && x > -1e300; };
    for (const auto& [k, v] : j.items()) {
        std::string e;
        if (k == "init") {
            if (v.is_string() && !v.get<std::string>().empty()) {
                o.init_path = absolute(v.get<std::string>(), dir);
                o.init_text.clear();
            } else if (v.is_object()) {
                o.init_text = v.dump();
                o.init_path = path + "#/init";
            } else {
                e = where + "\"init\" must be a path (a non-empty string) or an inline init config (an object), not " + v.dump() +
                    " (leave the key out for a daemon with no init)";
            }
        } else if (k == "on_init_exit") {
            e = choice(k, v, "restart", "exit", o.restart);
        } else if (k == "on_restart_limit") {
            bool exit_ = true;
            e = choice(k, v, "exit", "stay", exit_);
            o.restart_limit_stay = !exit_;
        } else if (k == "exit_code") {
            bool init_ = true;
            e = choice(k, v, "init", "own", init_);
            o.exit_code_own = !init_;
        } else if (k == "restart_limit") {
            if (!v.is_number_integer() || v.get<long long>() < 0 || v.get<long long>() > INT_MAX)
                e = where + "\"restart_limit\" must be an integer >= 0, not " + v.dump();
            else o.restart_limit = v.get<int>();
        } else if (k == "restart_window") {
            if (!v.is_number() || !(v.get<double>() > 0) || !finite(v.get<double>()))
                e = where + "\"restart_window\" must be a number of seconds > 0, not " + v.dump();
            else o.restart_window = v.get<double>();
        } else if (k == "exit_grace") {
            if (!v.is_number() || !(v.get<double>() >= 0) || !finite(v.get<double>()))
                e = where + "\"exit_grace\" must be a number of seconds >= 0, not " + v.dump();
            else o.exit_grace = v.get<double>();
        } else if (k == "on_parent_death") {
            e = choice(k, v, "exit", "stay", o.parent_death_exit);
        } else if (k == "cgroup" || k == "subuid") {
            e = choice(k, v, "auto", "off", k == "cgroup" ? o.cgroup_auto : o.subuid_auto);
            if (k == "cgroup") o.cgroup_off_note = "\"cgroup\": \"off\" in the daemon config";
        } else {
            e = where + "unknown key \"" + k + "\" (" + DCONF_KEYS + ")";
        }
        if (!e.empty()) return e;
    }
    return "";
}

}  // namespace

int main(int argc, char** argv) {
    // 先分出位置參數（daemon 設定檔）與命令列參數；順序：預設值 ← 設定檔 ← 命令列參數
    Options o;
    int conf_at = 0;                       // argv 裡 daemon 設定檔的位置；0＝沒有
    std::vector<int> init_at;              // argv 裡 --init 的值的位置（重跑自己時換成絕對路徑）
    std::vector<std::pair<std::string, std::string>> flags;
    const char* WITH_VALUE[] = {"--init", "--on-init-exit", "--restart-limit", "--restart-window", "--on-restart-limit",
                                "--exit-code", "--exit-grace", "--on-parent-death", "--cgroup", "--subuid"};
    for (int i = 1; i < argc; ++i) {
        std::string a = argv[i];
        if (a == "-h" || a == "--help") {
            std::cout << HELP;
            return 0;
        }
        if (a.empty() || a[0] != '-') {
            if (conf_at) return usage_error("only one daemon config file may be given (" + std::string(argv[conf_at]) + ", " + a + ")");
            conf_at = i;
            continue;
        }
        bool known = false;
        for (const char* w : WITH_VALUE) known = known || a == w;
        if (!known) return usage_error("unknown argument " + a);
        if (i + 1 >= argc) return usage_error("bad value: " + a + " needs a value");
        if (a == "--init") init_at.push_back(i + 1);
        flags.emplace_back(a, argv[++i]);
    }
    std::string cwd = cwd_dir();
    if (cwd.empty()) return usage_error("getcwd failed");
    if (conf_at) {
        o.config_path = absolute(argv[conf_at], cwd);
        std::string e = load_daemon_config(o.config_path, o);
        if (!e.empty()) return usage_error(e);
    }
    for (const auto& [a, v] : flags) {
        try {
            if (a == "--init") {
                if (v.empty()) return usage_error("--init needs a path");
                o.init_path = absolute(v, cwd);
                o.init_text.clear();
            } else if (a == "--on-init-exit") {
                if (v != "restart" && v != "exit") return usage_error("--on-init-exit is restart or exit");
                o.restart = v == "restart";
            } else if (a == "--on-restart-limit") {
                if (v != "exit" && v != "stay") return usage_error("--on-restart-limit is exit or stay");
                o.restart_limit_stay = v == "stay";
            } else if (a == "--exit-code") {
                if (v != "init" && v != "own") return usage_error("--exit-code is init or own");
                o.exit_code_own = v == "own";
            } else if (a == "--restart-limit") {
                o.restart_limit = std::stoi(v);
                if (o.restart_limit < 0) return usage_error("--restart-limit must be >= 0");
            } else if (a == "--restart-window") {
                o.restart_window = std::stod(v);
                if (!(o.restart_window > 0) || !(o.restart_window < 1e300)) return usage_error("--restart-window must be > 0");
            } else if (a == "--exit-grace") {
                o.exit_grace = std::stod(v);
                if (!(o.exit_grace >= 0) || !(o.exit_grace < 1e300)) return usage_error("--exit-grace must be a number of seconds >= 0");
            } else if (a == "--on-parent-death") {
                if (v != "exit" && v != "stay") return usage_error("--on-parent-death is exit or stay");
                o.parent_death_exit = v == "exit";
            } else if (a == "--cgroup" || a == "--subuid") {
                if (v != "auto" && v != "off") return usage_error(a + " is auto or off");
                (a == "--cgroup" ? o.cgroup_auto : o.subuid_auto) = v == "auto";
                if (a == "--cgroup") o.cgroup_off_note = "--cgroup off";
            }
        } catch (const std::exception&) {
            return usage_error("bad value for " + a + ": " + v);
        }
    }
    // 只用參數起（沒有 daemon 設定檔）又沒給 --init：照舊拒【擬】；要沒有 init 的 daemon，寫一份沒有 "init" 的 daemon 設定檔
    if (!conf_at && !has_init(o))
        return usage_error("--init CONFIG is required when no daemon config is given "
                           "(for a daemon with no init, give a daemon config without \"init\", e.g. one holding {})");
    if (has_init(o) && o.init_text.empty() && access(o.init_path.c_str(), R_OK) != 0)
        return usage_error("cannot read " + o.init_path + ": " + errstr(errno));
    std::vector<std::string> reexec;
    for (int i = 1; i < argc; ++i) {
        bool kv = std::find(init_at.begin(), init_at.end(), i) != init_at.end();
        reexec.push_back(i == conf_at ? o.config_path : kv ? absolute(argv[i], cwd) : std::string(argv[i]));
    }

    Cgroup cg = prepare_cgroup(o, reexec);   // 可能 exec systemd-run 再回到這裡（在 scope 裡）
    if (!cg.dir.empty()) setenv("AOS_DAEMON_CGROUP", cg.dir.c_str(), 1);
    else setenv("AOS_DAEMON_CGROUP_NOTE", cg.note.c_str(), 1);

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
