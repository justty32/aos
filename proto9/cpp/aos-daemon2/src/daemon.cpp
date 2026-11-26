// daemon.cpp：daemon 本體——PID namespace 的 1 號；擺出資訊與工具的目錄、住進只有它的小世界、起主 kernel、收屍、照工具檔的指令做事。
#include "common.hpp"

#include "aos/procfs.hpp"

#include <cerrno>
#include <condition_variable>
#include <csignal>
#include <cstring>
#include <deque>
#include <fcntl.h>
#include <functional>
#include <grp.h>
#include <linux/landlock.h>
#include <map>
#include <memory>
#include <mutex>
#include <poll.h>
#include <sched.h>
#include <sys/eventfd.h>
#include <sys/mount.h>
#include <sys/prctl.h>
#include <sys/signalfd.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include <unistd.h>

namespace d2 {

namespace pf = aos::procfs;

namespace {

struct Proc {
    ProcConfig cfg;
    bool main_kernel = false;
    Spawned sp;
    bool alive = true;
    int code = -1, sig = 0;
    std::string started_at, ended_at = "-";
};

// 表：名字 → 那隻。資訊目錄的 procs/<名>/ 是真的夾，放上表時建、從表上拿掉時連同底下整個拿掉（aos-procfs 的 remove_tree）。
struct State {
    std::mutex mu;
    std::map<std::string, std::shared_ptr<Proc>> procs;
    int kernel_restarts = 0;
    std::deque<double> deaths;   // 主 kernel 死的時間（monotonic）
    std::string kernel_last_exit = "-";
};

State S;
Options O;
ProcConfig KCFG;
pf::Fs* FS = nullptr;
pf::Ctl* CTL = nullptr;
// 放上表／拿掉時「表」與「目錄」一起改：主執行緒（start、主 kernel 重起）與做事的線（forget）不會交錯。
// 回答的線（Producer）不拿它，所以拿著它跟核心講話（remove_tree 的通知）不會卡住回答的線。
std::mutex DIR_MU;
long seq = 0;            // cgroup 夾名的流水號，只在主執行緒動
std::string started_at;
int EFD = -1;
bool gone = false;       // FUSE 連線斷了

// 做事的線把要 fork／收屍的事交給主執行緒（只有主執行緒 fork 與 waitpid）
struct Request {
    std::function<std::string()> fn;
    std::mutex m;
    std::condition_variable cv;
    bool done = false;
    std::string result;
};
std::mutex RQ_MU;
std::deque<std::shared_ptr<Request>> RQ;

void wake() {
    uint64_t one = 1;
    if (write(EFD, &one, sizeof one) < 0) {}
}

std::string on_main(std::function<std::string()> fn) {
    auto r = std::make_shared<Request>();
    r->fn = std::move(fn);
    {
        std::lock_guard<std::mutex> g(RQ_MU);
        RQ.push_back(r);
    }
    wake();
    std::unique_lock<std::mutex> lk(r->m);
    if (!r->cv.wait_for(lk, std::chrono::seconds(60), [&] { return r->done; }))
        return "Internal the main thread did not answer in 60 s";
    return r->result;
}

std::string exit_text(const Proc& p) {
    if (p.alive) return "-";
    if (p.sig) return "signal " + std::to_string(p.sig) + " " + signal_name(p.sig);
    return "code " + std::to_string(p.code);
}

std::string join(const std::vector<std::string>& v) {
    std::string s;
    for (const auto& x : v) s += x + "\n";
    return s;
}

// procs/<名>/ 的資訊檔（內容在回答的線上產生：只讀記憶體）。每個檔抓著那隻的 shared_ptr，夾拿掉時跟著放
void make_proc_nodes(const std::shared_ptr<Proc>& proc) {
    std::string d = "procs/" + proc->cfg.name;
    FS->add_dir(d);
    auto add = [&](const char* file, std::function<std::string(const Proc&)> f) {
        FS->add_text(d + "/" + file, [proc, f] {
            std::lock_guard<std::mutex> g(S.mu);
            return f(*proc);
        });
    };
    add("name", [](const Proc& p) { return p.cfg.name + "\n"; });
    add("pid", [](const Proc& p) {
        return "ns: " + std::to_string(p.sp.pid) + "\nhost: " + std::to_string(p.sp.host_pid) + "\n";
    });
    add("state", [](const Proc& p) { return std::string(p.alive ? "alive\n" : "dead\n"); });
    add("exit", [](const Proc& p) { return exit_text(p) + "\n"; });
    add("started_at", [](const Proc& p) { return p.started_at + "\n"; });
    add("ended_at", [](const Proc& p) { return p.ended_at + "\n"; });
    add("ns", [](const Proc& p) { return p.sp.ns; });
    add("ns_check", [](const Proc& p) { return p.sp.ns_check + "\n"; });
    add("uid", [](const Proc& p) {
        long host = p.cfg.uid == 0 ? W.host_uid : W.subuid_start + p.cfg.uid - 1;
        return "ns: " + std::to_string(p.cfg.uid) + "\nhost: " + std::to_string(host) + "\n";
    });
    add("locks", [](const Proc& p) { return join(p.sp.locks); });
    add("config", [](const Proc& p) { return p.cfg.path + "\n"; });
    // 相對連結：小世界裡是 /aos/procs/<名>/ → /cgroup/…；主 kernel 的天空也把 cgroup 夾放在 /cgroup，所以兩邊都通
    if (!proc->sp.cgroup.empty()) FS->add_symlink(d + "/cgroup", "../../../cgroup/" + proc->sp.cgroup);
}

// 主執行緒：放進表、擺出 procs/<名>/
void put_proc(const std::shared_ptr<Proc>& p) {
    std::lock_guard<std::mutex> dg(DIR_MU);
    {
        std::lock_guard<std::mutex> g(S.mu);
        S.procs[p->cfg.name] = p;
    }
    try {
        make_proc_nodes(p);
    } catch (const std::exception& e) {
        // 表跟目錄一起改，照理不會撞名；真的撞了就記下來，表上照樣有它（kill、forget 照常）
        log("procs/" + p->cfg.name + "/ not made: " + e.what());
    }
}

// 從表上拿掉（任何執行緒，回答的線除外），連同 procs/<名>/；only 非空時只在表上的還是它才拿。回它的 cgroup 夾名
std::string drop_proc(const std::string& name, const Proc* only = nullptr) {
    std::lock_guard<std::mutex> dg(DIR_MU);
    std::string cg;
    {
        std::lock_guard<std::mutex> g(S.mu);
        auto it = S.procs.find(name);
        if (it == S.procs.end() || (only && it->second.get() != only)) return "";
        cg = it->second->sp.cgroup;
        S.procs.erase(it);
    }
    if (!FS->remove_tree("procs/" + name)) log("procs/" + name + "/ was not there to remove");
    return cg;
}

std::shared_ptr<Proc> find(const std::string& name) {
    auto it = S.procs.find(name);
    return it == S.procs.end() ? nullptr : it->second;
}

// 主執行緒
std::string start_proc(const ProcConfig& cfg, bool main_kernel) {
    {
        std::lock_guard<std::mutex> g(S.mu);
        if (find(cfg.name)) return "ProcExists " + cfg.name + " (forget it first if it is dead)";
    }
    if (!main_kernel && !cfg.daemon_access.empty())
        return "ConfigBad daemon_access is only read from the main kernel's config (--kernel)";
    auto p = std::make_shared<Proc>();
    p->cfg = cfg;
    p->main_kernel = main_kernel;
    std::string err = spawn(cfg, main_kernel, ++seq, p->sp);
    if (!err.empty()) {
        log("start " + cfg.name + " failed: " + err);
        return err;
    }
    p->started_at = iso_now();
    put_proc(p);
    log("started " + cfg.name + " (pid " + std::to_string(p->sp.pid) + ", host pid " + std::to_string(p->sp.host_pid) +
        (main_kernel ? ", main kernel" : "") + ")");
    if (p->sp.ns_check != "ok") log("ns of " + cfg.name + " does not match its config: " + p->sp.ns_check);
    return "";
}

void rm_cgroup(const std::string& cg) {
    if (cg.empty() || W.cgfd < 0) return;
    for (int k = 0; k < 100; ++k) {
        if (unlinkat(W.cgfd, cg.c_str(), AT_REMOVEDIR) == 0 || errno == ENOENT) return;
        if (errno != EBUSY) break;
        usleep(10000);
    }
    log("cgroup " + cg + " not removed: " + errstr(errno));
}

[[noreturn]] void shutdown(int code, const std::string& why) {
    log("exiting (" + why + "), code " + std::to_string(code));
    // 1 號一走，Linux 也會收掉整片；這裡先收、等完，好把 cgroup 夾清掉
    kill(-1, SIGKILL);
    double end = mono_now() + 5;
    while (mono_now() < end) {
        pid_t r = waitpid(-1, nullptr, WNOHANG);
        if (r < 0 && errno == ECHILD) break;
        if (r <= 0) usleep(5000);
    }
    std::vector<std::string> cgs;
    {
        std::lock_guard<std::mutex> g(S.mu);
        for (const auto& [n, p] : S.procs)
            if (!p->sp.cgroup.empty()) cgs.push_back(p->sp.cgroup);
    }
    for (const auto& c : cgs) rm_cgroup(c);
    _exit(code);
}

// 主 kernel 死了（或起不來）：照起動參數做，判斷不在這裡以外
void kernel_died(const std::string& how, int as_code) {
    {
        std::lock_guard<std::mutex> g(S.mu);
        S.kernel_last_exit = how;
    }
    if (!O.restart) shutdown(as_code, "main kernel " + how + ", --on-kernel-exit exit");
    double now = mono_now();
    size_t n;
    {
        std::lock_guard<std::mutex> g(S.mu);
        S.deaths.push_back(now);
        while (!S.deaths.empty() && S.deaths.front() < now - O.restart_window) S.deaths.pop_front();
        n = S.deaths.size();
    }
    if (static_cast<int>(n) > O.restart_limit)
        shutdown(1, "main kernel died " + std::to_string(n) + " times within " + std::to_string(static_cast<int>(O.restart_window)) +
                        " s, more than --restart-limit " + std::to_string(O.restart_limit));
    rm_cgroup(drop_proc(KCFG.name));
    {
        std::lock_guard<std::mutex> g(S.mu);
        ++S.kernel_restarts;
    }
    log("restarting main kernel " + KCFG.name + " (" + how + ")");
    std::string err = start_proc(KCFG, true);
    if (!err.empty()) kernel_died("failed to start: " + err, 1);
}

void reap_all() {
    int st;
    pid_t pid;
    while ((pid = waitpid(-1, &st, WNOHANG)) > 0) {
        std::shared_ptr<Proc> hit;
        {
            std::lock_guard<std::mutex> g(S.mu);
            for (const auto& [n, p] : S.procs)
                if (p->alive && p->sp.pid == pid) hit = p;
            if (hit) {
                hit->alive = false;
                hit->ended_at = iso_now();
                if (WIFSIGNALED(st)) hit->sig = WTERMSIG(st);
                else hit->code = WEXITSTATUS(st);
            }
        }
        if (!hit) continue;   // 被收養的孫子、幫手
        std::string how = exit_text(*hit);
        log("proc " + hit->cfg.name + " exited: " + how);
        if (hit->main_kernel) kernel_died(how, hit->sig ? 128 + hit->sig : hit->code);
    }
}

// ---------- 工具檔 ctl ----------

std::string check_name(const pf::Command& c, size_t argc, const char* usage, int need_alive) {
    if (c.words.size() != argc) return std::string("ArgumentsBad usage: ") + usage;
    std::lock_guard<std::mutex> g(S.mu);
    auto p = find(c.words[1]);
    if (!p) return "ProcUnknown " + c.words[1];
    if (need_alive == 1 && !p->alive) return "ProcDead " + c.words[1] + " is not running";
    if (need_alive == 0 && p->alive) return "ProcAlive " + c.words[1] + " is still running (kill it first)";
    return "";
}

// 主 kernel（mount 模式）天空裡的 /aos、/cgroup 是 daemon 放的，ctl 的 mount／umount 不准動（蓋住或卸掉就斷了）
std::string reserved_dst(const std::string& name, const std::string& dst) {
    std::lock_guard<std::mutex> g(S.mu);
    auto p = find(name);
    if (!p || !p->main_kernel || !kernel_mounts(p->cfg)) return "";
    for (const char* top : {KERNEL_AOS, KERNEL_CGROUP}) {
        std::string t = top;
        if (t == KERNEL_CGROUP && W.cgfd < 0) continue;
        if (dst == t || dst.rfind(t + "/", 0) == 0)
            return "PathReserved " + t + " in the main kernel's ns is where the daemon put its " +
                   (t == KERNEL_AOS ? "directory" : "cgroup directory");
    }
    return "";
}

bool abs_clean(const std::string& p) {
    if (p.empty() || p[0] != '/') return false;
    try {
        NsEntry e = parse_ns_line("tmpfs " + p);
        return e.dst == p;
    } catch (...) {
        return false;
    }
}

void setup_ctl(pf::Ctl& ctl) {
    // 做完才回：start 等 exec 成功（或失敗）、mount／umount 等做完、kill 等送出、forget 等拿掉；做的時候失敗＝寫入失敗 EIO
    ctl.reply_when_done();
    ctl.on("start",
        [](const pf::Command& c) {
            std::string err;
            std::string text = read_host_file(c.words[1], err);
            if (!err.empty()) return pf::Result::failed(err);
            ProcConfig cfg;
            try {
                cfg = parse_config(text, c.words[1]);
            } catch (const std::exception& e) {
                return pf::Result::failed(e.what());
            }
            err = on_main([cfg] { return start_proc(cfg, false); });
            return err.empty() ? pf::Result::done() : pf::Result::failed(err);
        },
        [](const pf::Command& c) -> std::string {
            if (c.words.size() != 2) return "ArgumentsBad usage: start CONFIG_PATH";
            if (c.words[1][0] != '/') return "PathNotAbsolute " + c.words[1] + " (a path as seen where the daemon was started)";
            return "";
        });
    ctl.on("kill",
        [](const pf::Command& c) {
            int sig = signal_number(c.words[2]);
            std::lock_guard<std::mutex> g(S.mu);
            auto p = find(c.words[1]);
            if (!p || !p->alive) return pf::Result::failed("ProcDead " + c.words[1] + " is not running");
            // 還沒收屍前 PID 不會被別人拿走（收屍跟這裡拿同一把鎖）
            if (kill(p->sp.pid, sig) != 0) return pf::Result::failed("KillFailed " + errstr(errno));
            return pf::Result::done();
        },
        [](const pf::Command& c) -> std::string {
            if (c.words.size() == 3 && !signal_number(c.words[2])) return "SignalUnknown " + c.words[2];
            return check_name(c, 3, "kill NAME SIGNAL", 1);
        });
    ctl.on("forget",
        [](const pf::Command& c) {
            std::string cg;
            std::shared_ptr<Proc> p;
            {
                std::lock_guard<std::mutex> g(S.mu);
                p = find(c.words[1]);
                if (!p) return pf::Result::failed("ProcUnknown " + c.words[1]);
                if (p->alive) return pf::Result::failed("ProcAlive " + c.words[1]);
                cg = p->sp.cgroup;
            }
            // cgroup 裡還有它留下的行程就不拿掉（要收由 kernel 寫 cgroup.kill）
            if (!cg.empty() && unlinkat(W.cgfd, cg.c_str(), AT_REMOVEDIR) != 0 && errno != ENOENT)
                return pf::Result::failed("CgroupNotEmpty " + c.words[1] + ": " + errstr(errno) +
                                          " (processes it left are still in its cgroup; write 1 to its cgroup/cgroup.kill)");
            drop_proc(c.words[1], p.get());   // 這段時間裡主 kernel 被重起成同名的新一隻，就不拿那隻
            log("forgot " + c.words[1]);
            return pf::Result::done();
        },
        [](const pf::Command& c) { return check_name(c, 2, "forget NAME", 0); });
    ctl.on("mount",
        [](const pf::Command& c) {
            bool rw = c.words[2] == "-w";
            std::string name = c.words[1], src = c.words[rw ? 3 : 2], dst = c.words[rw ? 4 : 3];
            std::string err = on_main([=] {
                std::shared_ptr<Proc> p;
                {
                    std::lock_guard<std::mutex> g(S.mu);
                    p = find(name);
                    if (!p || !p->alive) return "ProcDead " + name;
                }
                std::string e = live_mount(p->sp.pid, src, dst, rw);
                if (!e.empty()) return "MountFailed " + e;
                std::vector<Mount> m = p->sp.mounts;
                m.push_back({"bind", src, dst, rw});
                std::string check, ns = ns_table(p->sp.pid, m, check);
                std::lock_guard<std::mutex> g(S.mu);
                p->sp.mounts = m;
                p->sp.ns = ns;
                p->sp.ns_check = check;
                return std::string();
            });
            if (err.empty()) log("mounted " + src + " at " + dst + " in " + name);
            return err.empty() ? pf::Result::done() : pf::Result::failed(err);
        },
        [](const pf::Command& c) -> std::string {
            bool rw = c.words.size() > 2 && c.words[2] == "-w";
            if (c.words.size() != (rw ? 5u : 4u)) return "ArgumentsBad usage: mount NAME [-w] SRC DST";
            const std::string& src = c.words[rw ? 3 : 2];
            const std::string& dst = c.words[rw ? 4 : 3];
            if (!abs_clean(src) || !abs_clean(dst) || dst == "/")
                return "PathBad SRC and DST must be clean absolute paths, DST not /";
            std::string e = check_name(pf::Command{c.line, {c.words[0], c.words[1]}}, 2, "mount NAME [-w] SRC DST", 1);
            return e.empty() ? reserved_dst(c.words[1], dst) : e;
        });
    ctl.on("umount",
        [](const pf::Command& c) {
            std::string name = c.words[1], dst = c.words[2];
            std::string err = on_main([=] {
                std::shared_ptr<Proc> p;
                {
                    std::lock_guard<std::mutex> g(S.mu);
                    p = find(name);
                    if (!p || !p->alive) return "ProcDead " + name;
                }
                std::string e = live_umount(p->sp.pid, dst);
                if (!e.empty()) return "UmountFailed " + e;
                std::vector<Mount> m;
                for (const auto& x : p->sp.mounts)
                    if (!(x.dst == dst || x.dst.rfind(dst + "/", 0) == 0)) m.push_back(x);
                std::string check, ns = ns_table(p->sp.pid, m, check);
                std::lock_guard<std::mutex> g(S.mu);
                p->sp.mounts = m;
                p->sp.ns = ns;
                p->sp.ns_check = check;
                return std::string();
            });
            if (err.empty()) log("unmounted " + dst + " in " + name);
            return err.empty() ? pf::Result::done() : pf::Result::failed(err);
        },
        [](const pf::Command& c) -> std::string {
            if (c.words.size() == 3 && (!abs_clean(c.words[2]) || c.words[2] == "/"))
                return "PathBad DST must be a clean absolute path, not /";
            std::string e = check_name(c, 3, "umount NAME DST", 1);
            return e.empty() ? reserved_dst(c.words[1], c.words[2]) : e;
        });
}

std::string status_text() {
    std::string s;
    std::lock_guard<std::mutex> g(S.mu);
    s += pf::kv_line("pid_ns", "1");
    s += pf::kv_line("pid_host", std::to_string(W.host_pid));
    s += pf::kv_line("started_at", started_at);
    s += pf::kv_line("main_kernel", KCFG.name);
    s += pf::kv_line("on_kernel_exit", O.restart ? "restart" : "exit");
    s += pf::kv_line("restart_limit", std::to_string(O.restart_limit) + " deaths within " +
                                          std::to_string(static_cast<int>(O.restart_window)) + " s");
    s += pf::kv_line("kernel_restarts", std::to_string(S.kernel_restarts));
    s += pf::kv_line("kernel_deaths_in_window", std::to_string(S.deaths.size()));
    s += pf::kv_line("kernel_last_exit", S.kernel_last_exit);
    s += pf::kv_line("landlock_abi", std::to_string(W.landlock_abi));
    s += pf::kv_line("cgroup", W.cgfd >= 0 ? W.cg_host : "off (" + W.cg_note + ")");
    s += pf::kv_line("subuid", W.subuid_count ? std::to_string(W.subuid_start) + " " + std::to_string(W.subuid_count) : "none");
    s += pf::kv_line("main_kernel_access", kernel_mounts(KCFG) ? std::string("mount ") + KERNEL_AOS : "ptrace /proc/1/cwd");
    s += pf::kv_line("procs", std::to_string(S.procs.size()));
    s += CTL->feedback();
    return s;
}

[[noreturn]] void fatal(const std::string& m) {
    log("error: " + m);
    _exit(2);
}

void must(int r, const std::string& what) {
    if (r != 0) fatal(what + ": " + errstr(errno));
}

}  // namespace

[[noreturn]] void daemon_main(const Options& o, int sync_fd) {
    O = o;
    long info[6] = {0};   // 外面的 PID、setgroups_ok、subuid 起點、數量、外面的 uid、gid
    if (read(sync_fd, info, sizeof info) != static_cast<ssize_t>(sizeof info)) _exit(2);
    close(sync_fd);
    prctl(PR_SET_PDEATHSIG, SIGKILL);   // 起動那一層死了就跟著走
    W.host_pid = info[0];
    W.setgroups_ok = info[1] != 0;
    W.subuid_start = info[2];
    W.subuid_count = info[3];
    W.host_uid = info[4];
    W.host_gid = info[5];
    if (W.setgroups_ok) must(setgroups(0, nullptr), "setgroups");
    started_at = iso_now();

    // 原本那一層（自己的 mount namespace 裡那份）：握住要的 fd
    must(mount(nullptr, "/", nullptr, MS_REC | MS_PRIVATE, nullptr), "make mounts private");
    W.hostprocfd = open("/proc", O_PATH | O_DIRECTORY | O_CLOEXEC);
    W.rootfd = open("/", O_PATH | O_DIRECTORY | O_CLOEXEC);
    const char* cg = getenv("AOS_DAEMON2_CGROUP");
    W.cg_note = getenv("AOS_DAEMON2_CGROUP_NOTE") ? getenv("AOS_DAEMON2_CGROUP_NOTE") : "";
    if (cg && *cg) {
        W.cg_host = cg;
        W.cgfd = open(cg, O_PATH | O_DIRECTORY | O_CLOEXEC);
        if (W.cgfd < 0) fatal("open cgroup " + W.cg_host + ": " + errstr(errno));
    }
    unsetenv("AOS_DAEMON2_CGROUP");
    unsetenv("AOS_DAEMON2_CGROUP_NOTE");
    unsetenv("AOS_DAEMON2_IN_SCOPE");
    long abi = syscall(SYS_landlock_create_ruleset, nullptr, 0, LANDLOCK_CREATE_RULESET_VERSION);
    W.landlock_abi = abi > 0 ? static_cast<int>(abi) : 0;
    {
        std::string err, text = read_host_file(O.kernel_path, err);
        if (!err.empty()) fatal(err);
        try {
            KCFG = parse_config(text, O.kernel_path);
        } catch (const std::exception& e) {
            fatal(std::string(e.what()) + " in " + O.kernel_path);
        }
        if (KCFG.uid != 0)
            fatal("ConfigBad the main kernel must run as uid 0 in its ns (its \"uid\" is " + std::to_string(KCFG.uid) +
                  "): ctl is 0200 and only the daemon's uid may use the mounted directory, in " + O.kernel_path);
        // cgroup 夾這時已經握住了（有沒有 cgroup 定了）
        std::string bad = kernel_ns_conflict(KCFG, W.cgfd >= 0);
        if (!bad.empty()) fatal(bad + " in " + O.kernel_path);
    }
    must(mount("proc", "/proc", "proc", MS_NOSUID | MS_NODEV | MS_NOEXEC, nullptr), "mount proc");
    W.procfd = open("/proc", O_PATH | O_DIRECTORY | O_CLOEXEC);
    W.orignsfd = open("/proc/self/ns/mnt", O_RDONLY | O_CLOEXEC);
    if (W.hostprocfd < 0 || W.rootfd < 0 || W.procfd < 0 || W.orignsfd < 0) fatal("open the fds kept for later");

    // 小世界：另一個 mount namespace，根是一塊小 tmpfs，裡面只有 aos/（資訊與工具）與 cgroup/（開關）
    must(unshare(CLONE_NEWNS), "unshare mount namespace");
    must(mount("tmpfs", "/tmp", "tmpfs", MS_NOSUID | MS_NODEV | MS_NOEXEC, "mode=0755,size=64k"), "mount small world");
    must(mkdir("/tmp/aos", 0755), "mkdir aos");
    if (W.cgfd >= 0) {
        must(mkdir("/tmp/cgroup", 0755), "mkdir cgroup");
        must(mount(W.cg_host.c_str(), "/tmp/cgroup", nullptr, MS_BIND, nullptr), "bind cgroup");
    }

    sigset_t sigs;
    sigemptyset(&sigs);
    for (int s : {SIGCHLD, SIGTERM, SIGINT, SIGHUP}) sigaddset(&sigs, s);
    pthread_sigmask(SIG_BLOCK, &sigs, nullptr);
    signal(SIGPIPE, SIG_IGN);
    int sfd = signalfd(-1, &sigs, SFD_CLOEXEC | SFD_NONBLOCK);
    EFD = eventfd(0, EFD_CLOEXEC | EFD_NONBLOCK);

    pf::Options opt;
    opt.fsname = "aosdaemon2";
    opt.on_gone = [] {
        gone = true;
        wake();
    };
    static pf::Fs fs(opt);   // 不解構：結束時直接 _exit，掛載跟著 namespace 消失
    FS = &fs;
    try {
        CTL = &fs.add_ctl("ctl", "aos_ctl_");
        setup_ctl(*CTL);
        fs.add_text("status", status_text);
        fs.add_dir("procs");
        fs.mount("/tmp/aos");
    } catch (const std::exception& e) {
        fatal(std::string("mount info directory: ") + e.what());
    }
    must(mount(nullptr, "/tmp", nullptr, MS_REMOUNT | MS_BIND | MS_RDONLY | MS_NOSUID | MS_NODEV | MS_NOEXEC, nullptr),
         "make small world read-only");
    must(chdir("/tmp"), "chdir small world");
    must(static_cast<int>(syscall(SYS_pivot_root, ".", ".")), "pivot_root");
    must(umount2(".", MNT_DETACH), "detach old root");
    must(chdir("/aos"), "chdir aos");

    std::string line = "export AOS_DAEMON=/proc/" + std::to_string(W.host_pid) + "/cwd\n";
    if (write(1, line.data(), line.size()) < 0) {}
    log("ready: pid " + std::to_string(W.host_pid) + ", landlock ABI " + std::to_string(W.landlock_abi) +
        ", cgroup " + (W.cgfd >= 0 ? W.cg_host : "off (" + W.cg_note + ")"));

    std::string err = start_proc(KCFG, true);
    if (!err.empty()) kernel_died("failed to start: " + err, 1);

    for (;;) {
        pollfd p[2] = {{sfd, POLLIN, 0}, {EFD, POLLIN, 0}};
        if (poll(p, 2, -1) < 0 && errno != EINTR) fatal("poll: " + errstr(errno));
        signalfd_siginfo si;
        while (read(sfd, &si, sizeof si) == static_cast<ssize_t>(sizeof si)) {
            if (si.ssi_signo == SIGCHLD) continue;
            shutdown(0, std::string("got ") + signal_name(static_cast<int>(si.ssi_signo)));
        }
        reap_all();
        uint64_t n;
        if (read(EFD, &n, sizeof n) < 0) {}
        if (gone) shutdown(1, "the info directory was disconnected");
        for (;;) {
            std::shared_ptr<Request> r;
            {
                std::lock_guard<std::mutex> g(RQ_MU);
                if (RQ.empty()) break;
                r = RQ.front();
                RQ.pop_front();
            }
            std::string res = r->fn();
            std::lock_guard<std::mutex> g(r->m);
            r->result = res;
            r->done = true;
            r->cv.notify_all();
        }
        reap_all();
    }
}

}  // namespace d2
