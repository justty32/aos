// serve.cpp：【serve】kernel 跑一次（說明見 serve.hpp）。
#include "serve/serve.hpp"

#include "queue/queue.hpp"

#include "aos/exec.hpp"
#include "aos/post.hpp"
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

namespace aos::llm_kernel {

// aos-exec 目標（資料夾、檔、`檔#/指標`）：相對的從 base 算、轉成絕對（信資料夾裡跑的 aos-exec 才找得到）。
static std::string target_abs(const std::string& t, const std::string& base) {
    aos::Spec sp = aos::split_hash(t);
    std::string p = aos::abspath(aos::join(base, sp.path));
    if (sp.pointer.empty()) {
        return p;
    }
    return p + "#" + sp.pointer;
}

Cfg read_cfg(const std::string& spec, const std::string& stack) {
    Json doc = aos::load_cfg(spec);
    std::string base = aos::dirname(aos::abspath(aos::split_hash(spec).path));
    aos::Resolved r = aos::loop::resolve_keys(doc, base, {"mailbox", "slots", "budget", "exec", "endpoint", "timeout_ms"});
    doc = r.value;
    if (!doc.is_object()) {
        throw Error{code::CfgBad, spec + " 要是 JSON 物件"};
    }
    Cfg c;
    c.base = base;
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
    Json ex = doc.value("exec", Json());
    if (!ex.is_string() || ex.get<std::string>().empty()) {
        throw Error{code::CfgBad, "exec 要是非空字串（endpoint 函數：資料夾、檔或 `檔#/指標`，相對的從 kernel.json 的資料夾算），不是 " + aos::dumps(ex)};
    }
    c.exec = target_abs(ex.get<std::string>(), base);
    if (!doc.contains("endpoints")) {
        throw Error{code::CfgBad, "沒寫 endpoints（代號 → 一組 llm 設定）"};
    }
    aos::Resolved eps = aos::resolve_shallow(doc["endpoints"], r.dir_of("endpoints"));
    if (!eps.value.is_object() || eps.value.empty()) {
        throw Error{code::CfgBad, "endpoints 要是非空物件（代號 → 一組 llm 設定），不是 " + aos::dumps(eps.value)};
    }
    c.endpoints = eps.value;
    for (auto& [k, v] : c.endpoints.items()) {
        c.endpoint_dirs[k] = eps.dir_of(k);
    }
    Json ep = doc.value("endpoint", Json());
    if (!ep.is_null()) {
        if (!ep.is_string() || !c.endpoints.contains(ep.get<std::string>())) {
            throw Error{code::CfgBad, "endpoint（預設代號）要是 endpoints 表裡的一個代號，不是 " + aos::dumps(ep)};
        }
        c.endpoint = ep.get<std::string>();
    }
    Json t = doc.value("timeout_ms", Json());
    if (!t.is_null()) {
        if (!aos::is_count(t)) {
            throw Error{code::CfgBad, "timeout_ms 要是非負整數（跑 endpoint 函數的上限），不是 " + aos::dumps(t)};
        }
        c.timeout_ms = t.get<long long>();
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
    Json endpoint = nullptr;   // 用的代號（查出來之前就回錯＝null）
    Json reply;
    unsigned long long elapsed_ms = 0;
};

// 回信走 reply_to（10-30，medium 決定 3、N-16）：信裡寫了 reply_to＝照 N-16 寄一封回信進去（body＝reply.json 那份、
// in_reply_to＝原信的信件名稱；11-04 起不附檔），寄出的信件名稱記在 <信>/reply_letter.txt（已經有＝上一次寄過了，不寄第二封）。
// 寄不出去（信箱不在、寫不進）不是 kernel 的錯：回「代號 原因」記進 served 的 reply_error，信照搬 done/。沒寫 reply_to＝null。
Json post_reply(const std::string& dir, const std::string& id, const Json& reply) {
    std::optional<Json> letter = aos::read_json(aos::join(dir, "letter.json"));
    if (!letter || !letter->is_object() || !letter->value("reply_to", Json()).is_string()) {
        return nullptr;
    }
    std::error_code ec;
    if (fs::exists(aos::join(dir, "reply_letter.txt"), ec)) {
        return nullptr;
    }
    try {
        aos::post::Mailbox box = aos::post::open((*letter)["reply_to"].get<std::string>());
        aos::post::SendOpts opts;
        opts.in_reply_to = id;
        std::string sig = aos::post::send(box, reply, opts);
        std::string tmp = aos::join(dir, ".reply_letter.txt.tmp");   // N-05
        std::FILE* f = std::fopen(tmp.c_str(), "w");
        if (f == nullptr || std::fprintf(f, "%s\n", sig.c_str()) < 0 || std::fclose(f) != 0 ||
            std::rename(tmp.c_str(), aos::join(dir, "reply_letter.txt").c_str()) != 0) {
            return std::string(code::WriteFailed) + " 回信寄出了（" + sig + "），但記不進 " + dir + "/reply_letter.txt";
        }
        return nullptr;
    } catch (const Error& e) {
        return e.code + " " + e.msg;
    }
}

// done/<id> 被收拾前：它寄過的回信還在 reply_to 的 new/（寄信的人不在了，沒人會拿）＝撤回自己寄的那封（N-16 撤回；在 cur/ 以後的不碰）。
void regret_reply(const std::string& dir) {
    std::optional<Json> letter = aos::read_json(aos::join(dir, "letter.json"));
    int err = 0;
    std::optional<std::string> sig = aos::read_file(aos::join(dir, "reply_letter.txt"), err);
    if (!letter || !letter->is_object() || !letter->value("reply_to", Json()).is_string() || !sig) {
        return;
    }
    std::string name = *sig;
    while (!name.empty() && (name.back() == '\n' || name.back() == ' ')) {
        name.pop_back();
    }
    if (name.empty() || name[0] == '.' || name.find('/') != std::string::npos) {
        return;
    }
    try {
        aos::post::regret(aos::post::open((*letter)["reply_to"].get<std::string>()), name);
    } catch (const Error&) {
    }
}

// 跑過的（子行程起來過＝cur/<id>/runner.json 在）才算一次、才看 usage；沒跑的（LetterBad、EndpointUnknown、DeadlineMissed、BudgetMissing…）不算。
bool ran(const std::string& dir) {
    std::error_code ec;
    return fs::exists(aos::join(dir, "runner.json"), ec);
}

class Server {
public:
    Server(const Cfg& cfg, const std::string& stack)
        : cfg_(cfg), mb_{cfg.mailbox}, slots_(cfg.slots), budget_(cfg.budget), stack_(stack) {}
    ~Server() {
        if (lock_fd_ >= 0) {
            close(lock_fd_);
        }
    }
    Server(const Server&) = delete;
    Server& operator=(const Server&) = delete;

    int run();

private:
    const Cfg& cfg_;
    Mailbox mb_;
    long long slots_;
    Budget budget_;
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
    void refuse(const std::string& id, const Json& level, const Json& reply, const Json& waited = nullptr,
                const Json& endpoint = nullptr);
    std::optional<Json> pick(Waiting& w);
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

// served.jsonl 一行、刪 request.json（含金鑰，04 #13）、cur → done（reply.json 已在 cur/<id>/ 裡）。
void Server::finish(const Served& s) {
    Json line = Json::object();
    line["served_at"] = s.served_at;
    line["letter"] = s.id;
    line["level"] = s.level;
    line["counter_waited_runs"] = s.waited_runs;
    line["endpoint"] = s.endpoint;
    Json error = nullptr;
    Json model = nullptr;
    if (s.reply.contains("error")) {
        error = s.reply["error"]["code"];
    } else if (s.reply.value("model", Json()).is_string()) {
        model = s.reply["model"];
    }
    line["model"] = model;
    line["error"] = error;
    line["elapsed_ms"] = s.elapsed_ms;
    std::string dir = aos::join(mb_.cur(), s.id);
    bool counted = ran(dir);
    Report rep;
    if (counted) {
        rep = report_of(s.reply);   // usage 從回信拿（11-04 起；沒有＝只算次數）
    }
    line["counter_tokens"] = rep.tokens;
    line["usage_bad"] = rep.bad;
    line["reply_error"] = post_reply(dir, s.id, s.reply);   // 回信走 reply_to（10-30）
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
    std::error_code ec;
    fs::remove(aos::join(dir, "request.json"), ec);
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
            Json body = letter->value("body", Json());
            if (body.is_object() && body.value("endpoint", Json()).is_string()) {
                s.endpoint = body["endpoint"];
            } else if (cfg_.endpoint) {
                s.endpoint = *cfg_.endpoint;
            }
        }
        std::optional<Json> reply = read_reply(aos::join(dir, "reply.json"));
        if (reply) {
            s.reply = *reply;   // 跑完、回信寫好了，只差搬 done/
        } else if (runner_alive(dir)) {
            ++busy_;   // 上一次 kernel 死了、跑信的子行程還活著：讓它跑完（佔一格），回信寫好後下一次再搬
            continue;
        } else {
            s.reply = error_reply(code::RunFailed, "上一次 kernel 跑這封信跑到一半停了，沒有回信（endpoint 函數可能還在跑或跑了一半）");
            write_reply(dir, s.reply);
        }
        finish(s);
    }
}

// 寄信的人不在了的（<信>/sender.flock 在、但沒人鎖著）：tmp/、done/ 直接刪；new/ 先改名回 tmp/ 再刪（跟撤信同一個做法，不會跟認領撞）。
// 沒有 sender.flock＝非同步寄的（aos-llm send、aos-post send）或還在建鎖檔：不判存活、不碰（11-04 衝突 2 (a)）。
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
            continue;   // ask 鎖好才寫 letter.json：還沒有＝可能正在建鎖檔、上鎖，不碰
        }
        if (has_sender(dir) && !sender_alive(dir)) {
            remove_tree(dir);
        }
    }
    for (const std::string& id : names_in(mb_.done())) {
        std::string dir = aos::join(mb_.done(), id);
        if (has_sender(dir) && !sender_alive(dir)) {
            regret_reply(dir);   // 它寄過、沒人拿的回信撤回（10-30；aos-post regret）
            remove_tree(dir);
        }
    }
    for (const std::string& id : names_in(mb_.fresh())) {
        std::string dir = aos::join(mb_.fresh(), id);
        if (has_sender(dir) && !sender_alive(dir)) {
            std::string t = aos::join(mb_.tmp(), id);
            if (move(dir, t)) {
                remove_tree(t);
            }
        }
    }
}

// 不跑、直接回信（LetterBad、RequestBad、Endpoint*、DeadlineMissed、BudgetMissing…）：先認領，認領不到＝寄信的剛撤信，算了。
void Server::refuse(const std::string& id, const Json& level, const Json& reply, const Json& waited, const Json& endpoint) {
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
    s.endpoint = endpoint;
    s.reply = reply;
    finish(s);
}

// 查代號、解那組的指示詞、定 exec（填進 w）；查不到或那組壞了＝回那封信的 error 回信。
std::optional<Json> Server::pick(Waiting& w) {
    const Json& body = w.letter["body"];
    if (body.contains("endpoint")) {
        w.endpoint = body["endpoint"].get<std::string>();
    } else if (cfg_.endpoint) {
        w.endpoint = *cfg_.endpoint;
    } else {
        return error_reply(code::EndpointMissing, "信沒寫 endpoint（代號），kernel.json 也沒寫預設的 endpoint");
    }
    if (!cfg_.endpoints.contains(w.endpoint)) {
        return error_reply(code::EndpointUnknown, "代號 " + w.endpoint + " 不在 kernel.json 的 endpoints 表裡");
    }
    Json g;
    try {
        g = aos::resolve(cfg_.endpoints[w.endpoint], cfg_.endpoint_dirs.at(w.endpoint));
    } catch (const Error& e) {
        return error_reply(e.code, "kernel.json 的 endpoints." + w.endpoint + "：" + e.msg);
    }
    if (!g.is_object()) {
        return error_reply(code::CfgBad, "kernel.json 的 endpoints." + w.endpoint + " 要是物件（一組 llm 設定），不是 " + aos::dumps(g));
    }
    w.exec = cfg_.exec;
    if (g.contains("exec")) {
        if (!g["exec"].is_string() || g["exec"].get<std::string>().empty()) {
            return error_reply(code::CfgBad, "kernel.json 的 endpoints." + w.endpoint + ".exec 要是非空字串，不是 " + aos::dumps(g["exec"]));
        }
        w.exec = target_abs(g["exec"].get<std::string>(), cfg_.base);
        g.erase("exec");
    }
    w.group = g;
    return std::nullopt;
}

std::vector<Waiting> Server::scan() {
    std::vector<Waiting> ws;
    double now = std::chrono::duration<double>(std::chrono::system_clock::now().time_since_epoch()).count();
    Json seen = Json::object();
    for (const std::string& id : names_in(mb_.fresh())) {
        std::string path = aos::join(aos::join(mb_.fresh(), id), "letter.json");
        std::optional<Json> letter = aos::read_json(path);
        if (!letter || !letter->is_object() || !letter->value("body", Json()).is_object() ||
            !(*letter)["body"].contains("request")) {
            std::string why = "信讀不懂：letter.json 要是 N-16 的信，body＝{\"endpoint\"?: 代號, \"request\": {...}, \"priority\"?}";
            if (letter && letter->is_object() && letter->contains("inst")) {
                why += "（頂層 inst／env 是 11-04 以前閘門的信，不再認）";
            }
            refuse(id, nullptr, error_reply(code::LetterBad, why));
            continue;
        }
        const Json& body = (*letter)["body"];
        if (body.contains("endpoint") && !body["endpoint"].is_string()) {
            refuse(id, nullptr, error_reply(code::LetterBad, "信的 body.endpoint 要是字串（代號），不是 " + aos::dumps(body["endpoint"])));
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
        Json level = level_name(w.priority.level);
        const Json& req = body["request"];
        if (!req.is_object() || !req.value("messages", Json()).is_array()) {
            refuse(id, level, error_reply(code::RequestBad, "body.request 要是物件、messages 要是陣列"));
            continue;
        }
        if (req.contains("stream") && !req["stream"].is_null() && req["stream"] != Json(false)) {
            refuse(id, level, error_reply(code::RequestBad, "串流不做：request 不能寫 stream: true"));
            continue;
        }
        std::optional<Json> bad = pick(w);
        if (bad) {
            Json ep = nullptr;
            if (!w.endpoint.empty()) {
                ep = w.endpoint;
            }
            refuse(id, level, *bad, nullptr, ep);
            continue;
        }
        if (w.priority.deadline && *w.priority.deadline < now) {
            refuse(id, level, error_reply(code::DeadlineMissed, "輪到之前時限已過，沒跑"), nullptr, w.endpoint);
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

// stderr.txt 的第一行（沒有＝空）。
std::string first_line(const std::string& path) {
    int err = 0;
    std::optional<std::string> t = aos::read_file(path, err);
    if (!t) {
        return "";
    }
    size_t n = t->find('\n');
    return n == std::string::npos ? *t : t->substr(0, n);
}

pid_t Server::start_runner(const Waiting& w) {
    std::string dir = aos::join(mb_.cur(), w.id);
    Json req = Json::object();
    req["endpoint"] = w.group;
    req["request"] = w.letter["body"]["request"];
    std::optional<std::string> werr = aos::write_json(aos::join(dir, "request.json"), req);
    if (werr) {
        throw Error{code::WriteFailed, *werr};
    }
    Json inst = Json::object();
    inst["argv"] = Json::array({"aos-exec", "--stack", dir + "/", w.exec});
    inst["cwd"] = dir;
    inst["stdin"] = aos::join(dir, "request.json");
    inst["stdout"] = aos::join(dir, "reply.json");
    inst["stderr"] = aos::join(dir, "stderr.txt");
    if (cfg_.timeout_ms) {
        inst["timeout_ms"] = *cfg_.timeout_ms;
    }
    std::fflush(nullptr);
    pid_t pid = fork();
    if (pid < 0) {
        throw Error{code::LaunchFailed, "fork 失敗：" + std::string(std::strerror(errno))};
    }
    if (pid > 0) {
        return pid;
    }
    // 子行程：只跑這一封（環境照 kernel 自己的，不換）
    close(lock_fd_);   // 鎖只留在 kernel 本身（子行程拿著的話 kernel 死了鎖也不放）
    Json me = Json::object();   // 先記下自己（kernel 本體死了、自己還活著時，下一次 kernel 看這個不去搶）
    me["pid"] = (long long)getpid();
    me["started_at_ticks"] = aos::proc_started_at_ticks(0).value_or(-1);
    aos::write_json(aos::join(dir, "runner.json"), me);
    Json reply;
    try {
        aos::exec::Result r = aos::exec::run_inst(inst, "/", {}, "/");
        if (r.code != 0 || r.signal != 0 || r.timed_out) {
            std::string why = "endpoint 函數退 " + std::to_string(r.code);
            if (r.timed_out) {
                why += "（逾時 " + std::to_string(*cfg_.timeout_ms) + " ms）";
            }
            std::string line = first_line(aos::join(dir, "stderr.txt"));
            if (!line.empty()) {
                why += "：" + line;
            }
            reply = error_reply(code::EndpointFailed, why);
        } else {
            std::optional<Json> got = read_reply(aos::join(dir, "reply.json"));
            if (got) {
                reply = *got;
            } else {
                reply = error_reply(code::ReplyBad, "endpoint 函數的 stdout 讀不懂（要是一行 {\"message\": {...}, \"usage\", \"model\"}）");
            }
        }
    } catch (const Error& e) {
        reply = error_reply(code::EndpointFailed, "endpoint 函數跑不起來：" + e.code + " " + e.msg);
    } catch (const std::exception& e) {
        reply = error_reply(code::Internal, e.what());
    }
    std::optional<std::string> err = aos::write_json(aos::join(dir, "reply.json"), reply);
    if (err) {
        std::fprintf(stderr, "aos-llm-kernel: WriteFailed %s\n", err->c_str());
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
                    break;   // 留在 new/ 等下一窗（寄信的一直等，由它自己那邊守）
                }
                q_.seen_at_runs.erase(w.id);
                refuse(w.id, level_name(w.priority.level),
                       error_reply(code::BudgetMissing, "這一窗（" + budget_.window + "）的額度用完了，沒跑"),
                       waited_runs(w, q_.runs), w.endpoint);
                continue;
            }
            if (n + busy_ >= slots_) {
                break;
            }
            if (!move(aos::join(mb_.fresh(), w.id), aos::join(mb_.cur(), w.id))) {
                continue;   // 寄信的剛撤信
            }
            q_.seen_at_runs.erase(w.id);
            Served s;
            s.served_at = aos::utc_now_ms();
            s.id = w.id;
            s.level = level_name(w.priority.level);
            s.waited_runs = waited_runs(w, q_.runs);
            s.endpoint = w.endpoint;
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

}  // namespace aos::llm_kernel
