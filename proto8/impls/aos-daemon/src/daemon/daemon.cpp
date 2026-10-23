// daemon.cpp：【daemon】Daemon（說明見 daemon.hpp；10-21 傍晚）。
//
// 每次（Loop 讀完 ctl 之後的 tend）：期望表＝ctl 的 loops（有寫）或 daemon.json 的 loops，加上 ctl 的 loops_added、減掉 loops_removed（10-23 晚）→
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
#include <cstdio>
#include <csignal>
#include <filesystem>
#include <limits>
#include <thread>
#include <unordered_map>
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

static void check_name(const std::string& name) {
    if (name.empty() || name.find('/') != std::string::npos || name.find('#') != std::string::npos || name[0] == '.') {
        throw Error{code::CfgBad, "loops 的名字 " + aos::dumps(Json(name)) + " 不能當資料夾名"};
    }
}

Json read_loops(const Json& v, const std::string& base, const std::string& key) {
    aos::Resolved top = aos::resolve_shallow(v, base);
    std::vector<aos::Resolved> pages;
    if (top.value.is_object()) {
        pages.push_back(top);
    } else if (top.value.is_array()) {
        for (const Json& p : top.value) {
            aos::Resolved page = aos::resolve_shallow(p, top.base_dir);
            if (!page.value.is_object()) {
                throw Error{code::CfgBad, key + " 寫成陣列時每一份要是 {名字: loop 設定}"};
            }
            pages.push_back(page);
        }
    } else {
        throw Error{code::CfgBad, key + " 要是 {名字: loop 設定}（或它的陣列）"};
    }
    Json out = Json::object();   // 名字查重用雜湊表、直接接在尾巴（ordered_json 的 []、contains 逐個比對，N 個就 N×N）
    auto& vec = static_cast<std::vector<std::pair<const std::string, Json>>&>(out.get_ref<Json::object_t&>());
    std::unordered_set<std::string> seen;
    for (const aos::Resolved& page : pages) {
        for (auto& [name, c] : page.value.items()) {
            check_name(name);
            if (!seen.insert(name).second) {
                throw Error{code::CfgBad, key + " 的名字 " + aos::dumps(Json(name)) + " 重複"};
            }
            aos::Resolved it = aos::resolve_shallow(c, page.base_dir);
            if (it.value.is_string() || it.value.is_array()) {
                vec.emplace_back(name, aos::resolve(it.value, it.base_dir));
            } else if (it.value.is_object()) {
                vec.emplace_back(name, aos::loop::resolve_keys(it.value, it.base_dir, {"run", "max", "interval_ms", "ctl", "state"}).value);
            } else {
                throw Error{code::CfgBad, key + "[" + name + "] 要是 aos-exec 的目標或 loop 設定"};
            }
        }
    }
    return out;
}

Json merge_rows(const Json& v) {
    if (v.is_object()) {
        return v;
    }
    if (!v.is_array()) {
        return Json();
    }
    Json out = Json::object();   // daemon 自己寫的分頁名字不重複，直接接在尾巴
    auto& vec = static_cast<std::vector<std::pair<const std::string, Json>>&>(out.get_ref<Json::object_t&>());
    for (const Json& p : v) {
        if (!p.is_object()) {
            return Json();
        }
        for (auto& [n, r] : p.items()) {
            vec.emplace_back(n, r);
        }
    }
    return out;
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
    try {   // 指示詞（10-23 晚）：起點＝設定檔的資料夾（cfg_base_）
        if (cfg_.contains("loops")) {
            loops_ = read_loops(cfg_["loops"], cfg_base_, "loops");
        }
        if (cfg_.contains("adopt")) {
            cfg_["adopt"] = aos::resolve(cfg_["adopt"], cfg_base_);
        }
    } catch (const Error& e) {
        if (e.code == code::DirectiveBad) {
            throw Error{e.code, "設定檔 " + spec + " 的指示詞解不開：" + e.msg};
        }
        throw;
    }
    if (!state_path_.empty()) {   // state 分頁的資料夾：state 檔名去掉副檔名＋_loops，跟 state 同一層（10-23 晚）
        std::string name = state_path_.substr(state_path_.rfind('/') + 1);
        size_t dot = name.rfind('.');
        if (dot != std::string::npos && dot > 0) {
            name = name.substr(0, dot);
        }
        parts_dir_ = aos::join(aos::dirname(state_path_), name + "_loops");
    }
    taken_ = taken_names(stack_, {ctl_path_, state_path_, parts_dir_});
    std::optional<std::string> bad = check_names(loops_, taken_);
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
    if (!old || !old->is_object() || !old->contains("loops")) {
        return;   // 第一次起來、或舊的讀不了：沒東西可接
    }
    Json rows;
    try {   // 分頁（10-23 晚）：loops 是 $ref 的陣列，解開再合起來；分頁讀不到＝舊的讀不了
        rows = merge_rows(aos::resolve((*old)["loops"], aos::dirname(state_path_)));
    } catch (const Error&) {
        return;
    }
    if (!rows.is_object()) {
        return;
    }
    for (auto& [name, r] : rows.items()) {
        if (!r.is_object()) {
            return;   // 有一列壞就整份不接
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

std::optional<std::string> Daemon::check_ctl(Json& doc, const std::string& base) {
    // ctl 改名單撞名、寫壞＝整份不採用（N-08；原因進 ctl_warning）。指示詞解不開丟 DirectiveBad，Loop 一樣當不採用。
    const char* lists[2] = {"loops", "loops_added"};
    for (const char* k : lists) {
        if (!doc.contains(k)) {
            continue;
        }
        try {
            doc[k] = read_loops(doc[k], base, k);
        } catch (const Error& e) {
            if (e.code == code::DirectiveBad) {
                throw;
            }
            return e.msg;
        }
        std::optional<std::string> bad = check_names(doc[k], taken_);
        if (bad) {
            return bad;
        }
    }
    if (doc.contains("loops_removed")) {
        Json rm = aos::resolve(doc["loops_removed"], base);
        bool ok = rm.is_array();
        for (const Json& n : rm) {
            ok = ok && n.is_string();
        }
        if (!ok) {
            return std::string("loops_removed 要是名字（字串）的陣列");
        }
        doc["loops_removed"] = rm;
    }
    return std::nullopt;
}

static const size_t PART_ROWS = 100;   // state 的 loops 表一份最多幾列（使用者 10-23「每個檔案一百個」；不開 key，C-56）

// FNV-1a 64 位元，16 個十六進位字：分頁檔名＝內容的雜湊（內容不變就沿用同一份、不重寫）。
static std::string fnv64(const std::string& text) {
    unsigned long long h = 1469598103934665603ULL;
    for (unsigned char c : text) {
        h ^= c;
        h *= 1099511628211ULL;
    }
    char buf[17];
    std::snprintf(buf, sizeof buf, "%016llx", h);
    return buf;
}

Json Daemon::write_parts(Json rows) {
    std::set<std::string> now;
    Json out;
    if (rows.size() > PART_ROWS) {
        std::error_code ec;
        std::filesystem::create_directories(parts_dir_, ec);
        if (ec) {
            throw Error{code::WriteFailed, "寫不了 " + parts_dir_ + "（" + ec.message() + "）"};
        }
        std::string rel = parts_dir_.substr(parts_dir_.rfind('/') + 1);
        out = Json::array();
        Json page = Json::object();
        auto* vec = &static_cast<std::vector<std::pair<const std::string, Json>>&>(page.get_ref<Json::object_t&>());
        size_t i = 0;
        for (auto& [n, r] : rows.items()) {
            vec->emplace_back(n, r);   // 名字本來就不重複，直接接在尾巴（同 info）
            i += 1;
            if (page.size() == PART_ROWS || i == rows.size()) {
                std::string name = fnv64(aos::dumps(page)) + ".json";
                std::string path = aos::join(parts_dir_, name);
                if (!std::filesystem::exists(path, ec)) {   // 同名＝同內容（先寫 .名字 再改名，所以在就是完整的）
                    aos::loop::write_window(path, page);
                }
                now.insert(name);
                out.push_back(Json::object({{"$ref", rel + "/" + name}}));
                page = Json::object();
                vec = &static_cast<std::vector<std::pair<const std::string, Json>>&>(page.get_ref<Json::object_t&>());
            }
        }
    }
    // 清舊分頁：留這次與上一次的（磁碟上的主檔現在還指著上一次的）；這個行程第一次寫時不清（上一個行程的主檔可能還指著）。
    if (parts_wrote_ && !parts_dir_.empty()) {
        std::error_code ec;
        std::vector<std::filesystem::path> old;
        for (const auto& e : std::filesystem::directory_iterator(parts_dir_, ec)) {
            std::string f = e.path().filename().string();
            if (now.count(f) == 0 && parts_prev_.count(f) == 0) {
                old.push_back(e.path());
            }
        }
        for (const auto& f : old) {
            std::filesystem::remove(f, ec);
        }
        if (now.empty() && parts_prev_.empty()) {
            std::filesystem::remove(parts_dir_, ec);   // 空了就拿掉（不空就留著，remove 失敗不管）
        }
    }
    parts_prev_ = now;
    parts_wrote_ = true;
    if (out.is_null()) {
        return rows;   // 沒超過：原樣
    }
    return out;
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
    out["loops"] = write_parts(std::move(rows));
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
    // 期望表（N-06：整份 ctl 就是期望，沒寫的回 daemon.json）＝（ctl 的 loops，沒寫＝daemon.json 的）＋loops_added－loops_removed（10-23 晚）
    const Json* base = ctl.contains("loops") ? &ctl["loops"] : &loops_;
    Json merged;
    if (ctl.contains("loops_added") || ctl.contains("loops_removed")) {
        std::unordered_map<std::string, const Json*> added;
        if (ctl.contains("loops_added")) {
            for (auto& [n, spec] : ctl["loops_added"].items()) {
                added[n] = &spec;
            }
        }
        std::unordered_set<std::string> removed;
        if (ctl.contains("loops_removed")) {
            for (const Json& n : ctl["loops_removed"]) {
                removed.insert(n.get<std::string>());
            }
        }
        merged = Json::object();   // 名字不重複，直接接在尾巴（ordered_json 的 [] 逐個比對，N 個就 N×N）
        auto& vec = static_cast<std::vector<std::pair<const std::string, Json>>&>(merged.get_ref<Json::object_t&>());
        for (auto& [n, spec] : base->items()) {
            if (removed.count(n) == 0) {   // 先加後減：同一個名字兩邊都寫＝不要
                auto a = added.find(n);    // 已在名單上的：設定換成 loops_added 的（已在跑的不看設定變了沒，同 N-54）
                vec.emplace_back(n, a == added.end() ? spec : *a->second);
                if (a != added.end()) {
                    added.erase(a);
                }
            }
        }
        if (ctl.contains("loops_added")) {
            for (auto& [n, spec] : ctl["loops_added"].items()) {
                if (added.count(n) > 0 && removed.count(n) == 0) {   // 名單上本來沒有的：接在後面
                    vec.emplace_back(n, spec);
                }
            }
        }
        base = &merged;
    }
    const Json& want = *base;
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
