// serve.cpp：【serve】kernel 跑一次（說明見 serve.hpp）。
#include "serve/serve.hpp"

#include "queue/queue.hpp"

#include "aos/exec.hpp"
#include "aos/files.hpp"
#include "aos/proc.hpp"

#include <algorithm>
#include <cerrno>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <map>
#include <signal.h>

#include <fcntl.h>
#include <sys/file.h>
#include <sys/wait.h>
#include <unistd.h>

namespace fs = std::filesystem;

namespace aos::kernel_llm {

Cfg read_cfg(const std::string& spec, const std::string& stack) {
    Json doc = aos::load_cfg(spec);
    std::string base = aos::dirname(aos::abspath(aos::split_hash(spec).path));
    doc = aos::loop::resolve_keys(doc, base, {"mailbox", "slots", "budget", "accept"}).value;
    if (!doc.is_object()) {
        throw Error{code::CfgBad, spec + " 要是 JSON 物件"};
    }
    Cfg c;
    Json m = doc.value("mailbox", Json());
    std::string mailbox = "mailbox";
    if (!m.is_null()) {
        if (!m.is_string() || m.get<std::string>().empty()) {
            throw Error{code::CfgBad, "mailbox 要是非空字串（信箱資料夾，相對的從 $AOS_STACK 算），不是 " + aos::dumps(m)};
        }
        mailbox = m.get<std::string>();
    }
    c.mailbox = aos::join(stack, mailbox);
    Json s = doc.value("slots", Json());
    if (!s.is_null()) {
        if (!aos::is_count(s) || s.get<long long>() < 1) {
            throw Error{code::CfgBad, "slots 要是正整數（同時跑幾封），不是 " + aos::dumps(s)};
        }
        c.slots = s.get<long long>();
    }
    c.budget = parse_budget(doc.value("budget", Json()));
    Json a = doc.value("accept", Json());
    if (!a.is_null()) {
        const std::string bad = "accept 要是 [{\"argv\": 非空字串陣列, \"cwd\": 字串}, …]，不是 " + aos::dumps(a);
        if (!a.is_array()) {
            throw Error{code::CfgBad, bad};
        }
        std::vector<Accepted> list;
        for (const Json& e : a) {
            if (!e.is_object() || !e.value("argv", Json()).is_array() || e["argv"].empty() ||
                !e.value("cwd", Json()).is_string() || e["cwd"].get<std::string>().empty()) {
                throw Error{code::CfgBad, bad};
            }
            Accepted one;
            for (const Json& x : e["argv"]) {
                if (!x.is_string()) {
                    throw Error{code::CfgBad, bad};
                }
                one.argv.push_back(x.get<std::string>());
            }
            one.cwd = aos::abspath(aos::join(base, e["cwd"].get<std::string>()));
            list.push_back(one);
        }
        c.accept = list;
    }
    return c;
}

namespace {

// 資料夾裡的名字（不含 . 開頭的），照字典序。
std::vector<std::string> names_in(const std::string& dir) {
    std::vector<std::string> out;
    std::error_code ec;
    for (const fs::directory_entry& e : fs::directory_iterator(dir, ec)) {
        std::string n = e.path().filename().string();
        if (!n.empty() && n[0] != '.') {
            out.push_back(n);
        }
    }
    std::sort(out.begin(), out.end());
    return out;
}

void make_dir(const std::string& dir) {
    std::error_code ec;
    fs::create_directories(dir, ec);
    if (ec || !fs::is_directory(dir)) {
        throw Error{code::MkdirFailed, "建不了 " + dir + (ec ? "：" + ec.message() : "")};
    }
}

// 改名；改不成回 false（ENOENT＝別人先改了）。
bool move(const std::string& from, const std::string& to) {
    return std::rename(from.c_str(), to.c_str()) == 0;
}

void remove_tree(const std::string& p) {
    std::error_code ec;
    fs::remove_all(p, ec);
}

void write_reply(const std::string& dir, const Json& reply) {
    std::optional<std::string> err = aos::write_json(aos::join(dir, "reply.json"), reply);
    if (err) {
        throw Error{code::WriteFailed, *err};
    }
}

Json error_reply(const std::string& c, const std::string& msg) {
    Json e = Json::object();
    e["code"] = c;
    e["msg"] = msg;
    Json r = Json::object();
    r["error"] = e;
    return r;
}

struct Served {
    std::string served_at;   // 這封信被處理的時間（認領、回錯、或接手上一次留下的；10-25 前叫 at）
    std::string id;
    Json level;          // "low"／"normal"／"high" 或 null（讀不懂信）
    Json waited_runs;    // 或 null
    Json reply;
    unsigned long long elapsed_ms = 0;
    Json time_ms = nullptr;                    // `_metainfo` 宣告的 time_ms（val；沒寫＝null）
    Json metainfo_bad = Json::array();         // 寫壞而當沒寫的 `_metainfo` key
};

// accept 名單（10-24）：單子的 argv 與 cwd 跟其中一張一字不差，而且沒自帶串流與 envs。
bool accepted(const std::vector<Accepted>& list, const Json& inst) {
    for (const char* k : {"envs", "stdin", "stdout", "stderr", "stdout_append", "stderr_append"}) {
        Json v = inst.value(k, Json());
        if (!v.is_null() && v != Json(false)) {
            return false;
        }
    }
    Json cwd = inst.value("cwd", Json());
    Json argv = inst.value("argv", Json());
    if (!cwd.is_string() || !argv.is_array()) {
        return false;
    }
    for (const Accepted& a : list) {
        if (aos::abspath(cwd.get<std::string>()) == a.cwd && argv == Json(a.argv)) {
            return true;
        }
    }
    return false;
}

// 跑過的（子行程起來過＝cur/<id>/runner.json 在）才算一次、才看回報；沒跑的（LetterBad、DeadlineMissed、BudgetMissing）不算。
bool ran(const std::string& dir) {
    std::error_code ec;
    return fs::exists(aos::join(dir, "runner.json"), ec);
}

class Server {
public:
    Server(const Cfg& cfg, const std::string& stack)
        : mb_{cfg.mailbox}, slots_(cfg.slots), budget_(cfg.budget), accept_(cfg.accept), stack_(stack) {}
    ~Server() {
        if (lock_fd_ >= 0) {
            close(lock_fd_);
        }
    }
    Server(const Server&) = delete;
    Server& operator=(const Server&) = delete;

    int run();

private:
    Mailbox mb_;
    long long slots_;
    Budget budget_;
    std::optional<std::vector<Accepted>> accept_;
    std::string stack_;
    int lock_fd_ = -1;
    Queue q_;
    Used used_;
    int got_ = 0;
    long long busy_ = 0;   // cur/ 裡上一次 kernel 留下、還在跑的

    void lock();
    void recover();
    void sweep();
    std::vector<Waiting> scan();
    void refuse(const std::string& id, const Json& level, const Json& reply, const Json& waited = nullptr);
    void finish(const Served& s);
    pid_t start_runner(const Waiting& w);
    void wait_runners(std::map<pid_t, Served>& running);
};

// cur/<id>/runner.json（跑信的子行程一起來就寫）記的那個行程還在不在。
bool runner_alive(const std::string& dir) {
    std::optional<Json> r = aos::read_json(aos::join(dir, "runner.json"));
    if (!r || !r->is_object() || !aos::is_count(r->value("pid", Json())) ||
        !r->value("started_at_ticks", Json()).is_number_integer()) {
        return false;
    }
    std::optional<long long> now = aos::proc_started_at_ticks((pid_t)(*r)["pid"].get<long long>());
    return now && *now == (*r)["started_at_ticks"].get<long long>();
}

void Server::lock() {
    std::string path = aos::join(mb_.root, ".flock");   // 10-29 改名（原 .lock；.lock/ 留給 N-15 的資料夾鎖）
    lock_fd_ = open(path.c_str(), O_RDWR | O_CREAT | O_CLOEXEC, 0644);
    if (lock_fd_ < 0) {
        throw Error{code::LockFailed, "開不了 " + path + "：" + std::strerror(errno)};
    }
    if (flock(lock_fd_, LOCK_EX | LOCK_NB) != 0) {
        throw Error{code::LockFailed, "信箱 " + mb_.root + " 被另一個 kernel 鎖著（同一個信箱同時只能一個 kernel）"};
    }
}

// served.jsonl 一行、cur → done（reply.json 已在 cur/<id>/ 裡）。
void Server::finish(const Served& s) {
    Json line = Json::object();
    line["served_at"] = s.served_at;
    line["letter"] = s.id;
    line["level"] = s.level;
    line["counter_waited_runs"] = s.waited_runs;
    Json code = nullptr;
    Json signal = nullptr;
    Json error = nullptr;
    if (s.reply.contains("error")) {
        error = s.reply["error"]["code"];
    } else {
        code = s.reply["code"];
        signal = s.reply["signal"];
    }
    line["code"] = code;
    line["signal"] = signal;
    line["error"] = error;
    line["elapsed_ms"] = s.elapsed_ms;
    line["time_ms"] = s.time_ms;
    line["metainfo_bad"] = s.metainfo_bad;
    std::string dir = aos::join(mb_.cur(), s.id);
    bool counted = ran(dir);
    Report rep;
    if (counted) {
        rep = read_report(aos::join(dir, "report.json"));   // 腦願意寫才有（AOS_KERNEL_REPORT）；沒寫＝只算次數
    }
    line["counter_tokens"] = rep.tokens;
    line["report_bad"] = rep.bad;
    std::string path = aos::join(stack_, "served.jsonl");
    std::FILE* f = std::fopen(path.c_str(), "a");
    if (f == nullptr) {
        throw Error{code::WriteFailed, "寫不了 " + path + "：" + std::strerror(errno)};
    }
    std::string text = aos::dumps(line) + "\n";
    bool ok = std::fwrite(text.data(), 1, text.size(), f) == text.size();
    if (std::fclose(f) != 0 || !ok) {
        throw Error{code::WriteFailed, "寫不了 " + path};
    }
    if (counted) {
        add_used(stack_, used_, rep);
    }
    std::string from = aos::join(mb_.cur(), s.id);
    std::string to = aos::join(mb_.done(), s.id);
    if (!move(from, to)) {
        throw Error{code::WriteFailed, "改名不了 " + from + " → " + to + "：" + std::strerror(errno)};
    }
}

// cur/ 裡留下的＝上一次 kernel 跑到一半死了（一次跑完才結束，而且有鎖，所以這時 cur/ 不該有東西）。
void Server::recover() {
    for (const std::string& id : names_in(mb_.cur())) {
        std::string dir = aos::join(mb_.cur(), id);
        Served s;
        s.served_at = aos::utc_now_ms();
        s.id = id;
        s.level = nullptr;
        s.waited_runs = nullptr;
        std::optional<Json> letter = aos::read_json(aos::join(dir, "letter.json"));
        if (letter && letter->is_object()) {
            try {
                s.level = level_name(priority_of(*letter).level);
            } catch (const Error&) {
            }
        }
        std::optional<Json> reply = read_reply(aos::join(dir, "reply.json"));
        if (reply) {
            s.reply = *reply;   // 跑完、回信寫好了，只差搬 done/
        } else if (runner_alive(dir)) {
            ++busy_;   // 上一次 kernel 死了、跑信的子行程還活著：讓它跑完（佔一格），回信寫好後下一次再搬
            continue;
        } else {
            s.reply = error_reply(code::RunFailed, "上一次 kernel 跑這封信跑到一半停了，沒有回信（單子可能還在跑或跑了一半）");
            write_reply(dir, s.reply);
        }
        finish(s);
    }
}

// 寄信的人不在了的（<信>/sender.flock 沒人鎖著）：tmp/、done/ 直接刪；new/ 先改名回 tmp/ 再刪（跟閘門撤信同一個做法，不會跟認領撞）。
// tmp/ 裡 . 開頭的＝閘門正在寫：鎖檔在而沒人鎖著才刪（還沒建鎖檔的那一瞬間不碰）。
void Server::sweep() {
    std::vector<std::string> tmps;
    std::error_code ec;
    for (const fs::directory_entry& e : fs::directory_iterator(mb_.tmp(), ec)) {
        tmps.push_back(e.path().filename().string());
    }
    for (const std::string& n : tmps) {
        std::string dir = aos::join(mb_.tmp(), n);
        bool writing = !n.empty() && n[0] == '.';
        if (writing && !fs::exists(aos::join(dir, "letter.json"), ec)) {
            continue;   // 閘門鎖好才寫 letter.json：還沒有＝可能正在建鎖檔、上鎖，不碰
        }
        if (!sender_alive(dir)) {
            remove_tree(dir);
        }
    }
    for (const std::string& id : names_in(mb_.done())) {
        std::string dir = aos::join(mb_.done(), id);
        if (!sender_alive(dir)) {
            remove_tree(dir);
        }
    }
    for (const std::string& id : names_in(mb_.fresh())) {
        if (!sender_alive(aos::join(mb_.fresh(), id))) {
            std::string t = aos::join(mb_.tmp(), id);
            if (move(aos::join(mb_.fresh(), id), t)) {
                remove_tree(t);
            }
        }
    }
}

// 不跑、直接回信（LetterBad、DeadlineMissed、BudgetMissing）：先認領，認領不到＝閘門剛撤信，算了。
void Server::refuse(const std::string& id, const Json& level, const Json& reply, const Json& waited) {
    std::string dir = aos::join(mb_.cur(), id);
    if (!move(aos::join(mb_.fresh(), id), dir)) {
        return;
    }
    write_reply(dir, reply);
    Served s;
    s.served_at = aos::utc_now_ms();
    s.id = id;
    s.level = level;
    s.waited_runs = waited;
    s.reply = reply;
    finish(s);
}

std::vector<Waiting> Server::scan() {
    std::vector<Waiting> ws;
    double now = std::chrono::duration<double>(std::chrono::system_clock::now().time_since_epoch()).count();
    Json seen = Json::object();
    for (const std::string& id : names_in(mb_.fresh())) {
        std::string path = aos::join(aos::join(mb_.fresh(), id), "letter.json");
        std::optional<Json> letter = aos::read_json(path);
        if (!letter || !letter->is_object() || !letter->value("inst", Json()).is_object() ||
            !letter->value("env", Json::object()).is_object()) {
            refuse(id, nullptr, error_reply(code::LetterBad, "信讀不懂：letter.json 要是 {\"inst\": 單子物件, \"env\": {…}, \"priority\": …}"));
            continue;
        }
        Waiting w;
        w.id = id;
        w.letter = *letter;
        try {
            w.priority = priority_of(*letter);
        } catch (const Error& e) {
            refuse(id, nullptr, error_reply(code::LetterBad, "信的 " + e.msg));
            continue;
        }
        if (accept_ && !accepted(*accept_, w.letter["inst"])) {
            refuse(id, level_name(w.priority.level),
                   error_reply(code::InstUnknown, "這張單子不在 kernel.json 的 accept 名單裡（argv、cwd 要一字不差，不能自帶 envs 與串流），沒跑"));
            continue;
        }
        if (w.priority.deadline && *w.priority.deadline < now) {
            refuse(id, level_name(w.priority.level), error_reply(code::DeadlineMissed, "輪到之前時限已過，沒跑"));
            continue;
        }
        w.seen_at_runs = q_.runs;
        Json old = q_.seen_at_runs.value(id, Json());
        if (aos::is_count(old)) {
            w.seen_at_runs = old.get<long long>();
        }
        seen[id] = w.seen_at_runs;
        ws.push_back(w);
    }
    q_.seen_at_runs = seen;   // 只留還在排的
    return ws;
}

pid_t Server::start_runner(const Waiting& w) {
    std::string dir = aos::join(mb_.cur(), w.id);
    Json inst = w.letter["inst"];
    if (inst.value("stdout", Json()).is_null()) {
        inst["stdout"] = aos::join(dir, "stdout.txt");
    }
    if (inst.value("stderr", Json()).is_null()) {
        inst["stderr"] = aos::join(dir, "stderr.txt");
    }
    if (inst.value("stdin", Json()).is_null()) {
        inst["stdin"] = "/dev/null";   // 閘門不轉自己的 stdin
    }
    Json env = w.letter.value("env", Json::object());
    std::fflush(nullptr);
    pid_t pid = fork();
    if (pid < 0) {
        throw Error{code::LaunchFailed, "fork 失敗：" + std::string(std::strerror(errno))};
    }
    if (pid > 0) {
        return pid;
    }
    // 子行程：只跑這一封
    close(lock_fd_);   // 鎖只留在 kernel 本身（子行程拿著的話 kernel 死了鎖也不放）
    if (!accept_) {
        clearenv();   // 照舊：環境整份換成寄信那一刻的（閘門透明，C-20）
    }
    for (auto& [k, v] : env.items()) {
        if (v.is_string() && (!accept_ || k.rfind("AOS_", 0) == 0)) {   // 有 accept：只疊信裡 AOS_ 開頭的，其他用 kernel 自己的
            setenv(k.c_str(), v.get<std::string>().c_str(), 1);
        }
    }
    setenv("AOS_KERNEL_REPORT", aos::join(dir, "report.json").c_str(), 1);   // 腦願意就把 API 回覆的 usage 寫進去（10-24）
    Json me = Json::object();   // 先記下自己（kernel 本體死了、自己還活著時，下一次 kernel 看這個不去搶）
    me["pid"] = (long long)getpid();
    me["started_at_ticks"] = aos::proc_started_at_ticks(0).value_or(-1);
    aos::write_json(aos::join(dir, "runner.json"), me);
    Json reply = Json::object();
    try {
        aos::exec::Result r = aos::exec::run_inst(inst, "/", {}, "/");
        reply["code"] = r.code;
        reply["signal"] = nullptr;
        if (r.signal != 0) {
            reply["signal"] = r.signal;
        }
    } catch (const Error& e) {
        reply = error_reply(e.code, "單子跑不起來：" + e.msg);
    } catch (const std::exception& e) {
        reply = error_reply(code::Internal, e.what());
    }
    std::optional<std::string> err = aos::write_json(aos::join(dir, "reply.json"), reply);
    if (err) {
        std::fprintf(stderr, "aos-kernel-llm: WriteFailed %s\n", err->c_str());
        std::fflush(stderr);
    }
    _exit(0);
}

void Server::wait_runners(std::map<pid_t, Served>& running) {
    using Clock = std::chrono::steady_clock;
    std::map<pid_t, Clock::time_point> started;
    for (auto& [pid, s] : running) {
        started[pid] = Clock::now();
    }
    std::map<pid_t, int> statuses;
    std::vector<pid_t> left;
    for (auto& [pid, s] : running) {
        left.push_back(pid);
    }
    sigset_t set;
    sigemptyset(&set);
    sigaddset(&set, SIGINT);
    sigaddset(&set, SIGTERM);
    sigaddset(&set, SIGHUP);
    while (!left.empty()) {
        std::vector<pid_t> still;
        for (pid_t pid : left) {
            int st = 0;
            pid_t r = waitpid(pid, &st, WNOHANG);
            if (r == pid) {
                statuses[pid] = st;
                long long us = std::chrono::duration_cast<std::chrono::microseconds>(Clock::now() - started[pid]).count();
                running[pid].elapsed_ms = (unsigned long long)((us + 500) / 1000);
            } else {
                still.push_back(pid);
            }
        }
        left = still;
        if (left.empty()) {
            break;
        }
        timespec ts{0, 20 * 1000 * 1000};
        int sig = sigtimedwait(&set, nullptr, &ts);
        if (sig > 0) {
            if (got_ == 0) {
                got_ = sig;
            }
            for (pid_t pid : left) {
                kill(pid, sig);   // 子行程的 run_inst 再轉給單子的整群
            }
        }
    }
    for (auto& [pid, s] : running) {
        std::string dir = aos::join(mb_.cur(), s.id);
        std::optional<Json> reply = read_reply(aos::join(dir, "reply.json"));
        if (reply) {
            s.reply = *reply;
        } else {
            int st = statuses[pid];
            std::string why = "跑這封信的子行程沒寫回信就結束了";
            if (WIFSIGNALED(st)) {
                why += "（被訊號 " + std::to_string(WTERMSIG(st)) + " 停掉）";
            }
            s.reply = error_reply(code::RunFailed, why);
            write_reply(dir, s.reply);
        }
        finish(s);
    }
}

int Server::run() {
    for (const std::string& d : {mb_.root, mb_.tmp(), mb_.fresh(), mb_.cur(), mb_.done()}) {
        make_dir(d);
    }
    lock();
    q_ = read_queue(stack_);
    q_.runs += 1;
    used_ = read_used(stack_, budget_.window);
    recover();
    sweep();
    std::vector<Waiting> ws = scan();
    order(ws, q_.runs);

    got_ = aos::loop::take_signal();
    std::map<pid_t, Served> running;
    if (got_ == 0) {
        long long n = 0;
        for (const Waiting& w : ws) {
            if (spent(budget_, used_, n + busy_)) {   // 這一窗額度到頂
                if (budget_.wait) {
                    break;   // 留在 new/ 等下一窗（閘門一直等，由包它那格的 timeout_ms 守）
                }
                q_.seen_at_runs.erase(w.id);
                refuse(w.id, level_name(w.priority.level),
                       error_reply(code::BudgetMissing, "這一窗（" + budget_.window + "）的額度用完了，沒跑"),
                       waited_runs(w, q_.runs));
                continue;
            }
            if (n + busy_ >= slots_) {
                break;
            }
            if (!move(aos::join(mb_.fresh(), w.id), aos::join(mb_.cur(), w.id))) {
                continue;   // 閘門剛撤信
            }
            q_.seen_at_runs.erase(w.id);
            Served s;
            s.served_at = aos::utc_now_ms();
            s.id = w.id;
            s.level = level_name(w.priority.level);
            s.waited_runs = waited_runs(w, q_.runs);
            if (w.priority.time_ms) {
                double v = *w.priority.time_ms;
                s.time_ms = v;
                if (v == std::floor(v) && v < 9e15) {
                    s.time_ms = (long long)v;   // 整數就印整數（800，不是 800.0）
                }
            }
            for (const std::string& k : w.priority.metainfo_bad) {
                s.metainfo_bad.push_back(k);
            }
            pid_t pid = 0;
            try {
                pid = start_runner(w);
            } catch (const Error& e) {
                Json reply = error_reply(e.code, e.msg);
                write_reply(aos::join(mb_.cur(), w.id), reply);
                s.reply = reply;
                finish(s);
                continue;
            }
            running[pid] = s;
            ++n;
        }
        wait_runners(running);
    }
    write_queue(stack_, q_);
    if (got_ != 0) {
        return 128 + got_;
    }
    return 0;
}

}  // namespace

int serve(const Cfg& cfg, const std::string& stack) {
    Server s(cfg, stack);
    return s.run();
}

}  // namespace aos::kernel_llm
