// daemon.cpp：【daemon】Daemon（說明見 daemon.hpp；10-21 傍晚；11-03 loops／execs 統稱 procs）。
//
// 每次（Loop 讀完 ctl.json 之後的 tend）：先讀 procs_ctl.json；ctl 是 stop／pause 就只看一眼（收已在收的、記自己結束的、daemon 要停的退了留成 stopped），不調表。
// 不然（開了信箱先套信、改底）期望表＝procs_ctl 的 procs（有寫）或底 want_，加上 procs_added、減掉 procs_removed；stopped 集合＝底 stopped_＋procs_stopped－procs_started →
//   reconcile：表上多出來的送 SIGTERM（phase stopping）就往下走、不等；之後每次看一眼，退了印 log、拿掉，滿 10 秒還在就 SIGKILL 整群——子 loop 那群，
//   加上它底下自成一群的（inst 起的單子，leaders_below）→
//   在 stopped 集合裡、還在跑的：往它的 ctl.json 寫 {"cmd": "stop", "seq": N}（halt），等它跑完這次自己退（沒有時間上限）→退了列留成 stopped（hold）→
//   看誰自己結束了（phase done，記 code／signal，印 log、從表上拿掉、本次執行不再起，11-02）→
//   起表上少掉的（在 stopped 集合裡的＝直接一列 stopped、不起），stopped 的列拿出 stopped 集合了＝用列上的 stack 再起（start）。
// 不論為什麼結束都先 finish()（收掉活著的子項；stopped 的列留著），Loop 再寫好 state。
// adopt：起來時讀自己上次的 procs_state，phase running、pid＋started_at_ticks 對得上的直接放回表上、不重起（N-17）；phase stopped 的列接成 stopped（不起、不判活）、名字進底的 stopped 集合。
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

static const int GRACE_MS = 10000;   // 收子項：SIGTERM 後等幾毫秒才 SIGKILL（P-36 daemon 的 grace 慣例 10000）

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

static void check_name(const std::string& name, const std::string& key) {
    if (name.empty() || name.find('/') != std::string::npos || name.find('#') != std::string::npos || name[0] == '.') {
        throw Error{code::CfgBad, key + " 的名字 " + aos::dumps(Json(name)) + " 不能當資料夾名"};
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

// proc 物件的 ws、stack（eca 10-30；stack 11-03 procs § 2b）：要是非空字串（null＝當沒寫、拿掉），相對路徑從 daemon 的 cwd 轉絕對（abspath 從行程的 cwd 算；
// daemon 自己不 cd，所以就是 daemon 的 cwd——信、procs_ctl、daemon.json 裡寫的都一樣，同相對 exec）；abspath 結尾不帶 /。不驗在不在
// （ws：aos-exec 會報 WsMissing，寫在小格 stderr.txt；stack：起的時候不在就建）。
static void fix_path(Json& c, const std::string& name, const std::string& key, const char* k, const char* what) {
    if (!c.contains(k)) {
        return;
    }
    const Json& w = c[k];
    if (w.is_null()) {
        c.erase(k);
        return;
    }
    if (!w.is_string() || w.get<std::string>().empty()) {
        throw Error{code::CfgBad, key + "[" + name + "]." + k + " 要是" + what + "的路徑（非空字串）"};
    }
    c[k] = aos::abspath(w.get<std::string>());
}

static bool is_target(const Json& t) {   // aos-exec 的目標：字串或 [目標, 參數...]（非空字串陣列）
    if (t.is_string()) {
        return true;
    }
    if (!t.is_array() || t.empty()) {
        return false;
    }
    for (const Json& a : t) {
        if (!a.is_string()) {
            return false;
        }
    }
    return true;
}

bool is_once(const Json& spec) {
    if (spec.is_string() || spec.is_array()) {
        return true;
    }
    if (!spec.is_object() || !spec.contains("exec")) {
        return false;
    }
    for (auto& [k, v] : spec.items()) {
        if (k != "exec" && k != "ws" && k != "stack") {
            return false;   // 多了任何一個 key＝loop 設定（procs § 2 第 3 條）
        }
    }
    return true;
}

Json read_procs(const Json& v, const std::string& base, const std::string& key) {
    aos::Resolved top = aos::resolve_shallow(v, base);   // 拆成好幾份檔＝{"$ref": [檔, …]}，合好的每個子項記著它來自哪份檔
    if (!top.value.is_object()) {
        throw Error{code::CfgBad, key + " 要是 {名字: proc}"};
    }
    Json out = Json::object();   // 名字本來就不重複（JSON 物件；$ref 陣列合的同名後面的蓋前面的），直接接在尾巴
    auto& vec = static_cast<std::vector<std::pair<const std::string, Json>>&>(out.get_ref<Json::object_t&>());
    vec.reserve(top.value.size());
    const std::string bad_target = " 要是 aos-exec 的目標（字串或 [目標, 參數...]）、{\"exec\": 目標或單子} 或 loop 設定";
    for (auto& [name, c] : top.value.items()) {
        check_name(name, key);
        aos::Resolved it = aos::resolve_shallow(c, top.dir_of(name));
        if (it.value.is_string() || it.value.is_array()) {   // exec 型（procs § 2 第 1 條）
            Json t = aos::resolve(it.value, it.base_dir);
            if (!is_target(t)) {
                throw Error{code::CfgBad, key + "[" + name + "]" + bad_target};
            }
            vec.emplace_back(name, std::move(t));
        } else if (it.value.is_object()) {
            aos::Resolved r = aos::loop::resolve_keys(it.value, it.base_dir, {"max", "interval_ms", "ctl", "state", "ws", "stack"});
            if (r.value.is_object() && r.value.contains("exec")) {   // exec 是單子時裡面不解、相對 $ref 轉成絕對（10-24）
                aos::Resolved ex = aos::loop::resolve_exec(r.value["exec"], r.dir_of("exec"));
                if (ex.value.is_object()) {
                    ex.value = abs_refs(ex.value, ex.base_dir);
                }
                r.value["exec"] = std::move(ex.value);
            }
            if (!r.value.is_object()) {
                throw Error{code::CfgBad, key + "[" + name + "]" + bad_target};
            }
            fix_path(r.value, name, key, "ws", "工作區");
            fix_path(r.value, name, key, "stack", " stack ");
            if (is_once(r.value) && !is_target(r.value["exec"]) && !r.value["exec"].is_object()) {   // exec 型的物件（procs § 2 第 2 條）
                throw Error{code::CfgBad, key + "[" + name + "]" + bad_target};
            }
            vec.emplace_back(name, std::move(r.value));   // loop 設定：daemon 認的格以外不驗，交給子 loop
        } else {
            throw Error{code::CfgBad, key + "[" + name + "]" + bad_target};
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

Daemon::Daemon(const std::map<std::string, std::string>& opts, const std::string& spec, const std::vector<std::string>& args)
    : Loop(opts, spec, daemon_defaults(), args) {
    if (stack_.empty()) {
        throw Error{code::StackMissing, "沒設定 AOS_STACK"};
    }
    try {   // 指示詞（10-23 晚）：起點＝設定檔的資料夾（cfg_dirs_）。舊名 loops／execs／loops_* 不認（C-48，11-03「當沒看到」）
        if (cfg_.contains("procs")) {
            procs_ = read_procs(cfg_["procs"], cfg_dirs_.dir_of("procs"), "procs");
        }
        for (const char* k : {"adopt", "procs_ctl", "procs_state", "procs_ctl_mailbox"}) {
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
    // 信箱（10-29 medium-plan § 四 3）：寫了（非 null）＝開信箱；沒寫、null＝不開。跟 procs_ctl 可以同時開
    Json mb = cfg_.value("procs_ctl_mailbox", Json());
    if (!mb.is_null()) {
        if (!mb.is_string() || mb.get<std::string>().empty()) {
            throw Error{code::CfgBad, "procs_ctl_mailbox 要是信箱的路徑或 null"};
        }
        mbox_path_ = aos::join(stack_, mb.get<std::string>());
    }
    // 管轄那一對窗（10-29 拆窗）：沒寫＝預設檔名、null＝不開；路徑同 ctl／state 接在 $AOS_STACK 後面
    std::pair<const char*, std::string*> wins[2] = {{"procs_ctl", &pctl_path_}, {"procs_state", &pstate_path_}};
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
    if (!pstate_path_.empty()) {   // 分檔的資料夾：procs_state 檔名去掉副檔名＋_procs，跟它同一層
        std::string name = pstate_path_.substr(pstate_path_.rfind('/') + 1);
        size_t dot = name.rfind('.');
        if (dot != std::string::npos && dot > 0) {
            name = name.substr(0, dot);
        }
        parts_dir_ = aos::join(aos::dirname(pstate_path_), name + "_procs");
    }
    Json a = cfg_.value("adopt", Json(true));
    if (!a.is_boolean()) {
        throw Error{code::CfgBad, "adopt 要是 true／false"};
    }
    cwd_ = std::filesystem::current_path().string();
    // 給子項的 AOS_DAEMON_STACK（11-02，resident-bob 衝突 2）：stack_ 轉絕對、結尾 /，跟 aos-exec 給的 AOS_STACK 同形；預設小格也從它拼（列上的 stack 一律絕對）
    dstack_ = aos::abspath(stack_);
    if (dstack_ != "/") {
        dstack_ += "/";
    }
    if (a.get<bool>()) {
        adopt();
    }
    want_ = procs_;   // 底：daemon.json 的 procs；信改它、procs_ctl 每圈疊在它上面
    if (!mbox_path_.empty()) {
        open_mailbox();   // 開了信箱：adopt 接回、daemon.json 沒有的也放進底（只留名）
    }
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
    for (auto& [name, r] : table.items()) {
        Json phase = r.value("phase", Json());
        Json st = r.value("stack", Json());
        Child c;
        c.own = false;
        c.stack = st.is_string() && !st.get<std::string>().empty() ? st.get<std::string>() : cell_of(name, Json());
        if (r.value("ws", Json()).is_string()) {
            c.ws = r["ws"];
        }
        if (phase == "stopped") {   // stopped 的列（11-03 procs § 2c 第 7 條）：接成 stopped、不起、不判活；名字進底的 stopped 集合
            c.phase = "stopped";
            c.held = true;
            c.code = r.value("code", Json());
            c.signal = r.value("signal", Json());
            stopped_.insert(name);
            add(name, c);
            continue;
        }
        if (phase != "running") {
            continue;
        }
        Json pid = r.value("pid", Json());
        Json ticks = r.value("started_at_ticks", Json());
        if (!pid.is_number_integer() || !ticks.is_number_integer()) {
            continue;
        }
        std::optional<long long> now = aos::proc_started_at_ticks((pid_t)pid.get<long long>());
        if (now && *now == ticks.get<long long>()) {
            c.pid = (pid_t)pid.get<long long>();
            c.started_at_ticks = ticks.get<long long>();
            std::error_code ec;
            c.once = !std::filesystem::exists(aos::join(c.stack, "loop.json"), ec);   // 小格有 daemon 寫的 loop.json＝loop 型（procs § 2 第 7 條）
            add(name, c);
        }
    }
}

void Daemon::add(const std::string& name, const Child& c) {
    table_.push_back({name, c});
    index_[name] = std::prev(table_.end());
    if (!c.held) {
        log_child(name, c);   // 起來（或 adopt 接回）一行；stopped 的列沒有行程，不印
    }
}

void Daemon::log_child(const std::string& name, const Child& c) {
    Json line = Json::object();
    line["at"] = aos::utc_now_ms();
    line["name"] = name;
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
    if (!c.held) {
        log_child(n, c);   // 結束一行（done／stopped，帶 code、signal）；stopped 的列被 rm 沒有行程結束，不印
    }
    if (c.phase == "done") {   // 自己結束的：本次執行不再起（11-02）。開了信箱再從底拿掉（之後再有信同名 procs_added＝重新起）
        if (!mbox_path_.empty()) {
            want_.erase(n);
        }
        ended_.insert(n);
    }
    stopped_.erase(n);   // 表上沒有了＝對 daemon 不存在：底的 stopped 集合也不留它
    index_.erase(n);
    return table_.erase(it);   // 小格（stack）留著
}

void Daemon::flush_table() {
    try {
        write_more(aos::loop::proc_fields());
    } catch (const Error& e) {
        throw aos::loop::StateError{e};
    }
}

void Daemon::term(Child& c) {
    c.phase = "stopping";
    c.termed = true;
    c.deadline = Clock::now() + std::chrono::milliseconds(GRACE_MS);
    kill(c.pid, SIGTERM);   // 給那支子項（它自己轉給它的那次）；已經沒了就算了
}

static bool is_nat(const Json& v) {
    return v.is_number_unsigned() || (v.is_number_integer() && v.get<long long>() >= 0);
}

void Daemon::halt(const std::string& name, Child& c) {
    // daemon 的 stop（procs § 2c 第 2 條、ctl-commands § 5）：往子 loop 的 ctl.json 寫一道 {"cmd": "stop", "seq": N}，讓它跑完這次自己退 0（不 SIGTERM）。
    // ctl 檔名看小格裡 daemon 自己寫的 loop.json 的 ctl（接回的也一樣）；N＝自己數的、也比 ctl 裡現有的 seq 大（內容一定跟上一道不一樣）。
    // 讀不到 loop.json、ctl 不是檔名（寫了 null＝子 loop 沒開 ctl）＝改送 SIGTERM（同樣退了就留成 stopped）
    c.soft = true;
    std::optional<Json> cfg = aos::read_json(aos::join(c.stack, "loop.json"));
    Json ctl = cfg && cfg->is_object() ? cfg->value("ctl", Json()) : Json();
    if (!ctl.is_string() || ctl.get<std::string>().empty()) {
        term(c);
        return;
    }
    std::string path = aos::join(c.stack, ctl.get<std::string>());
    std::optional<Json> old = aos::read_json(path);
    if (old && old->is_object() && is_nat(old->value("seq", Json())) && old->value("seq", Json()).get<long long>() > stop_seq_) {
        stop_seq_ = (*old)["seq"].get<long long>();
    }
    stop_seq_ += 1;
    try {
        aos::loop::write_window(path, Json::object({{"cmd", "stop"}, {"seq", stop_seq_}}));
    } catch (const Error& e) {
        throw Error{e.code, "停不了 " + name + "：" + e.msg};
    }
    c.phase = "stopping";
}

void Daemon::hold(const std::string& name, Child& c) {
    c.phase = "stopped";
    log_child(name, c);   // 行程結束一行
    c.held = true;        // 列留在表上（procs § 2c 第 2 條）：pid null、stack 不碰
    c.soft = false;
    c.termed = false;
    c.killed = false;
    c.pid = 0;
    c.started_at_ticks.reset();
}

bool Daemon::settle(Child& c) {
    if (!alive(c)) {
        c.phase = "stopped";   // 行程不在了
        return true;
    }
    if (c.termed && !c.killed && Clock::now() >= c.deadline) {   // 寫 ctl 的 stop 沒有時間上限，只有送過 SIGTERM 的才 SIGKILL
        std::vector<pid_t> below = leaders_below(c.pid);   // 先掃：子 loop 一死，底下自成 session 的單子就認不出是誰的了
        aos::signal_group(c.pid, SIGKILL);   // 整群：子 loop 與它同群的孫程式
        for (pid_t g : below) {
            aos::signal_group(g, SIGKILL);   // 底下自成一群的（inst 起的單子，連它的子孫）
        }
        c.killed = true;
    }
    return false;
}

// 不調表地看一眼：stopped 的列不動；running 的退了＝done（stop＝daemon 正要停它＝留成 stopped 的列）；收的途中的照收，
// 退了：daemon 下的 stop（soft）＝留成 stopped 的列，其他（被收掉的）＝拿掉。回 true＝這列結束了、要拿掉。
bool Daemon::look(const std::string& name, Child& c, bool stop) {
    if (c.held) {
        return false;
    }
    if (c.phase == "running") {
        if (alive(c)) {
            return false;
        }
        if (stop) {
            hold(name, c);
            return false;
        }
        c.phase = "done";   // 自己結束（跑滿、退 10、訊號、別人往它的 ctl 寫 stop……）：照 11-02 從表上拿掉
        return true;
    }
    if (c.phase == "stopping" && settle(c)) {
        if (c.soft) {
            hold(name, c);
            return false;
        }
        return true;
    }
    return false;
}

void Daemon::tend() {
    read_procs_ctl();   // 每圈先讀 ctl.json（Loop）、再讀 procs_ctl.json；停著、暫停也照讀
    if (stopping_ || paused_) {   // ctl 的 stop／pause（11-03 起是指令，Loop 照做完放在這兩格）
        // 這圈收工／整圈暫停（10-29 medium-plan § 四 2）：不調表、起停也等解除，只看一眼
        for (auto it = table_.begin(); it != table_.end();) {
            if (look(it->first, it->second, false)) {
                it = drop(it);
            } else {
                ++it;
            }
        }
        return;   // 接著 Loop 寫 paused／stopped 的 state（連 procs_state），不必另寫
    }
    // 信箱與 procs_ctl 共存——先套信（一次性的改動，改的是底 want_／stopped_），再把 procs_ctl（宣告）疊在底上算期望表
    Letters got;
    if (!mbox_path_.empty()) {
        for (auto it = ended_.begin(); it != ended_.end();) {   // 底來的已經從底拿掉了：放掉，信再加同名就起（procs_ctl 疊的留著）
            if (from_ctl(*it)) {
                ++it;
            } else {
                it = ended_.erase(it);
            }
        }
        got = take_letters();   // 全部認領、照順序套進底，套完才對一次表、再回信收信
    }
    Json merged;
    const Json& want = ctl_want(pctl_good_, merged);   // 沒開 procs_ctl：pctl_good_ 一直是 {}＝期望表就是底
    for (auto it = ended_.begin(); it != ended_.end();) {   // 期望表裡沒有它了＝之後名單再有它就照常起（11-02）
        if (want.contains(*it)) {
            ++it;
        } else {
            it = ended_.erase(it);
        }
    }
    reconcile(want, ctl_stopped(pctl_good_));
    if (!mbox_path_.empty()) {
        done_letters(got);
    }
}

bool Daemon::from_ctl(const std::string& name) const {
    if (pctl_path_.empty()) {
        return false;
    }
    const Json& c = pctl_good_;
    return (c.contains("procs") && c["procs"].contains(name)) || (c.contains("procs_added") && c["procs_added"].contains(name));
}

const Json& Daemon::ctl_want(const Json& ctl, Json& merged) const {
    // 期望表（N-06：整份 procs_ctl 就是期望，沒寫的回底）＝（procs_ctl 的 procs，沒寫＝底的）＋procs_added－procs_removed
    const Json& base = ctl.contains("procs") ? ctl["procs"] : want_;
    return merge_want(base, ctl, "procs_added", "procs_removed", merged);
}

Names Daemon::ctl_stopped(const Json& ctl) const {
    Names s = stopped_;   // 先加後減：同名兩邊都寫＝起（procs § 2c 第 1 條）
    if (ctl.contains("procs_stopped")) {
        for (const Json& n : ctl["procs_stopped"]) {
            s.insert(n.get<std::string>());
        }
    }
    if (ctl.contains("procs_started")) {
        for (const Json& n : ctl["procs_started"]) {
            s.erase(n.get<std::string>());
        }
    }
    return s;
}

std::string Daemon::cell_of(const std::string& name, const Json& spec) const {
    if (spec.is_object() && spec.contains("stack")) {
        return spec["stack"].get<std::string>();   // read_procs 已轉絕對（procs § 2b）
    }
    return dstack_ + "procs/" + name;   // 預設小格（11-03 原 loops/<名字>/）
}

Child Daemon::start(const std::string& name, const Json& spec, const std::string& cell) {
    bool deep = cell != dstack_ + "procs/" + name;   // 不是預設小格＝proc 自己的 stack：不在就 mkdir -p
    return is_once(spec) ? spawn_exec(name, cell, deep, spec, cwd_, dstack_) : spawn(name, cell, deep, spec, cwd_, dstack_);
}

void Daemon::reconcile(const Json& want, const Names& stopped) {
    std::unordered_map<std::string, const Json*> wanted;   // want 是 ordered_json，contains 是逐個比對；先收成雜湊表
    wanted.reserve(want.size());
    for (auto& [n, spec] : want.items()) {
        wanted.emplace(n, &spec);
    }
    for (auto it = table_.begin(); it != table_.end();) {
        auto& [n, c] = *it;
        bool in = wanted.count(n) > 0;
        bool stop = in && stopped.count(n) > 0;
        if (look(n, c, stop)) {
            it = drop(it);   // 結束了：印 log、拿掉（小格留著；11-02 子項結束後不留名單）
            continue;
        }
        if (c.held) {
            if (!in) {
                it = drop(it);   // stopped 的被 rm：列與集合都拿掉（stack 不碰）
                continue;
            }
        } else if (c.phase == "running") {
            if (!in) {
                term(c);         // 表上多出來的：送 SIGTERM 就往下走，不等（10-23 壓測後改）
            } else if (stop) {
                halt(n, c);      // daemon 的 stop：寫子 loop 的 ctl，等它跑完這次自己退
            }
        } else if (c.phase == "stopping" && c.soft && !c.termed && !in) {
            term(c);             // 等它自己退的途中被 rm：改送 SIGTERM
        }
        ++it;
    }
    flush_table();   // 起之前先寫一份（退掉的、ctl_seq 變了的；起一大批要好一陣子），沒變就不寫
    // null＝信箱模式接回的（只留名、沒有設定），不會起（stopped 的列 start＝照小格裡的 loop.json 起）；收的途中（stopping）的同名項還在表上：等它退了、下一次才起；
    // 本次執行已自己結束的（ended_）不起
    for (auto& [n, spec] : want.items()) {
        auto at = index_.find(n);
        if (at != index_.end()) {
            Child& c = at->second->second;
            if (c.held && stopped.count(n) == 0) {   // start（procs § 2c 第 3 條）：用列上的 stack 再起，ctl 不清（基準線）
                Child nc = start(n, spec, c.stack);
                c = nc;
                log_child(n, c);
                flush_table();
            }
            continue;
        }
        if (ended_.count(n) > 0 || (spec.is_null() && stopped.count(n) == 0)) {
            continue;
        }
        if (stopped.count(n) > 0) {   // add＋stop 同時（procs § 2c 第 2 條）：直接一列 stopped、不起、stack 不建
            Child c;
            c.phase = "stopped";
            c.held = true;
            c.own = false;
            c.stack = cell_of(n, spec);
            add(n, c);
        } else {
            add(n, start(n, spec, cell_of(n, spec)));
        }
        flush_table();   // 每起一個表就變了：寫一次（起一大批要好一陣子，讓人看得到進度）
    }
}

void Daemon::finish() {
    bool any = false;
    for (auto& [n, c] : table_) {
        if (c.held) {
            continue;   // stopped 的列：照寫進最後一份 state（procs § 2c 第 9 條）
        }
        if ((c.phase == "running" && alive(c)) || (c.phase == "stopping" && !c.termed)) {
            term(c);   // 等它自己退的（soft）也改送 SIGTERM；退了照樣留成 stopped 的列
        }
        any = any || c.phase == "stopping";
    }
    if (any) {
        try {
            write_state("stopping", Json());   // 等子項退：state 寫一份 stopping（連 procs_state）；寫不了就算了，收子項要緊
        } catch (const Error&) {
        }
    }
    while (true) {   // 結束的印 log、拿掉，每退一批寫一次 procs_state
        bool waiting = false;
        bool changed = false;
        for (auto it = table_.begin(); it != table_.end();) {
            auto& [n, c] = *it;
            bool was = c.held;
            if (look(n, c, false)) {   // 最後一次 tend 之後才自己結束的（沒送 SIGTERM）標 done、記 code（10-21 plan D7）
                it = drop(it);
                changed = true;
                continue;
            }
            changed = changed || was != c.held;
            waiting = waiting || !c.held;
            ++it;
        }
        if (changed) {
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
