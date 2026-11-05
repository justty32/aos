// daemon.cpp：【daemon】Daemon（說明見 daemon.hpp；10-21 傍晚；11-03 loops／execs 統稱 procs）。
//
// 每次（Loop 讀完 ctl.json 之後的 tend）：先讀 procs_ctl.json；ctl 是 stop／pause 就只看一眼（收已在收的、記自己結束的、daemon 要停的退了留成 stopped），不調表。
// 不然（開了信箱先套信、改底）期望表＝procs_ctl 的 procs（有寫）或底 want_，加上 procs_added、減掉 procs_removed；stopped 集合＝底 stopped_＋procs_stopped－procs_started →
//   reconcile：表上多出來的送 SIGTERM（phase stopping）就往下走、不等；之後每次看一眼，退了印 log、拿掉，滿 10 秒還在就 SIGKILL 整群——子 loop 那群，
//   加上它底下自成一群的（inst 起的單子，leaders_below）→
//   在 stopped 集合裡、還在跑的：往它的 ctl.json 寫 {"cmd": "stop", "seq": N}（halt），等它跑完這次自己退（沒有時間上限）→退了列留成 stopped（hold）→
//   看誰自己結束了（phase done，記 code／signal，印 log、從表上拿掉、本次執行不再起，11-02）→
//   起表上少掉的（在 stopped 集合裡的＝直接一列 stopped、不起），stopped 的列拿出 stopped 集合了＝用列上的 stack 再起（start）。
// 不論為什麼結束都先 finish()（收掉活著的子項；stopped 的列留著；還在跑的 loop 型退了列留成 sleeping，11-03 sleep／wake），Loop 再寫好 state。
// adopt：起來時讀自己上次的 procs_state，phase running、pid＋started_at_ticks 對得上的直接放回表上、不重起（N-17）；phase stopped 的列接成 stopped（不起、不判活）、名字進底的 stopped 集合；
//   phase sleeping 的列接成 sleeping（不判活）、不進 stopped 集合＝第一次 reconcile 照 start 那條用列上的 stack 再起（wake）。
#include "daemon/daemon.hpp"

#include "aos/files.hpp"
#include "aos/proc.hpp"

#include <chrono>
#include <fcntl.h>
#include <sys/file.h>
#include <unistd.h>
#include <cstdio>
#include <cstdlib>
#include <csignal>
#include <filesystem>
#include <limits>
#include <sstream>
#include <thread>
#include <unordered_map>
#include <unordered_set>

namespace aos::daemon {

using Clock = std::chrono::steady_clock;

static const int REVIVE_MS = 3000;  // 11-05（衝突 3）：wake／start 起來這麼久內就退＝原因寫「起不來」（11-05 晚起出錯結束一律留 stopped，3 秒只分原因字樣）
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

Json exec_of(const Json& spec, const std::string& cwd) {
    Json t = spec.is_object() ? spec.value("exec", Json()) : spec;
    if (t.is_array() && !t.empty()) {
        t = Json(t[0]);
    }
    if (!t.is_string()) {
        return Json();   // 內嵌單子、null（只留名）、設定沒寫 exec
    }
    std::string v = t.get<std::string>();
    if (v.empty() || v[0] == '#') {
        return Json(v);
    }
    size_t hash = v.find('#');   // 11-05：整理掉 ..（表上存相對 daemon 的 stack，`daemon/../kernel` 這種要先收掉）
    return Json(aos::abspath(aos::join(cwd, v.substr(0, hash))) + (hash == std::string::npos ? "" : v.substr(hash)));
}

Json def_of(const Json& spec) {
    return spec.is_object() ? spec.value("def", Json()) : Json();   // read_procs 已轉絕對（fix_path）；不驗在不在
}

bool is_once(const Json& spec) {
    if (spec.is_string() || spec.is_array()) {
        return true;
    }
    if (!spec.is_object() || !spec.contains("exec")) {
        return false;
    }
    for (auto& [k, v] : spec.items()) {
        if (k != "exec" && k != "ws" && k != "stack" && k != "def") {
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
            aos::Resolved r = aos::loop::resolve_keys(it.value, it.base_dir, {"max", "interval_ms", "ctl", "state", "ws", "stack", "def"});
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
            fix_path(r.value, name, key, "def", "定義資料夾");   // 11-04（aos-agent，使用者「那就b。」）：只記、不驗在不在
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
        for (const char* k : {"adopt", "procs_ctl", "procs_state", "procs_ctl_mailbox", "procs_loop", "procs_exec", "procs_stderr"}) {
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
    // 信箱（10-29 medium-plan § 四 3）：11-04 起沒寫＝預設名 procs_ctl_mailbox、null＝不開（跟 procs_ctl 同形；four-elements 題 5 後半）。跟 procs_ctl 可以同時開
    Json mb = cfg_.contains("procs_ctl_mailbox") ? cfg_["procs_ctl_mailbox"] : Json("procs_ctl_mailbox");
    if (!mb.is_null()) {
        if (!mb.is_string() || mb.get<std::string>().empty()) {
            throw Error{code::CfgBad, "procs_ctl_mailbox 要是信箱的路徑或 null"};
        }
        mbox_name_ = mb.get<std::string>();
        mbox_path_ = aos::join(stack_, mbox_name_);
    }
    // 小格裡三個檔名（11-04，four-elements 題 6「是否能在json中設置？但默認用這些名」）：沒寫＝預設；要是檔名（非空、不含 /、不以 . 開頭），不收 null
    std::pair<const char*, std::string*> cells[3] = {{"procs_loop", &names_.loop}, {"procs_exec", &names_.exec}, {"procs_stderr", &names_.err}};
    for (auto& [k, dst] : cells) {
        if (!cfg_.contains(k)) {
            continue;
        }
        const Json& v = cfg_[k];
        if (!v.is_string() || v.get<std::string>().empty() || v.get<std::string>().find('/') != std::string::npos ||
            v.get<std::string>()[0] == '.') {
            throw Error{code::CfgBad, std::string(k) + " 要是檔名（非空、不含 /、不以 . 開頭）"};
        }
        *dst = v.get<std::string>();
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
    // 給子項的 AOS_DAEMON（11-02，resident-bob 衝突 2；11-04 晚改名，舊名不認）：stack_ 轉絕對、結尾 /，跟 aos-exec 給的 AOS_STACK 同形；預設小格也從它拼（列上的 stack 一律絕對）
    dstack_ = aos::abspath(stack_);
    // 11-05 B 線：解開捷徑。子項拼 `$AOS_DAEMON/../../定義` 時 `..` 是 OS 照實體走的；stack 是捷徑（ws/.stack -> 別處）時字面算的 `..`
    // 會走到別處（實測：小格起不來 EntryMissing）。基準點是真實路徑，往上的 `..` 就跟字面一樣；往下穿過捷徑（定義是捷徑）本來就沒事，所以目標照字面
    {
        std::error_code ec;
        std::filesystem::path real = std::filesystem::canonical(dstack_, ec);
        if (!ec) {
            dstack_ = real.string();
        }
    }
    if (dstack_ != "/") {
        dstack_ += "/";
    }
    // 11-05（kernel-daemon 02 § 1 模式 1「繼承式」、06 步 1）：daemon 自己的身體（exec）也拿得到 AOS_DAEMON＝自己的 stack——
    // 身體是 daemon 起的，照 N-64 ④ 同一句；判官／llm kernel 當身體時靠它找自己這台的 ctl 信箱。子項照舊在 run_child 一律蓋過去。
    setenv("AOS_DAEMON", dstack_.c_str(), 1);
    check_running();   // 11-05（portable-flow 步 5「沒有才起、有就沿用」）
    if (a.get<bool>()) {
        adopt();
    }
    want_ = procs_;   // 底：daemon.json 的 procs；信改它、procs_ctl 每圈疊在它上面
    if (!mbox_path_.empty()) {
        open_mailbox();   // 開了信箱：adopt 接回、daemon.json 沒有的也放進底（只留名）
    }
}

// 11-05 B 線：用 flock 鎖住 stack 資料夾本身（不多建檔；O_CLOEXEC，子項 exec 後不帶著；行程不論怎麼死鎖都跟著放）。
// 鎖不到＝同一個 stack 已有 daemon 活著＝DaemonRunning。原本只比 state.json 的 pid＋ticks＋boot_id：兩個同時起時兩邊都還沒寫 state.json、
// 都過關，同一個 stack 跑兩個 daemon（實測一個死在 state.json.tmp 互搶、活下來的那個 state.json 記著死掉那個的 pid，再起第三個也擋不住）。
// pid 只拿來寫訊息。stack 打不開（不在）＝不鎖，後面寫窗時照各自的錯。
void Daemon::check_running() {
    int fd = ::open(stack_.c_str(), O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    if (fd < 0) {
        return;
    }
    if (::flock(fd, LOCK_EX | LOCK_NB) == 0) {
        lock_fd_ = fd;   // 一直開著到行程結束
        return;
    }
    ::close(fd);
    std::string who;
    std::optional<Json> st = state_path_.empty() ? std::nullopt : aos::read_json(state_path_);
    if (st && st->is_object() && st->value("pid", Json()).is_number_integer() && st->value("started_at_ticks", Json()).is_number_integer()) {
        // 對得上活著的才印 pid：另一個剛起、還沒寫 state.json 時，檔裡是上一個（已死）daemon 的 pid
        pid_t pid = (pid_t)(*st)["pid"].get<long long>();
        std::optional<long long> now = aos::proc_started_at_ticks(pid);
        if (now && *now == (*st)["started_at_ticks"].get<long long>()) {
            who = " (pid " + std::to_string(pid) + ")";
        }
    }
    throw Error{code::DaemonRunning, "a daemon is already running on this stack (" + stack_ + ")" + who + "; to reuse it, just aos-daemon-ctl add / aos-agent ctl add"};
}

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
            c.once = !std::filesystem::exists(aos::join(c.stack, names_.loop), ec);   // 小格有 daemon 寫的 loop.json（procs_loop 的名字）＝loop 型（procs § 2 第 7 條）
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
    stopped_.erase(n);   // 表上沒有了＝對 daemon 不存在：底的 stopped／slept 集合也不留它
    slept_.erase(n);
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
    // ctl 檔名看小格裡 daemon 自己寫的 loop.json（procs_loop 的名字）的 ctl（接回的也一樣）；N＝自己數的、也比 ctl 裡現有的 seq 大（內容一定跟上一道不一樣）。
    // ctl 沒寫＝ctl.json（aos-loop 的預設名，11-04 起 daemon 不再替它補）；讀不到 loop.json、ctl 不是檔名（寫了 null＝子 loop 沒開 ctl）＝改送 SIGTERM（同樣退了就留成 stopped）
    c.soft = true;
    std::optional<Json> cfg = aos::read_json(aos::join(c.stack, names_.loop));
    Json ctl = cfg && cfg->is_object() ? cfg->value("ctl", Json("ctl.json")) : Json();
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

void Daemon::hold(const std::string& name, Child& c, const char* phase) {
    c.phase = phase;      // stopped（daemon 下的 stop）或 sleeping（daemon 收工時收的 loop 型，11-03 sleep／wake）
    log_child(name, c);   // 行程結束一行
    c.held = true;        // 列留在表上（procs § 2c 第 2 條）：pid null、stack 不碰
    c.soft = false;
    c.nap = false;
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

// 11-05：出錯結束留成 stopped 的原因（英文，使用者 11-05「全都用英文吧」）：wake／start 後 REVIVE_MS 內退＝起不來，其他＝跑到一半掛了；
// 加結束碼（被訊號打掉多寫訊號）與小格 stderr 最後一行（最多 300 字）。
std::string Daemon::fail_reason(const Child& c) const {
    std::string code = aos::dumps(c.code);
    if (c.signal.is_number_integer()) {
        code += ", signal " + aos::dumps(c.signal);
    }
    bool quick = c.revived && Clock::now() - c.revived_at < std::chrono::milliseconds(REVIVE_MS);
    std::string why = quick ? "failed to start: exited within " + std::to_string(REVIVE_MS / 1000) + "s of wake/start (code " + code + ")"
                            : "failed while running: exited with code " + code;
    int err = 0;
    std::optional<std::string> text = aos::read_file(aos::join(c.stack, names_.err), err);
    if (text) {
        std::string t = *text;
        while (!t.empty() && (t.back() == '\n' || t.back() == ' ')) {
            t.pop_back();
        }
        std::string last = t.substr(t.rfind('\n') == std::string::npos ? 0 : t.rfind('\n') + 1);
        if (last.size() > 300) {
            last = last.substr(0, 300) + "...";
        }
        if (!last.empty()) {
            why += ": " + last;
        }
    }
    return why;
}

// 不調表地看一眼：stopped／sleeping 的列不動；running 的退了＝done（stop＝daemon 正要停它＝留成 stopped 的列；loop 型出錯結束＝留成 stopped＋reason，11-05）；收的途中的照收，
// 退了：daemon 下的 stop（soft）＝留成 stopped 的列、收工時收的 loop 型（nap）＝留成 sleeping 的列，其他（被收掉的）＝拿掉。回 true＝這列結束了、要拿掉。
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
        // 11-05（edge-agent 題 1「留表標 stopped (Recommended)」、edge-daemon 題 2「一起改成留表 (Recommended)」）：
        // loop 型出錯結束（結束碼非 0，含被訊號打掉的 128＋N）＝不下表，留成 stopped（要 start 才再起）＋reason（見 fail_reason）。
        // 3 秒（REVIVE_MS）只分原因字樣（起不來／跑到一半掛了）。退 0（做完：跑滿、身體退 10、別人往它的 ctl 寫 stop）照舊下表；
        // exec 型（只有跑和拔，start 不收它）、接回來的（不是自己生的、拿不到結束碼）也照舊下表。
        if (!c.once && c.code.is_number_integer() && c.code.get<long long>() != 0) {
            c.reason = fail_reason(c);
            hold(name, c);
            c.failed = true;   // 這一圈的起少的不再起它（stopped 參數是這圈開頭算的）
            stopped_.insert(name);
            return false;
        }
        c.phase = "done";   // 自己結束：照 11-02 從表上拿掉
        return true;
    }
    if (c.phase == "stopping" && settle(c)) {
        if (c.soft) {
            hold(name, c);
            return false;
        }
        if (c.nap) {
            hold(name, c, "sleeping");
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
    reconcile(want, ctl_stopped(pctl_good_), ctl_slept(pctl_good_));
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

Names Daemon::ctl_slept(const Json& ctl) const {
    Names s = slept_;   // 11-05：同 ctl_stopped（同名兩邊都寫＝醒）
    if (ctl.contains("procs_slept")) {
        for (const Json& n : ctl["procs_slept"]) {
            s.insert(n.get<std::string>());
        }
    }
    if (ctl.contains("procs_woken")) {
        for (const Json& n : ctl["procs_woken"]) {
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

Child Daemon::start(const std::string& name, const Json& spec, const std::string& cell, const Json& kept_ws, const Json& kept_exec,
                    const Json& kept_def) {
    bool deep = cell != dstack_ + "procs/" + name;   // 不是預設小格＝proc 自己的 stack：不在就 mkdir -p
    Child c = is_once(spec) ? spawn_exec(name, cell, deep, spec, cwd_, dstack_, names_) : spawn(name, cell, deep, spec, cwd_, dstack_, names_, kept_ws);
    c.exec = spec.is_null() ? kept_exec : exec_of(spec, cwd_);   // 11-04 晚：列上的 exec 欄
    c.def = spec.is_null() ? kept_def : def_of(spec);              // 11-04：列上的 def 欄
    return c;
}

void Daemon::reconcile(const Json& want, const Names& stopped, const Names& slept) {
    std::unordered_map<std::string, const Json*> wanted;   // want 是 ordered_json，contains 是逐個比對；先收成雜湊表
    wanted.reserve(want.size());
    for (auto& [n, spec] : want.items()) {
        wanted.emplace(n, &spec);
    }
    for (auto it = table_.begin(); it != table_.end();) {
        auto& [n, c] = *it;
        bool in = wanted.count(n) > 0;
        bool stop = in && stopped.count(n) > 0;
        bool nap = in && !stop && slept.count(n) > 0;   // 11-05 sleep：現在就睡（SIGTERM、10 秒 KILL、列 sleeping），wake 或 daemon 重開才醒
        if (look(n, c, stop)) {
            it = drop(it);   // 結束了：印 log、拿掉（小格留著；11-02 子項結束後不留名單）
            continue;
        }
        if (c.held) {
            if (!in) {
                it = drop(it);   // stopped／sleeping 的被 rm（或名單上沒有了）：列與集合都拿掉（stack 不碰）
                continue;
            }
            if (stop && c.phase == "sleeping") {
                c.phase = "stopped";   // 睡著的被 stop（例：daemon 沒在跑時寄的 procs_stopped）：不 wake，改成 stopped、要 start 才起
            }
        } else if (c.phase == "running") {
            if (!in) {
                term(c);         // 表上多出來的：送 SIGTERM 就往下走，不等（10-23 壓測後改）
            } else if (stop) {
                halt(n, c);      // daemon 的 stop：寫子 loop 的 ctl，等它跑完這次自己退
            } else if (nap && !c.once) {
                c.nap = true;    // 11-05 sleep：同收工那套，退了列留成 sleeping
                term(c);
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
            if (c.failed) {
                c.failed = false;   // 11-05：剛留成 stopped＋原因的，這圈不起；下一圈起 stopped 集合已有它
                continue;
            }
            if (c.held && stopped.count(n) == 0 && !(c.phase == "sleeping" && slept.count(n) > 0)) {   // 11-05：sleep 叫睡的不自己醒   // start（procs § 2c 第 3 條）／wake（sleeping 的列，11-03）：用列上的 stack 再起，ctl 不清（基準線）
                Child nc = start(n, spec, c.stack, c.ws, c.exec, c.def);   // 信箱接回只留名的（spec null）：ws 照列上的（11-03 晚：不然 wake 後表上 ws 變空）
                nc.revived = true;   // 11-05：REVIVE_MS 內退了＝留成 stopped＋原因（衝突 3）
                nc.revived_at = Clock::now();
                c = nc;
                log_child(n, c);
                flush_table();
            }
            continue;
        }
        if (ended_.count(n) > 0 || (spec.is_null() && stopped.count(n) == 0)) {
            continue;
        }
        if (stopped.count(n) > 0 || (slept.count(n) > 0 && !is_once(spec))) {   // add＋stop 同時（procs § 2c 第 2 條）：直接一列 stopped、不起、stack 不建
            Child c;
            c.phase = stopped.count(n) > 0 ? "stopped" : "sleeping";   // 11-05：add＋sleep 同時＝一列 sleeping、不起（wake 才起）
            c.held = true;
            c.own = false;
            c.stack = cell_of(n, spec);
            c.exec = exec_of(spec, cwd_);
            c.def = def_of(spec);
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
            continue;   // stopped／sleeping 的列：照寫進最後一份 state（procs § 2c 第 9 條）
        }
        if (c.phase == "running" && alive(c)) {
            c.nap = !c.once;   // 收工時還在跑的 loop 型（11-03 sleep／wake）：退了列留成 sleeping，再開時自動 wake；exec 型照舊拿掉
            term(c);
        } else if (c.phase == "stopping" && !c.termed) {
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
