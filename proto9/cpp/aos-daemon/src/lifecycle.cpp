// lifecycle.cpp：表上一隻底下的 proc 的狀態變化——登記成功、結束（自己的孩子或外來的）、procs/<名> 連結的加與拿掉；呼叫時都拿著 State::mu。
#include "daemon.hpp"

#include <sstream>
#include <sys/wait.h>
#include <unistd.h>

namespace aosd {

namespace {

Clock::duration secs(double s) { return std::chrono::duration_cast<Clock::duration>(std::chrono::duration<double>(s)); }

// 表上存的 "-"＝沒有：欄位表裡是空字串／沒有值（純文字照樣寫 -，json 是 null）
std::string none(const std::string& s) { return s == "-" ? "" : s; }
std::optional<long long> num(const std::string& s) {
    if (s == "-" || s.empty()) return std::nullopt;
    return std::stoll(s);
}

// aos_obey 的值：只留認得的字（stop、kill），照 stop、kill 的先後、不重複
std::vector<std::string> parse_obey(const std::string& v) {
    std::vector<std::string> out;
    for (const char* w : {"stop", "kill"}) {
        std::istringstream in(v);
        for (std::string x; in >> x;)
            if (x == w) {
                out.push_back(w);
                break;
            }
    }
    return out;
}

}  // namespace

ProcRow row_of(const Proc& p) {
    ProcRow r;
    r.phase = p.phase;
    r.want = p.want;
    if (p.pid > 0) r.pid = p.pid;
    r.code = num(p.code);
    r.signal = num(p.sig);
    r.reason = none(p.reason);
    r.persists = none(p.persists);
    r.mailbox = none(p.mailbox);
    r.stuck = p.stuck;
    if (p.external) {
        r.external = "yes";
        std::string words;
        for (const auto& w : p.obey) words += (words.empty() ? "" : " ") + w;
        r.obey = words;
    }
    return r;
}

void Supervisor::registered(const std::string& name, unsigned long long id, const std::string& settings) {
    Proc* p = find(name, id);
    if (!p || p->phase != "starting" || p->pid < 0) return;
    p->phase = "running";
    p->persists = kv_get(settings, "aos_persists");
    p->mailbox = kv_get(settings, "aos_mailbox");
    // 外來的：daemon 能對它下哪幾個字，只照它自己 settings 的 aos_obey（不照登記的人說的）；沒有這行＝只收 rm
    if (p->external) p->obey = parse_obey(kv_get(settings, "aos_obey"));
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
    if (!p.killed.empty()) p.reason = p.killed;
    else if (p.want == "down") p.reason = "stopped (registered, not our child: no exit code)";
    else p.reason = "exited (registered, not our child: no exit code)";
    p.stuck = "no";
    unlink(p);
    // 是 daemon 照 aos_obey 收掉的，它的死掛載也順手清；自己死的照舊不碰
    if (!p.killed.empty() && !p.mount.empty()) cleanups_.push_back(p.mount);
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
