// adopt.cpp：【daemon】接回上次的 proc 表與小格裡仍活著的子 loop（說明見 daemon.hpp）。
#include "daemon/daemon.hpp"
#include "aos/util/files.hpp"
#include "aos/util/proc.hpp"
#include <filesystem>

namespace aos::daemon {

using aos::loop::StateWindow;

Json Daemon::unrel(const Json& v) const {
    if (!v.is_string() || v.get<std::string>().empty()) {
        return v;
    }
    std::string s = v.get<std::string>();
    if (s[0] == '/' || s[0] == '#') {
        return v;   // 舊表（絕對）照用
    }
    size_t hash = s.find('#');
    std::string file = aos::abspath(aos::join(dstack_, s.substr(0, hash)));
    return Json(file + (hash == std::string::npos ? "" : s.substr(hash)));
}

// 11-05 第二輪：小格裡子 loop 自己的 state 窗（檔名看 daemon 寫的 loop.json 的 state，沒寫＝state.json、null＝沒開）。讀不到＝nullopt。
static std::optional<Json> cell_state(const std::string& cell, const std::string& loop_name) {
    std::optional<Json> cfg = aos::read_json(aos::join(cell, loop_name));
    Json name = StateWindow::default_name;
    if (cfg && cfg->is_object()) {
        name = cfg->value(StateWindow::config_key, name);
    }
    if (!name.is_string() || name.get<std::string>().empty()) {
        return std::nullopt;
    }
    std::optional<Json> st = aos::read_json(aos::join(cell, name.get<std::string>()));
    if (!st || !st->is_object()) {
        return std::nullopt;
    }
    return st;
}

// 11-05 第二輪：小格裡已經有一支活著的子 loop（它自己的 state 窗記的 pid＋started_at_ticks 對得上）＝回 pid、ticks。
// daemon 在「fork 了、表還沒寫」或「列在 stopping」時被 kill -9，重開後那支不在表上（或沒被接回），原本會在同一格再起一份（兩支 aos-loop 搶一個 stack）。
std::optional<std::pair<pid_t, long long>> live_in_cell(const std::string& cell, const std::string& loop_name) {
    std::optional<Json> st = cell_state(cell, loop_name);
    if (!st) {
        return std::nullopt;
    }
    Json pid = st->value(StateWindow::pid, Json());
    Json ticks = st->value(StateWindow::started_at_ticks, Json());
    if (!pid.is_number_integer() || !ticks.is_number_integer() || pid.get<long long>() <= 0) {
        return std::nullopt;
    }
    std::optional<long long> now = aos::proc_started_at_ticks((pid_t)pid.get<long long>());
    if (!now || *now != ticks.get<long long>()) {
        return std::nullopt;
    }
    return std::make_pair((pid_t)pid.get<long long>(), ticks.get<long long>());
}

void Daemon::adopt() {
    if (pstate_path_.empty()) {
        return;
    }
    std::optional<Json> old = aos::read_json(pstate_path_);
    if (!old || !old->is_object() || !old->contains("procs")) {
        return;   // 第一次起來、或舊的讀不了：沒東西可接
    }
    Json table;
    try {   // 切檔（10-23）：是 {"$ref": [分檔, …]}，用 aos-directive 解開就是合好的表；分檔讀不到＝舊的讀不了
        table = aos::resolve((*old)["procs"], aos::dirname(pstate_path_));
    } catch (const Error&) {
        return;
    }
    if (!table.is_object()) {
        return;
    }
    for (auto& [name, r] : table.items()) {
        if (!r.is_object()) {
            return;   // 有一列壞就整份不接
        }
    }
    // 上一個 daemon 死的時候在收工（state 窗 phase stopping）＝它正在收的那些本來要睡下（sleeping），不是被 stop
    std::optional<Json> me = state_path_.empty() ? std::nullopt : aos::read_json(state_path_);
    bool finishing = me && me->is_object() && me->value("phase", Json()) == "stopping";
    // 11-06（no-pid P1）：表頂層的 boot_id 跟這次開機不同（或沒寫）＝表上的行程都不在了（重開機後 pid＋ticks 可能撞上別的行程）；這台讀不到 boot_id＝照舊只比 pid＋ticks
    std::optional<std::string> boot = aos::boot_id();
    bool same_boot = !boot || old->value("boot_id", Json()) == Json(*boot);
    for (auto& [name, r] : table.items()) {
        Json phase = r.value("phase", Json());
        Json st = r.value("stack", Json());
        Child c;
        c.own = false;
        c.auto_restart = auto_restart_of(r);
        c.restart_on_stuck = ros_of(r);
        // 11-05（portable-flow）：表上的路徑相對 daemon 的 stack（dstack_）拼回；絕對的（舊表）照用
        c.stack = st.is_string() && !st.get<std::string>().empty() ? unrel(st).get<std::string>() : cell_of(name, Json());
        if (r.value("ws", Json()).is_string()) {
            c.ws = unrel(r["ws"]);
        }
        if (r.value("exec", Json()).is_string()) {
            c.exec = unrel(r["exec"]);   // 11-04 晚：照舊表帶過來（信箱模式接回的列沒有設定，exec 欄只能從這裡來）
        }
        if (r.value("def", Json()).is_string()) {
            c.def = unrel(r["def"]);   // 11-04（使用者「那就b。」）：同 exec 欄
        }
        if (r.value("reason", Json()).is_string()) {
            c.reason = r["reason"];   // 11-05：stopped 的原因照帶
        }
        if (r.value("limits", Json()).is_object()) {
            c.limits = r["limits"];   // 11-05（feat-proto 件 5）：起它時生效的份額照帶（信箱接回只留名的列再起時用它）
        }
        if (phase == "stopped" || phase == "sleeping") {   // stopped 的列（11-03 procs § 2c 第 7 條）：接成 stopped、不起、不判活；名字進底的 stopped 集合
            if (c.auto_restart) {
                std::error_code ec;
                c.once = !std::filesystem::exists(aos::join(c.stack, names_.loop), ec);   // 常駐列也照小格有沒有 loop.json 判 exec／loop 型
            }
            c.phase = phase.get<std::string>();            // sleeping 的列（11-03 sleep／wake）：同樣接成列、不判活，但不進 stopped 集合＝reconcile 第一圈就 wake
            c.held = true;
            c.code = r.value("code", Json());
            c.signal = r.value("signal", Json());
            if (phase == "stopped") {
                stopped_.insert(name);
            }
            add(name, c);
            continue;
        }
        if (phase != "running" && phase != "stopping") {
            continue;
        }
        std::error_code ec;
        c.once = !std::filesystem::exists(aos::join(c.stack, names_.loop), ec);   // 小格有 daemon 寫的 loop.json（procs_loop 的名字）＝loop 型（procs § 2 第 7 條）
        Json pid = r.value("pid", Json());
        Json ticks = r.value("started_at_ticks", Json());
        std::optional<long long> now = same_boot && pid.is_number_integer() && ticks.is_number_integer() ? aos::proc_started_at_ticks((pid_t)pid.get<long long>()) : std::nullopt;
        if (now && *now == ticks.get<long long>()) {
            c.pid = (pid_t)pid.get<long long>();
            c.started_at_ticks = ticks.get<long long>();
            if (phase == "stopping") {
                // 11-05 第二輪：上一個 daemon 正在收它時被 kill -9（stop 在等它跑完、sleep／rm 送了 TERM、收工途中）。原本不接＝它照跑、表上看不到
                //（信加的從此消失；daemon.json 裡的在同一格再起一份）。改成接回來接著收：送 SIGTERM、10 秒 SIGKILL；退了＝上一個 daemon 在收工（state
                // phase stopping）的留 sleeping（下一圈 wake），其他留 stopped（看不出當初是 stop、sleep 還是 rm：一律停著、看得到，要的 start、不要的 rm）。
                if (finishing) {
                    c.nap = !c.once || c.auto_restart;
                } else if (!c.once || c.auto_restart) {
                    c.soft = true;
                    stopped_.insert(name);
                }
                term(c);
            }
            add(name, c);
            continue;
        }
        // 11-05 第二輪：行程不在了、上一個 daemon 沒來得及記（kill -9、斷電、wsl --shutdown、OOM）。原本整列悄悄丟掉（信加的從表上永久消失）。
        // loop 型改成：running 的照「收工時還在跑」接成 sleeping（下一圈 wake，同一個 stack 接著做）——子 loop 自己的 state 窗寫 done（自己跑完了）才照舊不接；
        // stopping 的（正在收）＝上一個 daemon 在收工就 sleeping，其他 stopped。exec 型（跑一次的）照舊不接。
        if (c.once && !c.auto_restart) {
            continue;
        }
        if (phase == "running" && !c.auto_restart) {
            std::optional<Json> cs = cell_state(c.stack, names_.loop);
            if (cs && cs->value(StateWindow::phase, Json()) == StateWindow::done) {
                continue;
            }
        }
        c.held = true;
        c.phase = phase == "running" || finishing ? "sleeping" : "stopped";
        if (c.phase == "stopped") {
            stopped_.insert(name);
        }
        add(name, c);
    }
}


}  // namespace aos::daemon
