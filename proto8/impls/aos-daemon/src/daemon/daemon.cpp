// daemon.cpp：【daemon】Daemon（說明見 daemon.hpp）。照 proto8/bin/aos-daemon（10-21 傍晚）。
//
// 每拍（Loop 讀完 ctl 之後的 tend）：期望表＝ctl 的 loops（有寫）或 daemon.json 的 loops →
//   表上多出來的收掉（SIGTERM，等 10 秒，再 SIGKILL 整群；phase stopped）並移除 → 看誰自己結束了（phase done，記 code／signal）→
//   起表上少掉的。子 loop 結束後不自動重起（使用者 10-20「照預設」）：停在表上 done；要再起就從 loops 拿掉再放回。
// phase：running＝還在跑、done＝子 loop 自己結束、stopped＝daemon 收掉它（送了 SIGTERM／SIGKILL；10-23 命名統合前兩個都叫 exited）。
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

namespace aos::daemon {

using Clock = std::chrono::steady_clock;

static const int GRACE_MS = 10000;   // 收子 loop：SIGTERM 後等幾毫秒才 SIGKILL（P-36 daemon 的 grace 慣例 10000）

static aos::loop::Defaults daemon_defaults() {
    aos::loop::Defaults d;
    d.prog = "aos-daemon";
    d.max = std::nullopt;
    d.interval_ms = 200;
    d.need_val = false;
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
            table_.push_back({name, c});
        }
    }
}

Child* Daemon::find(const std::string& name) {
    for (auto& [n, c] : table_) {
        if (n == name) {
            return &c;
        }
    }
    return nullptr;
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
    for (auto& [n, c] : table_) {
        rows[n] = row(c);
    }
    Json out = Json::object();
    out["loops"] = rows;
    return out;
}

void Daemon::tend(const Json& ctl) {
    const Json& want = ctl.contains("loops") ? ctl["loops"] : loops_;
    std::vector<std::string> gone;
    for (auto& [n, c] : table_) {
        if (!want.contains(n)) {
            gone.push_back(n);
        }
    }
    stop(gone);
    for (const std::string& n : gone) {
        for (size_t i = 0; i < table_.size(); ++i) {
            if (table_[i].first == n) {
                table_.erase(table_.begin() + (long)i);
                break;
            }
        }
    }
    for (auto& [n, c] : table_) {
        if (c.phase == "running" && !alive(c)) {
            c.phase = "done";   // 子 loop 自己結束
        }
    }
    for (auto& [n, spec] : want.items()) {
        if (find(n) == nullptr) {
            table_.push_back({n, spawn(n, aos::join(stack_, n), spec, cwd_)});
        }
    }
}

void Daemon::stop(const std::vector<std::string>& names) {
    std::vector<Child*> live;
    for (const std::string& n : names) {
        Child* c = find(n);
        if (c != nullptr && c->phase == "running" && alive(*c)) {
            live.push_back(c);
        }
    }
    for (Child* c : live) {
        c->phase = "stopping";
        kill(c->pid, SIGTERM);   // 給那支子 loop（它自己轉給它的那拍）；已經沒了就算了
    }
    Clock::time_point deadline = Clock::now() + std::chrono::milliseconds(GRACE_MS);
    bool killed = false;
    while (true) {
        bool any = false;
        for (Child* c : live) {
            if (alive(*c)) {
                any = true;
            }
        }
        if (!any) {
            break;
        }
        if (!killed && Clock::now() >= deadline) {
            for (Child* c : live) {
                if (alive(*c)) {
                    aos::signal_group(c->pid, SIGKILL);   // 整群：連孫程式一起收
                }
            }
            killed = true;
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(50));
    }
    for (Child* c : live) {
        c->phase = "stopped";   // daemon 收掉的
    }
}

void Daemon::finish() {
    std::vector<std::string> all;
    for (auto& [n, c] : table_) {
        all.push_back(n);
    }
    stop(all);
    for (auto& [n, c] : table_) {   // 最後一次 tend 之後才自己結束的（stop 不收已經死的）標 done、記 code（10-21 plan D7）
        if (c.phase == "running" && !alive(c)) {
            c.phase = "done";
        }
    }
}

}  // namespace aos::daemon
