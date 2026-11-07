// daemon.cpp：【daemon】初始化設定、展開 tick 普通子項、設定環境、路徑、信箱與 stack 鎖（說明見 daemon.hpp）。
#include "daemon/daemon.hpp"
#include "child/limits.hpp"
#include "aos/util/files.hpp"
#include "aos/util/tick.hpp"
#include <cstdlib>
#include <filesystem>
#include <fcntl.h>
#include <limits>
#include <pthread.h>
#include <sys/file.h>
#include <unistd.h>

namespace aos::daemon {

static aos::loop::Defaults daemon_defaults() {
    aos::loop::Defaults d;
    d.prog = "aos-daemon";
    d.max = std::nullopt;
    d.interval_ms = 200;
    d.need_exec = false;
    return d;
}

// 只在入口展開；之後起停、重起與表列都走普通 proc。相對 file 從 daemon stack 算。
static void expand_tick(const Json& tick, const std::string& stack, Json& procs) {
    if (tick.is_null() || tick == Json(false)) {
        return;
    }
    if (tick != Json(true) && !tick.is_object()) {
        throw Error{code::CfgBad, "tick must be a boolean, an object or null"};
    }
    Json opts = tick.is_object() ? tick : Json::object();
    for (auto& [k, v] : opts.items()) {
        if (k != "file" && k != "interval_ms" && k != "name") {
            throw Error{code::CfgBad, "tick: unknown key " + k};
        }
    }
    for (const char* k : {"file", "name"}) {
        if (opts.contains(k) && (!opts[k].is_string() || opts[k].get<std::string>().empty())) {
            throw Error{code::CfgBad, std::string("tick.") + k + " must be a non-empty string"};
        }
    }
    long long interval = 0;
    if (opts.contains("interval_ms")) {
        const Json& n = opts["interval_ms"];
        if (!aos::is_count(n) || n == Json(0) ||
            (n.is_number_unsigned() && n.get<unsigned long long>() >
             static_cast<unsigned long long>(std::numeric_limits<long long>::max()))) {
            throw Error{code::CfgBad, "tick.interval_ms must be a positive integer within signed 64-bit range"};
        }
        interval = n.get<long long>();
    } else {
        interval = aos::tick_interval_ms();
    }
    std::string file = aos::abspath(aos::join(stack, opts.value("file", std::string("tick"))));
    std::string name = opts.value("name", std::string("_tick"));
    if (procs.contains(name)) {
        throw Error{code::CfgBad, "tick.name conflicts with procs: " + name};
    }
    // exec 陣列是 aos-exec 的檔案目標；PATH 指令用現有的內嵌單子 argv，不另開特殊規則。
    Json proc = Json::object({{"exec", Json::object({{"argv", Json::array({"aos-tick", file})}})},
                              {"interval_ms", interval}, {"auto_restart", true}});
    Json expanded = read_procs(Json::object({{name, proc}}), stack, "tick");   // 同一般 proc 驗名字
    for (auto& [n, spec] : procs.items()) {
        expanded[n] = spec;
    }
    procs = std::move(expanded);
    // 在任何子項（含身體）開始前設好；明寫 interval_ms 就設（寫 1000 也設，近的贏；11-07 sol 審查 #10），沒寫不動繼承的。
    setenv("AOS_TICK", file.c_str(), 1);
    if (opts.contains("interval_ms")) {
        std::string value = std::to_string(interval);
        setenv("AOS_TICK_INTERVAL", value.c_str(), 1);
    }
}

Daemon::Daemon(const std::map<std::string, std::string>& opts, const std::string& spec, const std::vector<std::string>& args)
    : Loop(opts, spec, daemon_defaults(), args) {
    if (has_exec_) {   // 11-05（edge-daemon 題 1）：身體 daemon 自己跑（run_body，失敗下一圈再跑）；Loop 當沒有身體
        body_ = exec_;
        has_body_ = true;
        has_exec_ = false;
    }
    if (stack_.empty()) {
        throw Error{code::StackMissing, "AOS_STACK is not set"};
    }
    try {   // 指示詞（10-23 晚）：起點＝設定檔的資料夾（cfg_dirs_）。舊名 loops／execs／loops_* 不認（C-48，11-03「當沒看到」）
        if (cfg_.contains("procs")) {
            procs_ = read_procs(cfg_["procs"], cfg_dirs_.dir_of("procs"), "procs");
        }
        if (cfg_.contains("tick")) {
            cfg_["tick"] = aos::loop::resolve_keys(cfg_["tick"], cfg_dirs_.dir_of("tick"),
                                                  {"file", "interval_ms", "name"}).value;
        }
        for (const char* k : {"adopt", "procs_ctl", "procs_state", "procs_ctl_mailbox", "procs_loop", "procs_exec", "procs_stderr", "limits"}) {
            if (cfg_.contains(k)) {
                cfg_[k] = aos::resolve(cfg_[k], cfg_dirs_.dir_of(k));
            }
        }
    } catch (const Error& e) {
        if (e.code == code::DirectiveBad) {
            throw Error{e.code, "config " + spec + ": cannot resolve directives: " + e.msg};
        }
        throw;
    }
    // 信箱（10-29 medium-plan § 四 3）：11-04 起沒寫＝預設名 procs_ctl_mailbox、null＝不開（跟 procs_ctl 同形；four-elements 題 5 後半）。跟 procs_ctl 可以同時開
    Json mb = cfg_.contains("procs_ctl_mailbox") ? cfg_["procs_ctl_mailbox"] : Json("procs_ctl_mailbox");
    if (!mb.is_null()) {
        if (!mb.is_string() || mb.get<std::string>().empty()) {
            throw Error{code::CfgBad, "procs_ctl_mailbox must be a mailbox path or null"};
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
            throw Error{code::CfgBad, std::string(k) + " must be a file name (non-empty, no /, not starting with .)"};
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
            throw Error{code::CfgBad, std::string(k) + " must be a file name or null"};
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
    // 11-05（feat-proto 件 5）：頂層 limits＝沒寫 limits 的列用的預設份額（沒寫、null＝不限）；壞＝CfgBad 退 1
    limits_ = cfg_.value("limits", Json());
    check_limits(limits_, "limits");
    Json a = cfg_.value("adopt", Json(true));
    if (!a.is_boolean()) {
        throw Error{code::CfgBad, "adopt must be true or false"};
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
    const char* inherited = std::getenv("AOS_DAEMON");
    if (inherited != nullptr && inherited[0] != '\0') {
        parent_ = std::string(inherited);   // 上一層照字面留；解不開也不改寫
        std::error_code parent_ec;
        std::error_code self_ec;
        std::string own_stack = dstack_;
        if (own_stack.size() > 1 && own_stack.back() == '/') {
            own_stack.pop_back();
        }
        std::filesystem::path parent_real = std::filesystem::canonical(inherited, parent_ec);
        std::filesystem::path self_real = std::filesystem::canonical(own_stack, self_ec);
        if (!parent_ec && !self_ec && parent_real == self_real) {
            parent_ = nullptr;   // 人殼把 AOS_DAEMON export 成自己：上一層不可能是自己
        }
    }
    // 11-05（kernel-daemon 02 § 1 模式 1「繼承式」、06 步 1）：daemon 自己的身體（exec）也拿得到 AOS_DAEMON＝自己的 stack——
    // 身體是 daemon 起的，照 N-64 ④ 同一句；判官／llm kernel 當身體時靠它找自己這台的 ctl 信箱。子項照舊在 run_child 一律蓋過去。
    setenv("AOS_DAEMON", dstack_.c_str(), 1);
    expand_tick(cfg_.value("tick", Json()), dstack_, procs_);
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
// 鎖不到＝同一個 stack 已有 daemon 活著＝DaemonExists。原本只比 state.json 的 pid＋ticks＋boot_id：兩個同時起時兩邊都還沒寫 state.json、
// 都過關，同一個 stack 跑兩個 daemon（實測一個死在 state.json.tmp 互搶、活下來的那個 state.json 記著死掉那個的 pid，再起第三個也擋不住）。
// stack 打不開（不在）＝不鎖，後面寫窗時照各自的錯。
// 11-06（no-pid P1）：fork 出來的子行程一律先關掉這把鎖（pthread_atfork）。O_CLOEXEC 只管 exec：不 exec 的子（exec 型 proc 是單子、
// 身體是單子＝子行程內 run_inst）原本一直帶著鎖，daemon 被 kill -9 後新 daemon 要等它跑完才拿得到（DaemonExists）。
// 身體的 fork 在 aos-loop 的 run_folder、run_child 管不到，所以掛在每次 fork 上；close 是 async-signal-safe。
static int g_lock_fd = -1;
static void close_lock_in_child() {
    if (g_lock_fd >= 0) {
        ::close(g_lock_fd);
    }
}

void Daemon::check_running() {
    int fd = ::open(stack_.c_str(), O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    if (fd < 0) {
        return;
    }
    if (::flock(fd, LOCK_EX | LOCK_NB) == 0) {
        lock_fd_ = fd;   // 一直開著到行程結束
        g_lock_fd = fd;
        pthread_atfork(nullptr, nullptr, close_lock_in_child);
        return;
    }
    ::close(fd);
    // 11-06（no-pid P1）：鎖不到已證明對方活著，只看它 state 窗的 phase；不對 /proc、不印 pid（只有 daemon 管自己的子才碰 pid）
    std::optional<Json> st = state_path_.empty() ? std::nullopt : aos::read_json(state_path_);
    bool closing = st && st->is_object() && st->value("phase", Json()) == "stopping";
    if (closing) {   // 11-05 第二輪：收工途中（等子項退，最多約 10 秒）叫人「沿用」是錯的
        throw Error{code::DaemonExists, "the daemon on this stack (" + stack_ + ") is shutting down; start again after it exits"};
    }
    throw Error{code::DaemonExists, "a daemon is already running on this stack (" + stack_ + "); to reuse it, just aos-daemon-ctl add / aos-agent ctl add"};
}


}  // namespace aos::daemon
