// stuck.cpp：【daemon】依公開 ctl/state_flux 窗的刺激與兩鐘期限標記卡住，並選擇收回重起。
#include "daemon/daemon.hpp"
#include "aos/util/files.hpp"
#include "aos/util/proc.hpp"
#include <limits>
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
    using aos::loop::StateFluxWindow;
    Json ctl = ctl_name(c.stack, names_);
    Json flux = StateFluxWindow::default_name;
    // 父寫的設定只提供公開窗名，不據此分類。
    auto cfg = aos::read_json(aos::join(c.stack, names_.loop));
    if (cfg && cfg->is_object()) {
        flux = cfg->value(StateFluxWindow::config_key, flux);
    }
    if (!ctl.is_string() || !flux.is_string()) {
        clear();
        return;
    }
    std::string ctl_path = aos::join(c.stack, ctl.get<std::string>());
    std::string flux_path = aos::join(c.stack, flux.get<std::string>());
    struct stat st {};
    auto response = aos::read_window("aos-daemon", flux_path);
    if (stat(ctl_path.c_str(), &st) != 0 || !S_ISREG(st.st_mode) || !response || !response->is_object()) {
        clear();
        return;
    }
    // 公開時間欄是 UTC 毫秒，與 ctl mtime 截到毫秒後使用同一格式比較。
    std::string modified = aos::utc_ms_at(static_cast<long long>(st.st_mtim.tv_sec) * 1000000000LL + st.st_mtim.tv_nsec);
    Json at = response->value(StateFluxWindow::responded_at, Json());
    if (!at.is_null() && !at.is_string()) {
        clear();
        return;
    }
    std::string answered = at.is_string() ? at.get<std::string>() : "";
    if (answered > c.observed_at && answered != c.last_response) {
        c.stuck_restarts = 0;   // 重起之後有過任何回應，連敗重新起算。
    }
    c.last_response = answered;
    // 11-06 晚（no-pid P9 06-06）：ctl 修改時間在未來（時鐘倒退、搬家時鐘差、手改 mtime）＝不當刺激，等牆鐘追上再看（no-pid 06「刺激在未來→不判」）。
    if (modified <= c.observed_at || modified <= answered || modified > aos::utc_now_ms()) {
        clear();
        return;
    }
    if (!c.stuck_deadline) {
        if (c.stuck_after_ms) {
            long long now = aos::utc_now_epoch_ms();
            long long ms = *c.stuck_after_ms;
            long long max = std::numeric_limits<long long>::max();
            // 正毫秒加到牆鐘若超過 signed 64-bit，期限飽和，避免相加溢位。
            long long at = max;
            if (now <= max - ms) {
                at = now + ms;
            }
            c.stuck_deadline = aos::Deadline{false, at};
        } else {
            c.stuck_deadline = aos::deadline_after(c.stuck_after_cycles);
        }
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
