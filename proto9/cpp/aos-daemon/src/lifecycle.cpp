// lifecycle.cpp：表上一隻底下的 proc 的狀態變化——登記成功、結束（自己的孩子或外來的）、procs/<名> 連結的加與拿掉；呼叫時都拿著 State::mu。
#include "daemon.hpp"

#include <sys/wait.h>
#include <unistd.h>

namespace aosd {

namespace {

Clock::duration secs(double s) { return std::chrono::duration_cast<Clock::duration>(std::chrono::duration<double>(s)); }

}  // namespace

void Supervisor::registered(const std::string& name, unsigned long long id, const std::string& settings) {
    Proc* p = find(name, id);
    if (!p || p->phase != "starting" || p->pid < 0) return;
    p->phase = "running";
    p->persist = kv_get(settings, "aos_persist");
    p->mailbox = kv_get(settings, "aos_mailbox");
    p->reason = "-";
    p->stuck = "no";
    p->next_try = Clock::now() + secs(cfg_.check_interval);
    link(*p);
}

// 自己的子行程結束了；呼叫時拿著 st_.mu
void Supervisor::exited(Proc& p, int status) {
    std::string what;
    if (WIFEXITED(status)) {
        p.code = std::to_string(WEXITSTATUS(status));
        p.sig = "-";
        what = "code " + p.code;
    } else {
        p.code = "-";
        p.sig = std::to_string(WTERMSIG(status));
        what = "signal " + p.sig + " (" + signal_name(WTERMSIG(status)) + ")";
    }
    if (p.phase == "starting") {
        p.phase = "failed";
        p.reason = "exited before registering (" + what + ")";
    } else if (p.phase != "failed") {
        p.phase = "stopped";
        if (!p.killed.empty()) p.reason = p.killed;
        else if (p.want == "down" && what == "code 0") p.reason = "stopped";
        else p.reason = (WIFEXITED(status) ? "exited with " : "killed by ") + what;
    }
    p.pid = -1;
    p.stuck = "no";
    unlink(p);
    if (!p.mount.empty()) cleanups_.push_back(p.mount);
    if (p.removing) st_.procs.erase(p.name);
}

void Supervisor::external_gone(Proc& p) {
    close(p.pidfd);
    p.pidfd = -1;
    p.pid = -1;
    if (p.phase != "failed") p.phase = "stopped";
    p.reason = "exited (registered, not our child: no exit code)";
    p.stuck = "no";
    unlink(p);
}

void Supervisor::link(Proc& p) {
    if (p.linked || p.pid < 0) return;
    try {
        fs_.add_symlink("procs/" + p.name, cwd_of(p.pid));
        p.linked = true;
    } catch (const std::exception&) {
    }
}

void Supervisor::unlink(Proc& p) {
    if (!p.linked) return;
    fs_.remove("procs/" + p.name);
    p.linked = false;
}

Proc* Supervisor::find(const std::string& name, unsigned long long id) {
    auto it = st_.procs.find(name);
    return it != st_.procs.end() && it->second.id == id ? &it->second : nullptr;
}

}  // namespace aosd
