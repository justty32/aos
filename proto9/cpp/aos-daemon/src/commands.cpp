// commands.cpp：監工做 procs_ctl 的字（add／rm／stop／start／kill／register）與 daemon 自己 stop 時收掉底下的；「做完」＝daemon 這邊的動作做完。
#include "daemon.hpp"

#include <cerrno>
#include <csignal>
#include <cstring>
#include <sys/syscall.h>
#include <unistd.h>

namespace aosd {

namespace {

Clock::duration secs(double s) { return std::chrono::duration_cast<Clock::duration>(std::chrono::duration<double>(s)); }

std::string ctl_error(int err, const std::string& name) {
    if (err == ETIMEDOUT) return "CtlTimeout " + name + " did not take the command in time (stuck? use kill)";
    if (err == EBUSY) return "CtlBusy " + name + "'s ctl is locked";
    return "CtlFailed " + name + ": " + std::strerror(err);
}

}  // namespace

void Request::finish(std::string err) {
    std::lock_guard<std::mutex> g(mu);
    error = std::move(err);
    finished = true;
    cv.notify_all();
}

bool Request::wait(double seconds) {
    std::unique_lock<std::mutex> lk(mu);
    return cv.wait_for(lk, std::chrono::duration<double>(seconds), [&] { return finished; });
}

std::string Supervisor::child_name(const std::string& name) const {
    return cfg_.aos_name == "/" ? name : cfg_.aos_name + "/" + name;
}

void Supervisor::handle(const std::shared_ptr<Request>& r) {
    const auto& w = r->words;
    std::lock_guard<std::mutex> g(st_.mu);
    if (w[0] == "add") return cmd_add(r);
    if (w[0] == "register") return cmd_register(r);
    // 回答的線上的 Check 已經看過一次；這裡再看，是因為兩者之間表可能變了
    auto it = st_.procs.find(w[1]);
    if (it == st_.procs.end()) return r->finish("ProcUnknown " + w[1]);
    Proc& p = it->second;
    if (w[0] == "rm") return cmd_rm(r, p);
    if (p.external) return r->finish("ProcExternal " + p.name + " was registered, not started here");
    if (w[0] == "stop") return cmd_stop(r, p);
    if (w[0] == "kill") {
        p.want = "down";
        if (p.pid > 0) force_kill(p, "killed by procs_ctl kill");
        return r->finish("");
    }
    // start
    if (shutting_) return r->finish("DaemonStopping not starting anything now");
    if (p.pid > 0) return r->finish(p.phase == "stopping" ? "ProcStopping " + p.name + " is still stopping" : "");
    r->finish(start_proc(p));
}

void Supervisor::cmd_add(const std::shared_ptr<Request>& r) {
    const std::string name = r->words[1], path = r->words[2];
    if (st_.procs.count(name)) return r->finish("ProcExists " + name);
    if (shutting_) return r->finish("DaemonStopping not starting anything now");
    std::string mdir = child_name(name);
    for (char& c : mdir)
        if (c == '/') c = '%';
    Proc& p = st_.procs[name];
    p.name = name;
    p.id = next_id_++;
    p.phase = "starting";
    p.reason = "reading " + path;
    p.mount = cfg_.mount_base + "/" + mdir;
    unsigned long long id = p.id;
    // 路徑可能指到某隻卡住的 proc 的目錄裡，所以連讀這份檔也交給小行程、帶期限
    helper(p, path, false, "", cfg_.ctl_timeout, [this, r, name, id, path](bool ok, int err, const std::string& data) {
        Proc* q = find(name, id);
        if (!q) return r->finish("ProcGone " + name + " was removed while loading");
        auto drop = [&](const std::string& why) {
            st_.procs.erase(name);
            r->finish(why);
        };
        if (!ok) return drop("PathBad " + path + ": " + (err == ETIMEDOUT ? "read timed out" : std::strerror(err)));
        size_t b = data.find_first_not_of(" \t\r\n");
        if (b != std::string::npos && data[b] == '{') {
            std::string why = parse_spec(data, q->argv, q->env);
            if (!why.empty()) return drop(why);
            // exec[0] 帶 / 卻不是絕對路徑：照 json 檔所在的夾算
            std::string& a0 = q->argv[0];
            if (a0.find('/') != std::string::npos && a0[0] != '/') a0 = path.substr(0, path.rfind('/') + 1) + a0;
        } else if (err != 0) {
            return drop("PathBad " + path + " is neither executable nor a json spec");
        } else {
            q->argv = {path};
        }
        r->finish(start_proc(*q));
    });
}

void Supervisor::cmd_register(const std::shared_ptr<Request>& r) {
    const std::string name = r->words[1];
    pid_t pid = static_cast<pid_t>(std::stol(r->words[2]));
    if (st_.procs.count(name)) return r->finish("ProcExists " + name);
    if (shutting_) return r->finish("DaemonStopping not registering anything now");
    for (auto& [n, q] : st_.procs)
        if (q.pid == pid) return r->finish("ProcExists pid " + r->words[2] + " is already " + n);
    // pidfd 釘住那支行程：它死了會變得可讀，PID 被別人拿走也不會認錯
    int fd = static_cast<int>(syscall(SYS_pidfd_open, pid, 0));
    if (fd < 0) return r->finish("ProcMissing no process " + r->words[2] + ": " + std::strerror(errno));
    Proc& p = st_.procs[name];
    p.name = name;
    p.id = next_id_++;
    p.external = true;
    p.pid = pid;
    p.pidfd = fd;
    p.phase = "starting";
    p.deadline = Clock::now() + secs(cfg_.register_timeout);
    p.next_try = Clock::now();
    r->finish("");
}

void Supervisor::cmd_stop(const std::shared_ptr<Request>& r, Proc& p) {
    p.want = "down";
    if (p.pid < 0) return r->finish("");
    if (p.phase == "starting") return r->finish("ProcStarting " + p.name + " has not registered yet (no ctl); use kill");
    if (p.hung > 0) return r->finish("ProcStuck " + p.name + " does not answer; use kill");
    std::string name = p.name;
    unsigned long long id = p.id;
    helper(p, cwd_of(p.pid) + "/ctl", true, "stop\n", cfg_.ctl_timeout, [this, r, name, id](bool ok, int err, const std::string&) {
        Proc* q = find(name, id);
        if (ok && q && q->phase == "running") q->phase = "stopping";
        r->finish(ok ? "" : ctl_error(err, name));
    });
}

void Supervisor::cmd_rm(const std::shared_ptr<Request>& r, Proc& p) {
    if (p.external || p.pid < 0) {
        // 外來的只從表上拿掉：不送訊號、不碰它的掛載
        unlink(p);
        if (p.pidfd >= 0) close(p.pidfd);
        st_.procs.erase(p.name);
        return r->finish("");
    }
    p.removing = true;
    p.want = "down";
    p.deadline = Clock::now() + secs(cfg_.stop_timeout);
    if (p.phase != "running" || p.hung > 0) {
        force_kill(p, "killed by rm");
        return r->finish("");
    }
    std::string name = p.name;
    unsigned long long id = p.id;
    helper(p, cwd_of(p.pid) + "/ctl", true, "stop\n", cfg_.ctl_timeout, [this, r, name, id](bool ok, int, const std::string&) {
        Proc* q = find(name, id);
        if (q && !ok) force_kill(*q, "killed by rm (stop was not taken)");
        else if (q && q->phase == "running") q->phase = "stopping";
        r->finish("");
    });
}

// 呼叫時拿著 st_.mu；fork 很快，不怕擋住讀表的人
std::string Supervisor::start_proc(Proc& p) {
    std::vector<std::string> env = p.env;
    env.push_back("AOS_NAME=" + child_name(p.name));
    env.push_back("AOS_MOUNT=" + p.mount);
    env.push_back("AOS_ROOT=" + cfg_.aos_root);
    std::string err;
    pid_t pid = spawn(p.argv, env, err);
    p.code = p.sig = p.persist = p.mailbox = "-";
    p.stuck = "no";
    p.killed.clear();
    p.last_error.clear();
    p.want = "up";
    if (pid < 0) {
        p.phase = "failed";
        p.reason = err;
        return err;
    }
    p.pid = pid;
    p.phase = "starting";
    p.reason = "-";
    p.deadline = Clock::now() + secs(cfg_.register_timeout);
    p.next_try = Clock::now() + secs(0.05);
    return "";
}

// 強制收：先斷開它的 FUSE 連線（放開被它拖住的人），再 SIGKILL；死掛載等收屍時清
void Supervisor::force_kill(Proc& p, const std::string& why) {
    if (p.pid < 0 || p.external) return;
    std::string m = mount_of_pid(p.pid);
    if (!m.empty()) pf::abort_connection(m);
    kill(p.pid, SIGKILL);
    p.killed = why.empty() ? "killed by daemon" : why;
}

void Supervisor::begin_shutdown() {
    if (shutting_) return;
    shutting_ = true;
    shut_deadline_ = Clock::now() + secs(cfg_.stop_timeout);
    std::lock_guard<std::mutex> g(st_.mu);
    st_.phase = "stopping";
    for (auto& [name, p] : st_.procs) {
        if (p.external || p.pid < 0) continue;
        p.want = "down";
        if (p.phase != "running" || p.hung > 0) {
            force_kill(p, "killed by daemon stop");
            continue;
        }
        unsigned long long id = p.id;
        helper(p, cwd_of(p.pid) + "/ctl", true, "stop\n", cfg_.ctl_timeout, [this, name, id](bool ok, int, const std::string&) {
            Proc* q = find(name, id);
            if (q && ok && q->phase == "running") q->phase = "stopping";
        });
    }
}

// 回 true＝可以結束了：底下自己起的都收完了，或強制收之後也等夠了
bool Supervisor::shutdown_tick() {
    auto now = Clock::now();
    std::lock_guard<std::mutex> g(st_.mu);
    bool any = false;
    for (auto& [name, p] : st_.procs) any = any || (!p.external && p.pid > 0);
    if (!any) return true;
    if (forced_) return now >= shut_deadline_;
    if (now < shut_deadline_) return false;
    forced_ = true;
    shut_deadline_ = now + secs(3);
    for (auto& [name, p] : st_.procs) force_kill(p, "killed by daemon stop (did not stop in time)");
    return false;
}

}  // namespace aosd
