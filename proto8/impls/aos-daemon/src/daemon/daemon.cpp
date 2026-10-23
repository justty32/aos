// daemon.cpp：【daemon】Daemon（說明見 daemon.hpp）。照 proto8/bin/aos-daemon（10-21 傍晚）。
//
// 每圈（Loop 讀完 ctl 之後的 tend）：期望表＝ctl 的 children（有寫）或 daemon.json 的 children →
//   表上多出來的收掉（SIGTERM，等 10 秒，再 SIGKILL 整群）並移除 → 看誰結束了（phase exited，記 code／signal）→
//   起表上少掉的。子 loop 結束後不自動重起（使用者 10-20「照預設」）：停在表上 exited；要再起就從 children 拿掉再放回。
// 不論為什麼結束都先 finish()（收掉全部子 loop），Loop 再寫好 state。
// adopt：起來時讀自己上次的 state，phase running、pid＋啟動時間對得上的子 loop 直接放回表上、不重起（N-17）。
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
    d.need_run = false;
    return d;
}

std::optional<std::string> check_children(const Json& v) {
    if (!v.is_object()) {
        return "children 要是 {名字: loop 設定}";
    }
    for (auto& [name, c] : v.items()) {
        if (name.empty() || name.find('/') != std::string::npos || name.find('#') != std::string::npos || name[0] == '.') {
            return "children 的名字 " + aos::dumps(Json(name)) + " 不能當資料夾名";
        }
        if (!c.is_string() && !c.is_array() && !c.is_object()) {
            return "children[" + name + "] 要是 aos-exec 的目標或 loop 設定";
        }
    }
    return std::nullopt;
}

Daemon::Daemon(const std::map<std::string, std::string>& opts, const std::string& spec)
    : Loop(opts, spec, daemon_defaults()) {
    if (stack_.empty()) {
        throw Error{code::StackMissing, "沒設定 AOS_STACK"};
    }
    children_ = Json::object();
    if (cfg_.contains("children")) {
        children_ = cfg_["children"];
    }
    std::optional<std::string> bad = check_children(children_);
    if (bad) {
        throw Error{code::FieldType, *bad};
    }
    Json a = cfg_.value("adopt", Json(true));
    if (!a.is_boolean()) {
        throw Error{code::FieldType, "adopt 要是 true／false"};
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
    if (!old || !old->is_object() || !old->contains("children") || !(*old)["children"].is_object()) {
        return;   // 第一次起來、或舊的讀不了：沒東西可接
    }
    const Json& rows = (*old)["children"];
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
        Json st = r.value("started", Json());
        if (!pid.is_number_integer() || !st.is_number_integer()) {
            continue;
        }
        std::optional<long long> now = aos::proc_started((pid_t)pid.get<long long>());
        if (now && *now == st.get<long long>()) {
            Child c;
            c.pid = (pid_t)pid.get<long long>();
            c.started = st.get<long long>();
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
    if (doc.contains("children")) {
        return check_children(doc["children"]);
    }
    return std::nullopt;
}

Json Daemon::info() {
    Json rows = Json::object();
    for (auto& [n, c] : table_) {
        rows[n] = row(c);
    }
    Json out = Json::object();
    out["children"] = rows;
    return out;
}

void Daemon::tend(const Json& ctl) {
    const Json& want = ctl.contains("children") ? ctl["children"] : children_;
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
            c.phase = "exited";
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
        c->phase = "exited";
    }
}

void Daemon::finish() {
    std::vector<std::string> all;
    for (auto& [n, c] : table_) {
        all.push_back(n);
    }
    stop(all);
    for (auto& [n, c] : table_) {   // 最後一次 tend 之後才結束的（stop 不收已經死的）也標 exited、記 code（10-21 plan D7）
        if (c.phase == "running" && !alive(c)) {
            c.phase = "exited";
        }
    }
}

}  // namespace aos::daemon
