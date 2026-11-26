// daemon.cpp：daemon 本體——PID namespace 的 1 號；擺出資訊與工具的目錄、住進只有它的小世界、起 init（有設定的話）、收屍、照工具檔的指令做事。
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
    bool init = false;
    Spawned sp;
    bool alive = true;
    int code = -1, sig = 0;
    std::string started_at, ended_at = "-";
};

// 表：名字 → 那隻。資訊目錄的 procs/<名>/ 是真的夾，放上表時建、從表上拿掉時連同底下整個拿掉（aos-procfs 的 remove_tree）。
struct State {
    std::mutex mu;
    std::map<std::string, std::shared_ptr<Proc>> procs;
    int init_restarts = 0;
    std::deque<double> deaths;   // init 死的時間（monotonic）
    std::string init_last_exit = "-";
    std::string init_gone;       // 非空＝到了重起上限、on_restart_limit stay：init 不再起（原因）
};

State S;
Options O;
ProcConfig ICFG;         // init 的設定；HAS_INIT false 時沒用
bool HAS_INIT = false;
pf::Fs* FS = nullptr;
pf::Ctl* CTL = nullptr;
// 放上表／拿掉時「表」與「目錄」一起改：主執行緒（start、init 重起）與做事的線（forget）不會交錯。
// 回答的線（Producer）不拿它，所以拿著它跟核心講話（remove_tree 的通知）不會卡住回答的線。
std::mutex DIR_MU;
long seq = 0;            // cgroup 夾名的流水號，只在主執行緒動
std::string started_at;
int EFD = -1;
bool gone = false;       // FUSE 連線斷了
// 收到結束訊號後、等 init 自己結束的那段（exit_grace）：只在主執行緒動
bool stopping = false;
double stop_deadline = 0;   // monotonic
std::string stop_why;

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
    add("ns.json", [](const Proc& p) { return p.sp.ns_json; });
    add("ns_check", [](const Proc& p) { return p.sp.ns_check + "\n"; });
    add("uid", [](const Proc& p) {
        long host = p.cfg.uid == 0 ? W.host_uid : W.subuid_start + p.cfg.uid - 1;
        return "ns: " + std::to_string(p.cfg.uid) + "\nhost: " + std::to_string(host) + "\n";
    });
    add("locks", [](const Proc& p) { return join(p.sp.locks); });
    add("config", [](const Proc& p) { return p.cfg.path + "\n"; });
    // 相對連結：小世界裡是 /aos/procs/<名>/ → /cgroup/…；init 的天空把 cgroup 夾放在 daemon_path 旁邊的 cgroup，所以兩邊都通
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
std::string start_proc(const ProcConfig& cfg, bool init) {
    {
        std::lock_guard<std::mutex> g(S.mu);
        if (find(cfg.name)) return "ProcExists " + cfg.name + " (forget it first if it is dead)";
    }
    if (!init && !cfg.daemon_access.empty())
        return "ConfigBad daemon_access is only read from init's config (\"init\" in the daemon config, or --init)";
    if (!init && !cfg.daemon_path.empty())
        return "ConfigBad daemon_path is only read from init's config (\"init\" in the daemon config, or --init)";
    auto p = std::make_shared<Proc>();
    p->cfg = cfg;
    p->init = init;
    std::string err = spawn(cfg, init, ++seq, p->sp);
    if (!err.empty()) {
        log("start " + cfg.name + " failed: " + err);
        return err;
    }
    p->started_at = iso_now();
    put_proc(p);
    log("started " + cfg.name + " (pid " + std::to_string(p->sp.pid) + ", host pid " + std::to_string(p->sp.host_pid) +
        (init ? ", init" : "") + ")");
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

// init 死了（或起不來）：照起動參數做，判斷不在這裡以外
void init_died(const std::string& how, int as_code) {
    {
        std::lock_guard<std::mutex> g(S.mu);
        S.init_last_exit = how;
    }
    // 結束訊號後的寬限裡 init 結束了：不重起，不再等，收掉其餘的
    if (stopping) shutdown(0, stop_why + "; init " + how + " within the exit grace");
    if (!O.restart)
        shutdown(O.exit_code_own ? EXIT_INIT_EXITED : as_code,
                 "init " + how + ", on_init_exit exit" + (O.exit_code_own ? ", exit_code own" : ", exit_code init"));
    double now = mono_now();
    size_t n;
    {
        std::lock_guard<std::mutex> g(S.mu);
        S.deaths.push_back(now);
        while (!S.deaths.empty() && S.deaths.front() < now - O.restart_window) S.deaths.pop_front();
        n = S.deaths.size();
    }
    if (static_cast<int>(n) > O.restart_limit) {
        std::string why = "init died " + std::to_string(n) + " times within " + std::to_string(static_cast<int>(O.restart_window)) +
                          " s, more than --restart-limit " + std::to_string(O.restart_limit);
        if (!O.restart_limit_stay) shutdown(1, why);
        // on_restart_limit stay：不再起 init，daemon 與其他 proc 照跑；死掉的 init 留在表上（看得到 exit，要拿掉就 forget）
        {
            std::lock_guard<std::mutex> g(S.mu);
            S.init_gone = why;
        }
        log(why + "; on_restart_limit stay: not restarting it, the daemon keeps running without init");
        return;
    }
    rm_cgroup(drop_proc(ICFG.name));
    {
        std::lock_guard<std::mutex> g(S.mu);
        ++S.init_restarts;
    }
    log("restarting init " + ICFG.name + " (" + how + ")");
    std::string err = start_proc(ICFG, true);
    if (!err.empty()) init_died("failed to start: " + err, 1);
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
        if (hit->init) init_died(how, hit->sig ? 128 + hit->sig : hit->code);
    }
}

// 主執行緒：收到 SIGTERM／SIGINT／SIGHUP。先只對 init 送 SIGTERM，最多等 exit_grace 秒（主循環照跑，ctl 照用），
// init 先結束就不再等（init_died），時間到就 shutdown（全部 SIGKILL）。寬限裡再收到的結束訊號不管（照樣等到時間到）。
// 沒有 init（設定沒給、或到了重起上限而 stay）：沒人可等，直接全部 SIGKILL。
void begin_stop(int sig) {
    std::string why = std::string("got ") + signal_name(sig);
    if (stopping) {
        log(why + " while waiting for init to exit; still waiting");
        return;
    }
    pid_t kp = 0;
    if (HAS_INIT) {
        std::lock_guard<std::mutex> g(S.mu);
        auto p = find(ICFG.name);
        if (p && p->init && p->alive) kp = p->sp.pid;
    }
    if (!kp) shutdown(0, why + (HAS_INIT ? ", init is not running" : ", no init"));
    kill(kp, SIGTERM);
    if (!(O.exit_grace > 0)) shutdown(0, why);
    stopping = true;
    stop_why = why;
    stop_deadline = mono_now() + O.exit_grace;
    log(why + ": sent SIGTERM to init " + ICFG.name + ", waiting up to " + seconds_text(O.exit_grace) +
        " s (exit_grace) before killing every proc");
}

// 做事的線：forget -k。那隻的 cgroup 夾裡還有行程就寫 cgroup.kill，等到空（最多 FORGET_KILL_WAIT 秒，monotonic）
const double FORGET_KILL_WAIT = 5;
std::string clear_cgroup(const std::string& name, const std::string& cg) {
    auto populated = [&] {
        std::string ev = read_fd_at(W.cgfd, cg + "/cgroup.events");
        return !ev.empty() && ev.find("populated 0") == std::string::npos;
    };
    if (!populated()) return "";
    int fd = openat(W.cgfd, (cg + "/cgroup.kill").c_str(), O_WRONLY | O_CLOEXEC);
    bool ok = fd >= 0 && write(fd, "1", 1) == 1;
    int e = errno;
    if (fd >= 0) close(fd);
    if (!ok) return "CgroupKillFailed " + name + ": writing " + cg + "/cgroup.kill: " + errstr(e) + " (cgroup.kill needs Linux 5.14)";
    log("forget -k " + name + ": wrote cgroup.kill of " + cg);
    double end = mono_now() + FORGET_KILL_WAIT;
    while (populated()) {
        if (mono_now() > end)
            return "Timeout " + name + ": its cgroup " + cg + " still has processes " + seconds_text(FORGET_KILL_WAIT) +
                   " s after writing cgroup.kill";
        usleep(10000);
    }
    return "";
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

// init（mount 模式）天空裡的 daemon_path 與旁邊的 cgroup 是 daemon 放的，ctl 的 mount／umount 不准動（蓋住或卸掉就斷了）
std::string reserved_dst(const std::string& name, const std::string& dst) {
    std::lock_guard<std::mutex> g(S.mu);
    auto p = find(name);
    if (!p || !p->init || !init_mounts(p->cfg)) return "";
    std::string dp = init_daemon_path(p->cfg), cp = init_cgroup_path(p->cfg);
    for (const std::string& t : {dp, cp}) {
        if (t == cp && W.cgfd < 0) continue;
        if (dst == t || dst.rfind(t + "/", 0) == 0)
            return "PathReserved " + t + " in init's ns is where the daemon put its " + (t == dp ? "directory" : "cgroup directory");
    }
    return "";
}

bool abs_clean(const std::string& p) { return abs_path_ok(p); }

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
            err = load_seccomp_list(cfg);   // locks.seccomp 是名單檔時：讀檔、名字換號碼（錯了 EIO＋ConfigBad）
            if (!err.empty()) return pf::Result::failed(err);
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
    // forget [-k] NAME：-k＝那隻（一定要已經死了）的 cgroup 夾裡還有它留下的行程，先寫 cgroup.kill、等到空再拿掉；沒有 cgroup 時跟 forget 一樣
    ctl.on("forget",
        [](const pf::Command& c) {
            bool k = c.words[1] == "-k";
            const std::string& name = c.words.back();
            std::string cg;
            std::shared_ptr<Proc> p;
            {
                std::lock_guard<std::mutex> g(S.mu);
                p = find(name);
                if (!p) return pf::Result::failed("ProcUnknown " + name);
                if (p->alive) return pf::Result::failed("ProcAlive " + name);
                cg = p->sp.cgroup;
            }
            if (k && !cg.empty()) {
                std::string e = clear_cgroup(name, cg);
                if (!e.empty()) return pf::Result::failed(e);
            }
            if (!cg.empty()) {
                // 不帶 -k：cgroup 裡還有它留下的行程就不拿掉（要收由 init 寫 cgroup.kill，或用 forget -k）
                // 帶 -k：已經空了；剛被殺的還沒收屍時 rmdir 可能短暫 EBUSY，等一下
                double end = mono_now() + (k ? FORGET_KILL_WAIT : 0);
                for (;;) {
                    if (unlinkat(W.cgfd, cg.c_str(), AT_REMOVEDIR) == 0 || errno == ENOENT) break;
                    if (!k || errno != EBUSY || mono_now() > end)
                        return pf::Result::failed("CgroupNotEmpty " + name + ": " + errstr(errno) +
                                                  " (processes it left are still in its cgroup; write 1 to its cgroup/cgroup.kill, or use forget -k " +
                                                  name + ")");
                    usleep(10000);
                }
            }
            drop_proc(name, p.get());   // 這段時間裡 init 被重起成同名的新一隻，就不拿那隻
            log("forgot " + name + (k ? " (-k)" : ""));
            return pf::Result::done();
        },
        [](const pf::Command& c) -> std::string {
            bool k = c.words.size() > 1 && c.words[1] == "-k";
            if (c.words.size() != (k ? 3u : 2u)) return "ArgumentsBad usage: forget [-k] NAME";
            return check_name(pf::Command{c.line, {c.words[0], c.words.back()}}, 2, "forget [-k] NAME", 0);
        });
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
                std::string check, nsj, ns = ns_table(p->sp.pid, m, check, nsj);
                std::lock_guard<std::mutex> g(S.mu);
                p->sp.mounts = m;
                p->sp.ns = ns;
                p->sp.ns_json = nsj;
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
                std::string check, nsj, ns = ns_table(p->sp.pid, m, check, nsj);
                std::lock_guard<std::mutex> g(S.mu);
                p->sp.mounts = m;
                p->sp.ns = ns;
                p->sp.ns_json = nsj;
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
    s += pf::kv_line("config", O.config_path.empty() ? "-" : O.config_path);
    s += pf::kv_line("init", HAS_INIT ? ICFG.name : "-");
    std::string state = "none (no init in the daemon config)";
    if (HAS_INIT && !S.init_gone.empty()) {
        state = "gone (restart limit reached: " + S.init_gone + "; on_restart_limit stay)";
    } else if (HAS_INIT) {
        auto p = find(ICFG.name);
        state = p && p->init ? (p->alive ? "alive" : "dead") : "starting";
    }
    s += pf::kv_line("init_state", state);
    s += pf::kv_line("on_init_exit", O.restart ? "restart" : "exit");
    s += pf::kv_line("restart_limit", std::to_string(O.restart_limit) + " deaths within " +
                                          std::to_string(static_cast<int>(O.restart_window)) + " s");
    s += pf::kv_line("on_restart_limit", O.restart_limit_stay ? "stay" : "exit");
    s += pf::kv_line("exit_code", O.exit_code_own ? "own" : "init");
    s += pf::kv_line("exit_grace", seconds_text(O.exit_grace) + " s");
    s += pf::kv_line("on_parent_death", O.parent_death_exit ? "exit" : "stay");
    s += pf::kv_line("init_restarts", std::to_string(S.init_restarts));
    s += pf::kv_line("init_deaths_in_window", std::to_string(S.deaths.size()));
    s += pf::kv_line("init_last_exit", S.init_last_exit);
    s += pf::kv_line("landlock_abi", std::to_string(W.landlock_abi));
    s += pf::kv_line("cgroup", W.cgfd >= 0 ? W.cg_host : "off (" + W.cg_note + ")");
    s += pf::kv_line("subuid", W.subuid_count ? std::to_string(W.subuid_start) + " " + std::to_string(W.subuid_count) : "none");
    s += pf::kv_line("init_access", !HAS_INIT ? "-" : init_mounts(ICFG) ? "mount " + init_daemon_path(ICFG) : "ptrace /proc/1/cwd");
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
    // on_parent_death exit（預設）：起動那一層死了就跟著走；先設再等 pipe，起動那一層在中間死了也不會漏
    // stay：不設；起動那一層死了 daemon 照跑（被外面那層的 init／subreaper 收養），結束由對 daemon 送 SIGTERM
    if (O.parent_death_exit) prctl(PR_SET_PDEATHSIG, SIGKILL);
    long info[6] = {0};   // 外面的 PID、setgroups_ok、subuid 起點、數量、外面的 uid、gid
    if (read(sync_fd, info, sizeof info) != static_cast<ssize_t>(sizeof info)) _exit(2);
    close(sync_fd);
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
    const char* cg = getenv("AOS_DAEMON_CGROUP");
    W.cg_note = getenv("AOS_DAEMON_CGROUP_NOTE") ? getenv("AOS_DAEMON_CGROUP_NOTE") : "";
    if (cg && *cg) {
        W.cg_host = cg;
        W.cgfd = open(cg, O_PATH | O_DIRECTORY | O_CLOEXEC);
        if (W.cgfd < 0) fatal("open cgroup " + W.cg_host + ": " + errstr(errno));
    }
    unsetenv("AOS_DAEMON_CGROUP");
    unsetenv("AOS_DAEMON_CGROUP_NOTE");
    unsetenv("AOS_DAEMON_IN_SCOPE");
    long abi = syscall(SYS_landlock_create_ruleset, nullptr, 0, LANDLOCK_CREATE_RULESET_VERSION);
    W.landlock_abi = abi > 0 ? static_cast<int>(abi) : 0;
    HAS_INIT = has_init(O);
    if (HAS_INIT) {
        std::string err, text = O.init_text;   // daemon 設定檔裡內嵌的就不用讀檔
        if (text.empty()) text = read_host_file(O.init_path, err);
        if (!err.empty()) fatal(err);
        try {
            ICFG = parse_config(text, O.init_path);
        } catch (const std::exception& e) {
            fatal(std::string(e.what()) + " in " + O.init_path);
        }
        // init 的 locks.seccomp 名單檔只在起動時讀一次（重起時用同一份）
        if (std::string se = load_seccomp_list(ICFG); !se.empty()) fatal(se + " in " + O.init_path);
        if (ICFG.uid != 0)
            fatal("ConfigBad init must run as uid 0 in its ns (its \"uid\" is " + std::to_string(ICFG.uid) +
                  "): ctl is 0200 and only the daemon's uid may use the mounted directory, in " + O.init_path);
        if (ICFG.landlock && W.landlock_abi < 1)
            fatal("ConfigBad init asks for Landlock (locks.landlock true) but this Linux has none, in " + O.init_path);
        // cgroup 夾這時已經握住了（有沒有 cgroup 定了）
        std::string bad = init_ns_conflict(ICFG, W.cgfd >= 0);
        if (!bad.empty()) fatal(bad + " in " + O.init_path);
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
    opt.fsname = "aosdaemon";
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

    if (HAS_INIT) {
        std::string err = start_proc(ICFG, true);
        if (!err.empty()) init_died("failed to start: " + err, 1);
    } else {
        log("no init (the daemon config has no \"init\"): only the outside reaches the directory, through /proc/" +
            std::to_string(W.host_pid) + "/cwd");
    }

    for (;;) {
        pollfd p[2] = {{sfd, POLLIN, 0}, {EFD, POLLIN, 0}};
        int timeout = -1;
        if (stopping) {
            double left = stop_deadline - mono_now();
            timeout = left <= 0 ? 0 : left > 3600 ? 3600000 : static_cast<int>(left * 1000) + 1;
        }
        if (poll(p, 2, timeout) < 0 && errno != EINTR) fatal("poll: " + errstr(errno));
        signalfd_siginfo si;
        while (read(sfd, &si, sizeof si) == static_cast<ssize_t>(sizeof si)) {
            if (si.ssi_signo == SIGCHLD) continue;
            begin_stop(static_cast<int>(si.ssi_signo));
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
        if (stopping && mono_now() >= stop_deadline)
            shutdown(0, stop_why + "; init was still running after exit_grace " + seconds_text(O.exit_grace) + " s");
    }
}

}  // namespace d2
