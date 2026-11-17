// ctl.cpp：【daemon】由控制窗推得期望表、停止與睡眠集合（說明見 daemon.hpp）。
#include "daemon/daemon.hpp"

namespace aos::daemon {

bool Daemon::from_ctl(const std::string& name) const {
    if (pctl_path_.empty()) {
        return false;
    }
    const Json& c = pctl_good_;
    return (c.contains("procs") && c["procs"].contains(name)) || (c.contains("procs_added") && c["procs_added"].contains(name));
}

const Json& Daemon::ctl_want(const Json& ctl, Json& merged) const {
    // 期望表（N-06：整份 procs_ctl 就是期望，沒寫的回底）＝（procs_ctl 的 procs，沒寫＝底的）＋procs_added－procs_removed
    const Json& base = ctl.contains("procs") ? ctl["procs"] : want_;
    return merge_want(base, ctl, "procs_added", "procs_removed", merged);
}

Names Daemon::ctl_stopped(const Json& ctl) const {
    Names s = stopped_;   // 先加後減：同名兩邊都寫＝起（procs § 2c 第 1 條）
    if (ctl.contains("procs_stopped")) {
        for (const Json& n : ctl["procs_stopped"]) {
            s.insert(n.get<std::string>());
        }
    }
    if (ctl.contains("procs_started")) {
        for (const Json& n : ctl["procs_started"]) {
            s.erase(n.get<std::string>());
        }
    }
    return s;
}

Names Daemon::ctl_slept(const Json& ctl) const {
    Names s = slept_;   // 11-05：同 ctl_stopped（同名兩邊都寫＝醒）
    if (ctl.contains("procs_slept")) {
        for (const Json& n : ctl["procs_slept"]) {
            s.insert(n.get<std::string>());
        }
    }
    if (ctl.contains("procs_woken")) {
        for (const Json& n : ctl["procs_woken"]) {
            s.erase(n.get<std::string>());
        }
    }
    return s;
}


}  // namespace aos::daemon
