// daemon.cpp：【daemon】Daemon（說明見 daemon.hpp；10-21 傍晚）。
//
// 每次（Loop 讀完 ctl.json 之後的 tend）：先讀 loops_ctl.json（10-29 拆窗）；ctl 是 stopped／paused 就只看一眼（收已送 SIGTERM 的、記自己結束的），不調表。
// 不然期望表＝loops_ctl 的 loops（有寫）或 daemon.json 的 loops，加上 loops_ctl 的 loops_added、減掉 loops_removed（10-23 晚）→
//   表上多出來的送 SIGTERM（phase stopping）就往下走、不等；之後每次 tend 看一眼，退了標 stopped（印 log）並移除、滿 10 秒還在就
//   SIGKILL 整群——子 loop 那群，加上它底下自成一群的（inst 起的單子，leaders_below；10-24 審後補，原本打不到）（10-23 壓測後改：原本原地等滿 10 秒，那段 state 不寫、ctl 不讀、別的子 loop 沒人顧）→
//   看誰自己結束了（phase done，記 code／signal，印 log、從表上拿掉）→ 起表上少掉的（每起一個印 log、寫一次 loops_state，有變才寫）。
//   子 loop 結束後不自動重起（使用者 10-20「照預設」）；11-02 起也不留在表上（「改成子項結束後不留名單」）：本次執行不再起它
//   （ctl 模式記進 ended_、信箱模式從 want_ 拿掉；規則見 daemon.hpp），要再起：ctl 模式從名單拿掉（daemon 看過一圈）再放回，信箱模式再寄一封 *_added。
// phase：running＝還在跑、stopping＝送了 SIGTERM 還沒退、done＝子 loop 自己結束、stopped＝daemon 收掉它（送了 SIGTERM／SIGKILL；
// 10-23 命名統合前兩個都叫 exited）。done／stopped 11-02 起只出現在 log 那一行（loops_state 上看不到：印完就拿掉）。
// 不論為什麼結束都先 finish()（收掉全部子 loop），Loop 再寫好 state。
// 信箱（loops_ctl_mailbox，10-29；11-02 晚改名、跟 loops_ctl 共存）：底 want_ 在記憶體裡，每圈先 take_letters 套信、再疊 loops_ctl、reconcile 對表、done_letters 回信收信（mailbox.cpp）。
// adopt：起來時讀自己上次的 loops_state（10-29 前是 state），phase running、pid＋started_at_ticks 對得上的子 loop 直接放回表上、不重起（N-17）。
// execs（10-30）：exec 型子項跟子 loop 同一張表（Child::once）、同一套對表與收法（SIGTERM 直接打那支程式、10 秒 SIGKILL 整群），
// 只是起的時候 spawn_exec；期望表兩份（loops、execs），loops_state 寫成兩張表、adopt 兩張都接。
// ws（eca 10-30，thinking 2026-10-30-eca 衝突 1、N-28／N-54 補草稿）：loops、execs 的子項物件多認一個選填 ws（工作區）——read_loops 解指示詞、
// 從 daemon 的 cwd 轉絕對、留在期望表的子項上；起的時候子行程設 AOS_WS（child.cpp）。execs 物件「只看 exec、其他 key 忽略」的第一個例外。
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

// 子項物件的 ws（eca 10-30）：要是非空字串（null＝當沒寫、拿掉），相對路徑從 daemon 的 cwd 轉絕對（abspath 從行程的 cwd 算；
// daemon 自己不 cd，所以就是 daemon 的 cwd——信、loops_ctl、daemon.json 裡寫的都一樣，同相對 exec）。不驗在不在（aos-exec 會報 WsMissing，寫在小格 stderr.txt）。
static void fix_ws(Json& c, const std::string& name, const std::string& key) {
    if (!c.contains("ws")) {
        return;
    }
    const Json& w = c["ws"];
    if (w.is_null()) {
        c.erase("ws");
        return;
    }
    if (!w.is_string() || w.get<std::string>().empty()) {
        throw Error{code::CfgBad, key + "[" + name + "].ws 要是工作區的路徑（非空字串）"};
    }
    c["ws"] = aos::abspath(w.get<std::string>());
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
            aos::Resolved r = aos::loop::resolve_keys(it.value, it.base_dir, {"max", "interval_ms", "ctl", "state", "ws"});
            if (r.value.is_object() && r.value.contains("exec")) {   // exec 是單子時裡面不解、相對 $ref 轉成絕對（10-24）
                aos::Resolved ex = aos::loop::resolve_exec(r.value["exec"], r.dir_of("exec"));
                if (ex.value.is_object()) {
                    ex.value = abs_refs(ex.value, ex.base_dir);
                }
                r.value["exec"] = std::move(ex.value);
            }
            if (r.value.is_object()) {
                fix_ws(r.value, name, key);   // eca 10-30：子項的工作區
            }
            vec.emplace_back(name, std::move(r.value));
        } else {
            throw Error{code::CfgBad, key + "[" + name + "] 要是 aos-exec 的目標或 loop 設定"};
        }
    }
    return out;
}

Json read_execs(const Json& v, const std::string& base, const std::string& key) {
    Json out = read_loops(v, base, key);   // 名字規則、指示詞同 loops（物件的 exec 已整個解；是單子就只換了一層、相對 $ref 轉成絕對）
    for (auto& [name, c] : out.items()) {
        Json t = c.is_object() ? c.value("exec", Json()) : c;
        if (c.is_object() && t.is_object()) {   // 11-02 晚（使用者「6.要」）：{"exec": 內嵌單子}——收成 {"exec": 單子, "ws"?}，spawn_exec 照單子跑一次
            Json k = Json::object({{"exec", std::move(t)}});
            if (c.contains("ws")) {
                k["ws"] = c["ws"];
            }
            c = std::move(k);
            continue;
        }
        bool ok = t.is_string() || (t.is_array() && !t.empty());
        if (t.is_array()) {
            for (const Json& a : t) {
                ok = ok && a.is_string();
            }
        }
        if (!ok) {
            throw Error{code::CfgBad, key + "[" + name + "] 要是 aos-exec 的目標（字串或 [目標, 參數...]）或 {\"exec\": 目標或單子}"};
        }
        if (c.is_object() && c.contains("ws")) {   // eca 10-30：寫了 ws（read_loops 已轉絕對）＝收成 {"exec": 目標, "ws": 它}，其他 key 照舊忽略
            c = Json::object({{"exec", std::move(t)}, {"ws", c["ws"]}});
        } else {
            c = std::move(t);
        }
    }
    return out;
}

const Json& merge_want(const Json& base, const Json& ctl, const char* added_key, const char* removed_key, Json& merged) {
    if (!ctl.contains(added_key) && !ctl.contains(removed_key)) {
        return base;
    }
    std::unordered_map<std::string, const Json*> added;
    if (ctl.contains(added_key)) {
        for (auto& [n, spec] : ctl[added_key].items()) {
            added[n] = &spec;
        }
    }
    std::unordered_set<std::string> removed;
    if (ctl.contains(removed_key)) {
        for (const Json& n : ctl[removed_key]) {
            removed.insert(n.get<std::string>());
        }
    }
    merged = Json::object();   // 名字不重複，直接接在尾巴（ordered_json 的 [] 逐個比對，N 個就 N×N）
    auto& vec = static_cast<std::vector<std::pair<const std::string, Json>>&>(merged.get_ref<Json::object_t&>());
    for (auto& [n, spec] : base.items()) {
        if (removed.count(n) == 0) {   // 先加後減：同一個名字兩邊都寫＝不要
            auto a = added.find(n);    // 已在名單上的：設定換成 added 的（已在跑的不看設定變了沒，同 N-54）
            vec.emplace_back(n, a == added.end() ? spec : *a->second);
            if (a != added.end()) {
                added.erase(a);
            }
        }
    }
    if (ctl.contains(added_key)) {
        for (auto& [n, spec] : ctl[added_key].items()) {
            if (added.count(n) > 0 && removed.count(n) == 0) {   // 名單上本來沒有的：接在後面
                vec.emplace_back(n, spec);
            }
        }
    }
    return merged;
}

std::optional<std::string> check_apart(const Json& loops, const Json& execs) {
    if (execs.empty()) {
        return std::nullopt;
    }
    std::unordered_set<std::string> names;
    names.reserve(loops.size());
    for (auto& [n, spec] : loops.items()) {
        names.insert(n);
    }
    for (auto& [n, spec] : execs.items()) {
        if (names.count(n) > 0) {
            return "名字 " + aos::dumps(Json(n)) + " 同時在 loops 與 execs（兩邊共用名字空間）";
        }
    }
    return std::nullopt;
}

Daemon::Daemon(const std::map<std::string, std::string>& opts, const std::string& spec, const std::vector<std::string>& args)
    : Loop(opts, spec, daemon_defaults(), args) {
    if (stack_.empty()) {
        throw Error{code::StackMissing, "沒設定 AOS_STACK"};
    }
    loops_ = Json::object();
    try {   // 指示詞（10-23 晚）：起點＝設定檔的資料夾（cfg_dirs_）
        if (cfg_.contains("loops")) {
            loops_ = read_loops(cfg_["loops"], cfg_dirs_.dir_of("loops"), "loops");
        }
        if (cfg_.contains("execs")) {   // 10-30：一次性的子項，形狀同 loops
            execs_ = read_execs(cfg_["execs"], cfg_dirs_.dir_of("execs"), "execs");
        }
        for (const char* k : {"adopt", "loops_ctl", "loops_state", "loops_ctl_mailbox"}) {
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
    // 信箱（10-29 medium-plan § 四 3；11-02 晚改名 loops_ctl_mailbox、跟 loops_ctl 共存）：寫了（非 null）＝開信箱；沒寫、null＝不開。
    // 舊名 loops_mailbox 不認（照「其他 key 忽略」，11-02 晚代定）
    Json mb = cfg_.value("loops_ctl_mailbox", Json());
    if (!mb.is_null()) {
        if (!mb.is_string() || mb.get<std::string>().empty()) {
            throw Error{code::CfgBad, "loops_ctl_mailbox 要是信箱的路徑或 null"};
        }
        mbox_path_ = aos::join(stack_, mb.get<std::string>());
    }
    // 管轄那一對窗（10-29 拆窗）：沒寫＝預設檔名、null＝不開；路徑同 ctl／state 接在 $AOS_STACK 後面。11-02 晚起開了信箱也照開 loops_ctl
    std::pair<const char*, std::string*> wins[2] = {{"loops_ctl", &lctl_path_}, {"loops_state", &lstate_path_}};
    for (auto& [k, path] : wins) {
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
    // 11-02 拿掉「子項名字跟自己的窗撞名」（taken_names／check_names，10-22）：子項小格在 loops/<名字>/，撞不到 stack 頂層的窗
    std::optional<std::string> bad = check_apart(loops_, execs_);   // 10-30：execs 與 loops 共用名字空間
    if (bad) {
        throw Error{code::CfgBad, *bad};
    }
    Json a = cfg_.value("adopt", Json(true));
    if (!a.is_boolean()) {
        throw Error{code::CfgBad, "adopt 要是 true／false"};
    }
    cwd_ = std::filesystem::current_path().string();
    // 給子項的 AOS_DAEMON_STACK（11-02，resident-bob 衝突 2、daemon-env 方向題 2，使用者「照建議走」）：stack_ 轉絕對、結尾 /，
    // 跟 aos-exec 給的 AOS_STACK 同形（經 aos-exec 起的 stack_ 本來就是這樣；直接跑 daemon 時 $AOS_STACK 可能是相對的，子項會 cd 走、要絕對）
    dstack_ = aos::abspath(stack_);
    if (dstack_ != "/") {
        dstack_ += "/";
    }
    if (a.get<bool>()) {
        adopt();
    }
    want_ = loops_;   // 底（11-02 晚）：daemon.json 的 loops／execs；信改它、loops_ctl 每圈疊在它上面
    want_execs_ = execs_;
    if (!mbox_path_.empty()) {
        open_mailbox();   // 開了信箱：adopt 接回、daemon.json 沒有的也放進底（只留名）
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
    Json tables[2];   // loops、execs（10-30；10-30 前的 loops_state 沒有 execs＝空的）
    const char* keys[2] = {"loops", "execs"};
    for (int i = 0; i < 2; ++i) {
        if (i == 1 && !old->contains("execs")) {
            tables[i] = Json::object();
            continue;
        }
        try {   // 切檔（10-23）：是 {"$ref": [分檔, …]}，用 aos-directive 解開就是合好的表；分檔讀不到＝舊的讀不了
            tables[i] = aos::resolve((*old)[keys[i]], aos::dirname(lstate_path_));
        } catch (const Error&) {
            return;
        }
        if (!tables[i].is_object()) {
            return;
        }
        for (auto& [name, r] : tables[i].items()) {
            if (!r.is_object()) {
                return;   // 有一列壞就整份不接
            }
        }
    }
    for (int i = 0; i < 2; ++i) {
        for (auto& [name, r] : tables[i].items()) {
            if (r.value("phase", Json()) != "running" || index_.count(name) > 0) {
                continue;   // 兩張表同名（不該有）：先接到的算
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
                c.once = (i == 1);
                if (r.value("ws", Json()).is_string()) {
                    c.ws = r["ws"];   // eca 10-30：照舊列記著（10-30 前的列沒有＝null）
                }
                add(name, c);
            }
        }
    }
}

void Daemon::add(const std::string& name, const Child& c) {
    table_.push_back({name, c});
    index_[name] = std::prev(table_.end());
    log_child(name, c);   // 起來（或 adopt 接回）一行
}

void Daemon::log_child(const std::string& name, const Child& c) {
    Json line = Json::object();
    line["at"] = aos::utc_now_ms();
    line["name"] = name;
    line["table"] = c.once ? "execs" : "loops";
    line["phase"] = c.phase;
    line["pid"] = (long long)c.pid;
    line["code"] = c.code;
    line["signal"] = c.signal;
    if (!c.ws.is_null()) {
        line["ws"] = c.ws;
    }
    log_line(line);
}

Daemon::Table::iterator Daemon::drop(Table::iterator it) {
    auto& [n, c] = *it;
    log_child(n, c);   // 結束一行（done／stopped，帶 code、signal）
    if (c.phase == "done") {   // 自己結束的：本次執行不再起（11-02；被收掉的本來就不在期望表上，或換了種類要起新的）
        // 一律記進 ended_（期望表扣掉它，直到某一圈期望表裡沒有它；這一圈後面起少的也不會再起它）。
        // 11-02 晚（信箱與 loops_ctl 共存）：開了信箱再從底拿掉——下一圈套信之前，不是 loops_ctl 疊上去的那些就從 ended_ 放掉，
        // 所以之後再有信同名 *_added＝重新起；loops_ctl 疊上去的（它的 loops／execs 或 *_added 裡有）照 ended_ 的規則
        if (!mbox_path_.empty()) {
            (c.once ? want_execs_ : want_).erase(n);
        }
        ended_.insert({n, c.once});
    }
    index_.erase(n);
    return table_.erase(it);   // 小格 loops/<名字>/ 留著
}

void Daemon::flush_table() {
    try {
        write_more(aos::loop::proc_fields());
    } catch (const Error& e) {
        throw aos::loop::StateError{e};
    }
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

void Daemon::term(Child& c) {
    c.phase = "stopping";
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

void Daemon::tend() {
    read_loops_ctl();   // 每圈先讀 ctl.json（Loop）、再讀 loops_ctl.json；停著、暫停也照讀
    if (stopping_ || paused_) {   // ctl 的 stop／pause（11-03 起是指令，Loop 照做完放在這兩格）
        // 這圈收工／整圈暫停（10-29 medium-plan § 四 2）：不調表，只看一眼——自己結束的記 done、收的途中的照收；結束的印 log、拿掉（11-02）
        for (auto it = table_.begin(); it != table_.end();) {
            auto& [n, c] = *it;
            if (c.phase == "running" && !alive(c)) {
                c.phase = "done";
            } else if (c.phase == "stopping") {
                settle(c);
            }
            if (c.phase == "done" || c.phase == "stopped") {
                it = drop(it);
            } else {
                ++it;
            }
        }
        return;   // 接著 Loop 寫 paused／stopped 的 state（連 loops_state），不必另寫
    }
    // 11-02 晚：信箱與 loops_ctl 共存——先套信（一次性的改動，改的是底 want_／want_execs_），再把 loops_ctl（宣告）疊在底上算期望表
    Letters got;
    if (!mbox_path_.empty()) {
        for (auto it = ended_.begin(); it != ended_.end();) {   // 底來的已經從底拿掉了：放掉，信再加同名就起（loops_ctl 疊的留著）
            if (from_ctl(it->first, it->second)) {
                ++it;
            } else {
                it = ended_.erase(it);
            }
        }
        got = take_letters();   // 全部認領、照順序套進底，套完才對一次表、再回信收信
    }
    Json lm;
    Json em;
    auto [lw, ew] = ctl_want(lctl_good_, lm, em);   // 沒開 loops_ctl：lctl_good_ 一直是 {}＝期望表就是底
    for (auto it = ended_.begin(); it != ended_.end();) {   // 期望表裡（同種類）沒有它了＝之後名單再有它就照常起（11-02）
        const Json& w = it->second ? *ew : *lw;
        if (w.contains(it->first)) {
            ++it;
        } else {
            it = ended_.erase(it);
        }
    }
    reconcile(*lw, *ew);
    if (!mbox_path_.empty()) {
        done_letters(got);
    }
}

bool Daemon::from_ctl(const std::string& name, bool once) const {
    if (lctl_path_.empty()) {
        return false;
    }
    const Json& c = lctl_good_;
    const char* whole = once ? "execs" : "loops";
    const char* added = once ? "execs_added" : "loops_added";
    return (c.contains(whole) && c[whole].contains(name)) || (c.contains(added) && c[added].contains(name));
}

std::pair<const Json*, const Json*> Daemon::ctl_want(const Json& ctl, Json& lm, Json& em) const {
    // 期望表（N-06：整份 loops_ctl 就是期望，沒寫的回底）＝（loops_ctl 的 loops，沒寫＝底的）＋loops_added－loops_removed（10-23 晚）；
    // execs 那半同理（10-30；11-02 晚 loops_ctl 多認整份的 execs）。底＝want_／want_execs_（daemon.json＋adopt 接回的＋信改過的，11-02 晚）
    const Json& base = ctl.contains("loops") ? ctl["loops"] : want_;
    const Json& ebase = ctl.contains("execs") ? ctl["execs"] : want_execs_;
    return {&merge_want(base, ctl, "loops_added", "loops_removed", lm), &merge_want(ebase, ctl, "execs_added", "execs_removed", em)};
}

void Daemon::reconcile(const Json& want, const Json& want_execs) {
    std::unordered_map<std::string, bool> wanted;   // 名字 → 是不是 exec 型（want 是 ordered_json，contains 是逐個比對；先收成雜湊表）
    wanted.reserve(want.size() + want_execs.size());
    for (auto& [n, spec] : want.items()) {
        wanted.emplace(n, false);
    }
    for (auto& [n, spec] : want_execs.items()) {
        wanted.emplace(n, true);   // 兩邊同名不會到這裡（check_apart 擋在前面）
    }
    auto keep = [&](const std::string& n, const Child& c) {   // 期望表上有、而且種類一樣（種類換了＝收掉舊的、下一次起新的，10-30）
        auto w = wanted.find(n);
        return w != wanted.end() && w->second == c.once;
    };
    for (auto it = table_.begin(); it != table_.end();) {
        auto& [n, c] = *it;
        if (c.phase == "running") {
            if (!alive(c)) {
                c.phase = "done";   // 子項自己結束
            } else if (!keep(n, c)) {
                term(c);            // 表上多出來的：送 SIGTERM 就往下走，不等（10-23 壓測後改）
            }
        } else if (c.phase == "stopping") {
            settle(c);
        }
        if (c.phase == "done" || c.phase == "stopped") {
            it = drop(it);          // 結束了：印 log、拿掉（小格留著；11-02 子項結束後不留名單）
        } else {
            ++it;
        }
    }
    flush_table();   // 起之前先寫一份（退掉的、ctl_seq 變了的；起一大批要好一陣子，10-23 第 5 點），沒變就不寫
    // null＝信箱模式接回的（只留名、沒有設定），不會起；收的途中（stopping）的同名項還在表上：等它退了、下一次才起新的；
    // 本次執行已自己結束的（ended_，ctl 模式）不起。信箱模式的已在 drop 從 want_ 拿掉——want 就是 want_，這裡已經看不到
    for (auto& [n, spec] : want.items()) {
        if (index_.count(n) == 0 && !spec.is_null() && ended_.count({n, false}) == 0) {
            add(n, spawn(n, aos::join(aos::join(stack_, "loops"), n), spec, cwd_, dstack_));   // 11-02：子項的小格在 loops/<名字>/
            flush_table();          // 每起一個表就變了：寫一次（起一大批要好一陣子，讓人看得到進度；10-23 原本每秒一份）
        }
    }
    for (auto& [n, target] : want_execs.items()) {
        if (index_.count(n) == 0 && !target.is_null() && ended_.count({n, true}) == 0) {
            add(n, spawn_exec(n, aos::join(aos::join(stack_, "loops"), n), target, cwd_, dstack_));   // 10-30：直接 aos-exec 一次，不包 aos-loop
            flush_table();
        }
    }
}

void Daemon::finish() {
    bool any = false;
    for (auto& [n, c] : table_) {
        if (c.phase == "running" && alive(c)) {
            term(c);
        }
        any = any || c.phase == "stopping";
    }
    if (any) {
        try {
            write_state("stopping", Json());   // 等子項退：state 寫一份 stopping（連 loops_state）；寫不了就算了，收子項要緊
        } catch (const Error&) {
        }
    }
    while (true) {   // 11-02：結束的印 log、拿掉，每退一批寫一次 loops_state（不再每秒一份心跳）
        bool waiting = false;
        bool dropped = false;
        for (auto it = table_.begin(); it != table_.end();) {
            auto& [n, c] = *it;
            if (c.phase == "running" && !alive(c)) {
                c.phase = "done";   // 最後一次 tend 之後才自己結束的（沒送 SIGTERM）標 done、記 code（10-21 plan D7）
            } else if (c.phase == "stopping") {
                settle(c);
            }
            if (c.phase == "done" || c.phase == "stopped") {
                it = drop(it);
                dropped = true;
            } else {
                waiting = true;
                ++it;
            }
        }
        if (dropped) {
            try {
                flush_table();
            } catch (const Error&) {
            }
        }
        if (!waiting) {
            break;
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(50));
    }
}

}  // namespace aos::daemon
