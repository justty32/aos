// daemon.cpp：【daemon】Daemon（說明見 daemon.hpp）。照 proto8/bin/aos-daemon（10-21 傍晚）。
//
// 每次（Loop 讀完 ctl 之後的 tend）：期望表＝ctl 的 loops（有寫）或 daemon.json 的 loops →
//   表上多出來的送 SIGTERM（phase stopping）就往下走、不等；之後每次 tend 看一眼，退了標 stopped 並移除、滿 10 秒還在就
//   SIGKILL 整群（10-23 壓測後改：原本原地等滿 10 秒，那段 state 不寫、ctl 不讀、別的子 loop 沒人顧）→
//   看誰自己結束了（phase done，記 code／signal）→ 起表上少掉的（起之前先寫一份 state、起很久時每秒一份）。子 loop 結束後不自動重起（使用者 10-20「照預設」）：停在表上 done；要再起就從 loops 拿掉再放回。
// phase：running＝還在跑、stopping＝送了 SIGTERM 還沒退、done＝子 loop 自己結束、stopped＝daemon 收掉它（送了 SIGTERM／SIGKILL；
// 10-23 命名統合前兩個都叫 exited）。
// 不論為什麼結束都先 finish()（收掉全部子 loop），Loop 再寫好 state。
// adopt：起來時讀自己上次的 state，phase running、pid＋started_at_ticks 對得上的子 loop 直接放回表上、不重起（N-17）。
#include "daemon/daemon.hpp"

#include "aos/files.hpp"
#include "aos/proc.hpp"

#include <chrono>
#include <csignal>
#include <filesystem>
#include <limits>
#include <thread>
#include <unordered_set>

namespace aos::daemon {

using Clock = std::chrono::steady_clock;

static const int GRACE_MS = 10000;   // 收子 loop：SIGTERM 後等幾毫秒才 SIGKILL（P-36 daemon 的 grace 慣例 10000）

static aos::loop::Defaults daemon_defaults() {
    aos::loop::Defaults d;
    d.prog = "aos-daemon";
    d.max = std::nullopt;
    d.interval_ms = 200;
    d.need_run = false;
    return d;
}

std::optional<std::string> check_loops(const Json& v) {
    if (!v.is_object()) {
        return "loops 要是 {名字: loop 設定}";
    }
    for (auto& [name, c] : v.items()) {
        if (name.empty() || name.find('/') != std::string::npos || name.find('#') != std::string::npos || name[0] == '.') {
            return "loops 的名字 " + aos::dumps(Json(name)) + " 不能當資料夾名";
        }
        if (!c.is_string() && !c.is_array() && !c.is_object()) {
            return "loops[" + name + "] 要是 aos-exec 的目標或 loop 設定";
        }
    }
    return std::nullopt;
}

std::set<std::string> taken_names(const std::string& stack, const std::vector<std::string>& paths) {
    std::set<std::string> out;
    std::string base = aos::abspath(stack);
    std::string prefix = base;
    if (!prefix.ends_with('/')) {
        prefix += "/";
    }
    for (const std::string& p : paths) {
        if (p.empty()) {
            continue;   // 沒開
        }
        std::string a = aos::abspath(p);
        if (!a.starts_with(prefix) || a.size() == prefix.size()) {
            continue;   // 在 $AOS_STACK 外面（或就是它）不算
        }
        std::string rel = a.substr(prefix.size());
        out.insert(rel.substr(0, rel.find('/')));
    }
    return out;
}

std::optional<std::string> check_names(const Json& v, const std::set<std::string>& taken) {
    for (auto& [name, c] : v.items()) {
        if (taken.count(name) > 0) {
            return "loops 的名字 " + aos::dumps(Json(name)) + " 跟 daemon 自己的 ctl／state 撞名";
        }
    }
    return std::nullopt;
}

Daemon::Daemon(const std::map<std::string, std::string>& opts, const std::string& spec)
    : Loop(opts, spec, daemon_defaults()) {
    if (stack_.empty()) {
        throw Error{code::StackMissing, "沒設定 AOS_STACK"};
    }
    loops_ = Json::object();
    if (cfg_.contains("loops")) {
        loops_ = cfg_["loops"];
    }
    std::optional<std::string> bad = check_loops(loops_);
    if (bad) {
        throw Error{code::CfgBad, *bad};
    }
    taken_ = taken_names(stack_, {ctl_path_, state_path_});
    bad = check_names(loops_, taken_);
    if (bad) {
        throw Error{code::CfgBad, *bad};   // 使用者 10-22「子項名字擋掉跟 ctl／state 同名」
    }
    Json a = cfg_.value("adopt", Json(true));
    if (!a.is_boolean()) {
        throw Error{code::CfgBad, "adopt 要是 true／false"};
    }
    cwd_ = std::filesystem::current_path().string();
    if (a.get<bool>()) {
        adopt();
    }
}

void Daemon::adopt() {
    if (state_path_.empty()) {
        return;
    }
    std::optional<Json> old = aos::read_json(state_path_);
    if (!old || !old->is_object() || !old->contains("loops") || !(*old)["loops"].is_object()) {
        return;   // 第一次起來、或舊的讀不了：沒東西可接
    }
    const Json& rows = (*old)["loops"];
    for (auto& [name, r] : rows.items()) {
        if (!r.is_object()) {
            return;   // 同 bin 版：有一列壞就整份不接
        }
    }
    for (auto& [name, r] : rows.items()) {
        if (r.value("phase", Json()) != "running") {
            continue;
        }
        Json pid = r.value("pid", Json());
        Json st = r.value("started_at_ticks", Json());
        if (!pid.is_number_integer() || !st.is_number_integer()) {
            continue;
        }
        std::optional<long long> now = aos::proc_started_at_ticks((pid_t)pid.get<long long>());
        if (now && *now == st.get<long long>()) {
            Child c;
            c.pid = (pid_t)pid.get<long long>();
            c.started_at_ticks = st.get<long long>();
            c.own = false;
            add(name, c);
        }
    }
}

void Daemon::add(const std::string& name, const Child& c) {
    table_.push_back({name, c});
    index_[name] = std::prev(table_.end());
}

std::optional<std::string> Daemon::check_ctl(const Json& doc) {
    if (doc.contains("loops")) {   // ctl 改 loops 撞名＝整份不採用（N-08；原因進 ctl_warning）
        std::optional<std::string> bad = check_loops(doc["loops"]);
        if (bad) {
            return bad;
        }
        return check_names(doc["loops"], taken_);
    }
    return std::nullopt;
}

Json Daemon::info() {
    Json rows = Json::object();
    // ordered_json 的 rows[n] 每次都逐個比對 key（N 個就 N×N）；名字在表上本來就不重複，直接接在尾巴
    auto& vec = static_cast<std::vector<std::pair<const std::string, Json>>&>(rows.get_ref<Json::object_t&>());
    vec.reserve(table_.size());
    for (auto& [n, c] : table_) {
        vec.emplace_back(n, row(c));
    }
    Json out = Json::object();
    out["loops"] = std::move(rows);
    return out;
}

void Daemon::term(Child& c, bool removing) {
    c.phase = "stopping";
    c.removing = removing;
    c.deadline = Clock::now() + std::chrono::milliseconds(GRACE_MS);
    kill(c.pid, SIGTERM);   // 給那支子 loop（它自己轉給它的那次）；已經沒了就算了
}

bool Daemon::settle(Child& c) {
    if (!alive(c)) {
        c.phase = "stopped";   // daemon 收掉的
        return true;
    }
    if (!c.killed && Clock::now() >= c.deadline) {
        aos::signal_group(c.pid, SIGKILL);   // 整群：連孫程式一起收
        c.killed = true;
    }
    return false;
}

void Daemon::tend(const Json& ctl) {
    const Json& want = ctl.contains("loops") ? ctl["loops"] : loops_;
    std::unordered_set<std::string> wanted;   // want 是 ordered_json，contains 是逐個比對；先收成雜湊表
    wanted.reserve(want.size());
    for (auto& [n, spec] : want.items()) {
        wanted.insert(n);
    }
    for (auto it = table_.begin(); it != table_.end();) {
        auto& [n, c] = *it;
        if (c.phase == "running") {
            if (!alive(c)) {
                c.phase = "done";   // 子 loop 自己結束
            } else if (wanted.count(n) == 0) {
                term(c, true);      // 表上多出來的：送 SIGTERM 就往下走，不等（10-23 壓測後改）
            }
        } else if (c.phase == "stopping") {
            settle(c);
        }
        if (c.phase != "running" && c.phase != "stopping" && (c.removing || wanted.count(n) == 0)) {
            index_.erase(n);        // 收完了（或早就結束了）的多出來那列：拿掉（小格留著）
            it = table_.erase(it);
        } else {
            ++it;
        }
    }
    for (auto& [n, spec] : want.items()) {
        if (index_.count(n) == 0) {   // 收的途中（stopping）的同名項還在表上：等它退了、下一次才起新的
            beat();                   // 起一大批要好一陣子：起之前先寫一份、之後每秒一份（10-23 壓測後加）
            add(n, spawn(n, aos::join(stack_, n), spec, cwd_));
        }
    }
}

void Daemon::finish() {
    for (auto& [n, c] : table_) {
        if (c.phase == "running" && alive(c)) {
            term(c, false);
        }
    }
    while (true) {
        bool any = false;
        for (auto& [n, c] : table_) {
            if (c.phase == "stopping" && !settle(c)) {
                any = true;
            }
        }
        if (!any) {
            break;
        }
        try {
            beat("stopping");   // 等子項退的時候心跳照跳（N-17）；寫不了就算了，收子項要緊
        } catch (const Error&) {
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(50));
    }
    for (auto it = table_.begin(); it != table_.end();) {
        auto& [n, c] = *it;
        if (c.phase == "running" && !alive(c)) {
            c.phase = "done";   // 最後一次 tend 之後才自己結束的（沒送 SIGTERM）標 done、記 code（10-21 plan D7）
        }
        if (c.removing) {       // ctl 早就要拿掉、收工時才退的：照樣拿掉
            index_.erase(n);
            it = table_.erase(it);
        } else {
            ++it;
        }
    }
}

}  // namespace aos::daemon
