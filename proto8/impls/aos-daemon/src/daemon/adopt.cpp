// adopt.cpp：【daemon】按保存的入口與控制意圖接回 proc 表，不以小格檔案分類（說明見 daemon.hpp）。
#include "daemon/daemon.hpp"
#include "aos/util/files.hpp"
#include "aos/util/proc.hpp"

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
    // 11-06 晚（no-pid P9 06-13）：子 state 的 boot_id 跟這次開機不同＝那支已不在（重開機後 pid＋ticks 可能撞號）；這台讀不到 boot_id 或子沒寫＝照舊只比 pid＋ticks。
    std::optional<std::string> boot = aos::boot_id();
    Json sboot = st->value(StateWindow::boot_id, Json());
    if (boot && sboot.is_string() && sboot.get<std::string>() != *boot) {
        return std::nullopt;
    }
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
    // 上一個 daemon 收工時還記為 running 的列要睡下；stopping 的列只看自己的 stop_mode。
    std::optional<Json> me = state_path_.empty() ? std::nullopt : aos::read_json(state_path_);
    bool finishing = me && me->is_object() && me->value("phase", Json()) == "stopping";
    // 11-06（no-pid P1）：表頂層的 boot_id 跟這次開機不同（或沒寫）＝表上的行程都不在了（重開機後 pid＋ticks 可能撞上別的行程）；這台讀不到 boot_id＝照舊只比 pid＋ticks
    std::optional<std::string> boot = aos::boot_id();
    bool same_boot = !boot || old->value("boot_id", Json()) == Json(*boot);
    for (auto& [name, r] : table.items()) {
        Json phase = r.value("phase", Json());
        if (phase == "stuck") {
            phase = "running";
        }
        Json st = r.value("stack", Json());
        Child c;
        c.launch = r.value("launch", Json());
        if (c.launch.is_object()) {
            Json target = c.launch.value("exec", Json());
            if (target.is_string()) {
                c.launch["exec"] = unrel(target);
            } else if (target.is_array() && !target.empty()) {
                c.launch["exec"][0] = unrel(target[0]);
            }
            for (const char* key : {"ws", "stack", "def"}) {
                if (c.launch.contains(key)) {
                    c.launch[key] = unrel(c.launch[key]);
                }
            }
            c.launch = abs_refs(c.launch, dstack_);
        }
        c.own = false;
        c.auto_restart = auto_restart_of(r);
        c.restart_on_stuck = ros_of(r);
        Json threshold = r.value("stuck_after_cycles", Json(10));
        if (aos::is_count(threshold) && threshold.get<long long>() > 0) {
            c.stuck_after_cycles = threshold.get<long long>();
        }
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
        if (phase != "running" && r.value("reason", Json()).is_string()) {
            c.reason = r["reason"];   // 11-05：stopped 的原因照帶
        }
        if (r.value("limits", Json()).is_object()) {
            c.limits = r["limits"];   // 11-05（feat-proto 件 5）：起它時生效的份額照帶（信箱接回只留名的列再起時用它）
        }
        if (phase == "stopped" || phase == "sleeping") {   // stopped 的列（11-03 procs § 2c 第 7 條）：接成 stopped、不起、不判活；名字進底的 stopped 集合
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
        Json pid = r.value("pid", Json());
        Json ticks = r.value("started_at_ticks", Json());
        std::optional<long long> now = same_boot && pid.is_number_integer() && ticks.is_number_integer() ? aos::proc_started_at_ticks((pid_t)pid.get<long long>()) : std::nullopt;
        if (now && *now == ticks.get<long long>()) {
            c.pid = (pid_t)pid.get<long long>();
            c.started_at_ticks = ticks.get<long long>();
            if (phase == "stopping") {
                // 接回收的途中仍照公開 stop_mode；stop 不會因 daemon 重開而改送訊號。
                std::string mode = r.value("stop_mode", std::string("stop"));
                if (mode == "sleep") {
                    c.nap = true;
                    term(c);
                } else if (mode == "stop") {
                    c.soft = true;
                    stopped_.insert(name);
                    halt(name, c);
                } else {
                    term(c);
                }
            }
            add(name, c);
            continue;
        }
        // 拿不到結束碼的自然結束照舊下表；auto_restart 仍重起，收途中保留原意。
        if (phase == "running" && !c.auto_restart && !finishing) {
            continue;
        }
        std::string mode = r.value("stop_mode", std::string("stop"));
        if (phase == "stopping" && mode == "remove") {
            continue;
        }
        c.held = true;
        c.phase = phase == "running" || mode == "sleep" ? "sleeping" : "stopped";
        if (c.phase == "stopped") {
            stopped_.insert(name);
        }
        add(name, c);
    }
}


}  // namespace aos::daemon
