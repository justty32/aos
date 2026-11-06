// stuck.cpp：【daemon】依公開 ctl/state 窗的刺激與兩鐘期限標記卡住，並選擇收回重起。
#include "daemon/daemon.hpp"
#include "aos/util/files.hpp"
#include "aos/util/proc.hpp"
#include <sys/stat.h>

namespace aos::daemon {

void Daemon::check_stuck(const std::string& name, Child& c) {
    auto clear = [&] {
        c.stuck = false;
        c.stuck_deadline.reset();
    };
    if (stopping_) {
        clear();
        return;
    }
    using aos::loop::CtlWindow;
    using aos::loop::StateWindow;
    Json ctl = CtlWindow::default_name;
    Json state = StateWindow::default_name;
    if (!c.once) {
        // loop.json 是父自己寫的設定；不辨認子程式的身分。
        auto cfg = aos::read_json(aos::join(c.stack, names_.loop));
        if (!cfg || !cfg->is_object()) {
            clear();
            return;
        }
        ctl = cfg->value(CtlWindow::config_key, ctl);
        state = cfg->value(StateWindow::config_key, state);
    }
    if (!ctl.is_string() || !state.is_string()) {
        clear();
        return;
    }
    std::string ctl_path = aos::join(c.stack, ctl.get<std::string>());
    std::string state_path = aos::join(c.stack, state.get<std::string>());
    struct stat st {};
    auto response = aos::read_json(state_path);
    if (stat(ctl_path.c_str(), &st) != 0 || !S_ISREG(st.st_mode) || !response || !response->is_object()) {
        clear();
        return;
    }
    // 公開時間欄是 UTC 毫秒，與 ctl mtime 截到毫秒後使用同一格式比較。
    std::string modified = aos::utc_ms_at(static_cast<long long>(st.st_mtim.tv_sec) * 1000000000LL + st.st_mtim.tv_nsec);
    Json at = response->value(StateWindow::responded_at, Json());
    if (!at.is_null() && !at.is_string()) {
        clear();
        return;
    }
    std::string answered = at.is_string() ? at.get<std::string>() : "";
    if (answered > c.observed_at && answered != c.last_response) {
        c.stuck_restarts = 0;   // 重起之後有過任何回應，連敗重新起算。
    }
    c.last_response = answered;
    if (modified <= c.observed_at || modified <= answered) {
        clear();
        return;
    }
    if (!c.stuck_deadline) {
        c.stuck_deadline = aos::deadline_after(c.stuck_after_ticks);
    }
    if (!aos::expired(*c.stuck_deadline)) {
        return;
    }
    c.stuck = true;
    if (c.restart_on_stuck && !paused_) {
        ++c.stuck_restarts;
        Json line = Json::object({{"at", aos::utc_now_ms()}, {"name", name}, {"phase", "stuck"},
                                  {"reason", c.stuck_restarts >= 3 ? "control window response timed out 3 times without a response; stopping" : "control window response timed out; restarting"}});
        log_line(line);
        term(c);   // 現成 SIGTERM／10 秒 SIGKILL／settle 路徑。
        c.stuck_restart = true;
    }
}

}  // namespace aos::daemon
