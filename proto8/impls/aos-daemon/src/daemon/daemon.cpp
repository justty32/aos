// daemon.cpp：【daemon】Daemon（說明見 daemon.hpp；10-21 傍晚）。
//
// 每次（Loop 讀完 ctl.json 之後的 tend）：先讀 loops_ctl.json（10-29 拆窗）；ctl 是 stopped／paused 就只看一眼（收已送 SIGTERM 的、記自己結束的），不調表。
// 不然期望表＝loops_ctl 的 loops（有寫）或 daemon.json 的 loops，加上 loops_ctl 的 loops_added、減掉 loops_removed（10-23 晚）→
//   表上多出來的送 SIGTERM（phase stopping）就往下走、不等；之後每次 tend 看一眼，退了標 stopped 並移除、滿 10 秒還在就
//   SIGKILL 整群——子 loop 那群，加上它底下自成一群的（inst 起的單子，leaders_below；10-24 審後補，原本打不到）（10-23 壓測後改：原本原地等滿 10 秒，那段 state 不寫、ctl 不讀、別的子 loop 沒人顧）→
//   看誰自己結束了（phase done，記 code／signal）→ 起表上少掉的（起之前先寫一份 state、起很久時每秒一份）。子 loop 結束後不自動重起（使用者 10-20「照預設」）：停在表上 done；要再起就從 loops 拿掉再放回。
// phase：running＝還在跑、stopping＝送了 SIGTERM 還沒退、done＝子 loop 自己結束、stopped＝daemon 收掉它（送了 SIGTERM／SIGKILL；
// 10-23 命名統合前兩個都叫 exited）。
// 不論為什麼結束都先 finish()（收掉全部子 loop），Loop 再寫好 state。
// 信箱模式（loops_mailbox，10-29）：期望表改成記憶體裡的 want_，每圈先 take_letters 套信、reconcile 對表、done_letters 回信收信（mailbox.cpp）。
// adopt：起來時讀自己上次的 loops_state（10-29 前是 state），phase running、pid＋started_at_ticks 對得上的子 loop 直接放回表上、不重起（N-17）。
#include "daemon/daemon.hpp"

#include "aos/files.hpp"
#include "aos/proc.hpp"

#include <chrono>
#include <cstdio>
#include <csignal>
#include <filesystem>
#include <limits>
#include <sstream>
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
    d.need_exec = false;
    return d;
}

// root 底下（子、孫…）自己當群組組長的行程：/proc 掃一遍（stat 第 4 欄 ppid、第 5 欄 pgrp）。SIGKILL 子 loop 時一起整群收（10-24 審後補）：
// 子 loop 跑的單子——內嵌的在子 loop 自己行程內 run_inst、字串目標的在它 fork 的 aos-exec 裡——由 inst 的 libaos 起、自成 session，
// 整群打子 loop 打不到；單子不理 SIGTERM、grace_ms 又比 10 秒長時，子 loop 被收掉後它會留成孤兒。掃完到送之間它結束了、
// pid 又剛好被別的組長拿走的機會跟 killpg 本身一樣小，不管。讀不到 /proc＝回空的（只收子 loop 那群，同以前）。
static std::vector<pid_t> leaders_below(pid_t root) {
    std::unordered_map<pid_t, std::vector<pid_t>> kids;
    std::unordered_map<pid_t, pid_t> pgrp;
    std::error_code ec;
    for (std::filesystem::directory_iterator it("/proc", ec), end; !ec && it != end; it.increment(ec)) {
        std::string n = it->path().filename().string();
        if (n.empty() || n.find_first_not_of("0123456789") != std::string::npos) {
            continue;
        }
        int err = 0;
        std::optional<std::string> text = aos::read_file("/proc/" + n + "/stat", err);
        size_t paren = text ? text->rfind(')') : std::string::npos;
        if (paren == std::string::npos) {
            continue;
        }
        std::istringstream rest(text->substr(paren + 1));   // 第 2 欄程式名可能有空白：從最後一個 ')' 之後數
        std::string state;
        long ppid = 0;
        long pg = 0;
        if (!(rest >> state >> ppid >> pg)) {
            continue;
        }
        pid_t pid = (pid_t)std::stol(n);
        kids[(pid_t)ppid].push_back(pid);
        pgrp[pid] = (pid_t)pg;
    }
    std::vector<pid_t> out;
    std::vector<pid_t> todo{root};
    while (!todo.empty()) {
        pid_t p = todo.back();
        todo.pop_back();
        for (pid_t k : kids[p]) {
            if (pgrp[k] == k) {
                out.push_back(k);
            }
            todo.push_back(k);
        }
    }
    return out;
}

static void check_name(const std::string& name) {
    if (name.empty() || name.find('/') != std::string::npos || name.find('#') != std::string::npos || name[0] == '.') {
        throw Error{code::CfgBad, "loops 的名字 " + aos::dumps(Json(name)) + " 不能當資料夾名"};
    }
}

Json abs_refs(const Json& v, const std::string& base) {
    if (v.is_array()) {
        Json out = Json::array();
        for (const Json& x : v) {
            out.push_back(abs_refs(x, base));
        }
        return out;
    }
    if (!v.is_object()) {
        return v;
    }
    Json out = v;
    if (v.contains("$ref")) {   // 指示詞：只動 $ref 的檔名（其他 key 指示詞不看，不往裡面走）
        auto fix = [&](Json& s) {
            if (!s.is_string()) {
                return;
            }
            std::string r = s.get<std::string>();
            size_t hash = r.find('#');
            std::string file = r.substr(0, hash);
            if (!file.empty() && file[0] != '/') {
                s = aos::join(base, file) + (hash == std::string::npos ? "" : r.substr(hash));
            }
        };
        Json& ref = out["$ref"];
        if (ref.is_array()) {
            for (Json& s : ref) {
                fix(s);
            }
        } else {
            fix(ref);
        }
        return out;
    }
    for (auto& [k, x] : out.items()) {
        x = abs_refs(x, base);
    }
    return out;
}

Json read_loops(const Json& v, const std::string& base, const std::string& key) {
    aos::Resolved top = aos::resolve_shallow(v, base);   // 拆成好幾份檔＝{"$ref": [檔, …]}，合好的每個子項記著它來自哪份檔
    if (!top.value.is_object()) {
        throw Error{code::CfgBad, key + " 要是 {名字: loop 設定}"};
    }
    Json out = Json::object();   // 名字本來就不重複（JSON 物件；$ref 陣列合的同名後面的蓋前面的），直接接在尾巴
    auto& vec = static_cast<std::vector<std::pair<const std::string, Json>>&>(out.get_ref<Json::object_t&>());
    vec.reserve(top.value.size());
    for (auto& [name, c] : top.value.items()) {
        check_name(name);
        aos::Resolved it = aos::resolve_shallow(c, top.dir_of(name));
        if (it.value.is_string() || it.value.is_array()) {
            vec.emplace_back(name, aos::resolve(it.value, it.base_dir));
        } else if (it.value.is_object()) {
            aos::Resolved r = aos::loop::resolve_keys(it.value, it.base_dir, {"max", "interval_ms", "ctl", "state"});
            if (r.value.is_object() && r.value.contains("exec")) {   // exec 是單子時裡面不解、相對 $ref 轉成絕對（10-24）
                aos::Resolved ex = aos::loop::resolve_exec(r.value["exec"], r.dir_of("exec"));
                if (ex.value.is_object()) {
                    ex.value = abs_refs(ex.value, ex.base_dir);
                }
                r.value["exec"] = std::move(ex.value);
            }
            vec.emplace_back(name, std::move(r.value));
        } else {
            throw Error{code::CfgBad, key + "[" + name + "] 要是 aos-exec 的目標或 loop 設定"};
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
            return "loops 的名字 " + aos::dumps(Json(name)) + " 跟 daemon 自己的 ctl／state／loops_ctl／loops_state／loops_mailbox 撞名";
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
    try {   // 指示詞（10-23 晚）：起點＝設定檔的資料夾（cfg_dirs_）
        if (cfg_.contains("loops")) {
            loops_ = read_loops(cfg_["loops"], cfg_dirs_.dir_of("loops"), "loops");
        }
        for (const char* k : {"adopt", "loops_ctl", "loops_state", "loops_mailbox"}) {
            if (cfg_.contains(k)) {
                cfg_[k] = aos::resolve(cfg_[k], cfg_dirs_.dir_of(k));
            }
        }
    } catch (const Error& e) {
        if (e.code == code::DirectiveBad) {
            throw Error{e.code, "設定檔 " + spec + " 的指示詞解不開：" + e.msg};
        }
        throw;
    }
    // 信箱模式（10-29 medium-plan § 四 3）：loops_mailbox 寫了（非 null）＝信箱模式、loops_ctl 不開；loops_ctl 也明寫了（非 null）＝CfgBad
    Json mb = cfg_.value("loops_mailbox", Json());
    if (!mb.is_null()) {
        if (!mb.is_string() || mb.get<std::string>().empty()) {
            throw Error{code::CfgBad, "loops_mailbox 要是信箱的路徑或 null"};
        }
        if (cfg_.contains("loops_ctl") && !cfg_["loops_ctl"].is_null()) {
            throw Error{code::CfgBad, "loops_ctl 與 loops_mailbox 只能寫一個（信箱模式不開 loops_ctl）"};
        }
        mbox_path_ = aos::join(stack_, mb.get<std::string>());
    }
    // 管轄那一對窗（10-29 拆窗）：沒寫＝預設檔名、null＝不開；路徑同 ctl／state 接在 $AOS_STACK 後面
    std::pair<const char*, std::string*> wins[2] = {{"loops_ctl", &lctl_path_}, {"loops_state", &lstate_path_}};
    for (auto& [k, path] : wins) {
        if (!mbox_path_.empty() && path == &lctl_path_) {
            continue;   // 信箱模式：loops_ctl 沒寫（走預設）也不開
        }
        Json v = cfg_.contains(k) ? cfg_[k] : Json(std::string(k) + ".json");
        if (v.is_null()) {
            continue;
        }
        if (!v.is_string() || v.get<std::string>().empty()) {
            throw Error{code::CfgBad, std::string(k) + " 要是檔名或 null"};
        }
        *path = aos::join(stack_, v.get<std::string>());
    }
    if (!lstate_path_.empty()) {   // 分檔的資料夾：loops_state 檔名去掉副檔名＋_loops，跟它同一層（10-23 晚；10-29 起跟著 loops_state）
        std::string name = lstate_path_.substr(lstate_path_.rfind('/') + 1);
        size_t dot = name.rfind('.');
        if (dot != std::string::npos && dot > 0) {
            name = name.substr(0, dot);
        }
        parts_dir_ = aos::join(aos::dirname(lstate_path_), name + "_loops");
    }
    taken_ = taken_names(stack_, {ctl_path_, state_path_, lctl_path_, lstate_path_, parts_dir_, mbox_path_});
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
    if (!mbox_path_.empty()) {
        open_mailbox();
    }
}

void Daemon::adopt() {
    if (lstate_path_.empty()) {
        return;
    }
    std::optional<Json> old = aos::read_json(lstate_path_);
    if (!old || !old->is_object() || !old->contains("loops")) {
        return;   // 第一次起來、或舊的讀不了：沒東西可接
    }
    Json rows;
    try {   // 切檔（10-23）：loops 是 {"$ref": [分檔, …]}，用 aos-directive 解開就是合好的表；分檔讀不到＝舊的讀不了
        rows = aos::resolve((*old)["loops"], aos::dirname(lstate_path_));
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

std::optional<std::string> Daemon::check_ctl(Json& doc, const aos::Resolved&) {
    // ctl.json 只管 loop 面向（10-29 拆窗）：loops*（10-29 前寫在這裡的名單）不採用，其他 key 照採。
    // 過渡期（衝突 5，使用者 10-29「都照建議」）：寫了就在 state 的 ctl_warning 提醒一句；之後會拿掉這段、回到不認得的 key 一律忽略（C-48）。
    bool moved = false;
    for (const char* k : {"loops", "loops_added", "loops_removed"}) {
        if (doc.contains(k)) {
            doc.erase(k);
            moved = true;
        }
    }
    if (moved) {
        ctl_note_ = "ctl 的 loops／loops_added／loops_removed 已搬到 loops_ctl.json（ctl 裡的不採用）";
    }
    return std::nullopt;
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
        std::vector<pid_t> below = leaders_below(c.pid);   // 先掃：子 loop 一死，底下自成 session 的單子就認不出是誰的了
        aos::signal_group(c.pid, SIGKILL);   // 整群：子 loop 與它同群的孫程式
        for (pid_t g : below) {
            aos::signal_group(g, SIGKILL);   // 底下自成一群的（inst 起的單子，連它的子孫）
        }
        c.killed = true;
    }
    return false;
}

void Daemon::tend(const Json& loop_ctl) {
    read_loops_ctl();   // 每圈先讀 ctl.json（Loop）、再讀 loops_ctl.json；停著、暫停也照讀
    if (loop_ctl.value("stopped", false) || loop_ctl.value("paused", false)) {
        // 這圈收工／整圈暫停（10-29 medium-plan § 四 2）：不調表，只看一眼——自己結束的記 done、收的途中的照收、早就要拿掉的收完拿掉
        for (auto it = table_.begin(); it != table_.end();) {
            auto& [n, c] = *it;
            if (c.phase == "running" && !alive(c)) {
                c.phase = "done";
            } else if (c.phase == "stopping") {
                settle(c);
            }
            if (c.phase != "running" && c.phase != "stopping" && c.removing) {
                index_.erase(n);
                it = table_.erase(it);
            } else {
                ++it;
            }
        }
        return;
    }
    if (mbox_path_.empty()) {
        Json merged;
        reconcile(ctl_want(merged));
        return;
    }
    Letters got = take_letters();   // 信箱模式：全部認領、照順序套進 want_，套完才對一次表、再回信收信
    reconcile(want_);
    done_letters(got);
}

const Json& Daemon::ctl_want(Json& merged) {
    const Json& ctl = lctl_good_;
    // 期望表（N-06：整份 loops_ctl 就是期望，沒寫的回 daemon.json）＝（loops_ctl 的 loops，沒寫＝daemon.json 的）＋loops_added－loops_removed（10-23 晚）
    const Json* base = ctl.contains("loops") ? &ctl["loops"] : &loops_;
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
    return *base;
}

void Daemon::reconcile(const Json& want) {
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
        if (index_.count(n) == 0 && !spec.is_null()) {   // null＝信箱模式接回的（只留名、沒有設定），不會起；收的途中（stopping）的同名項還在表上：等它退了、下一次才起新的
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
        if (c.removing) {       // loops_ctl 早就要拿掉、收工時才退的：照樣拿掉
            index_.erase(n);
            it = table_.erase(it);
        } else {
            ++it;
        }
    }
}

}  // namespace aos::daemon
