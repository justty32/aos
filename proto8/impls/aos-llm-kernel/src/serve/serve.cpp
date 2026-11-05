// serve.cpp：【serve】kernel 跑一次（說明見 serve.hpp）。
#include "serve/serve.hpp"

#include "daemon/daemon.hpp"
#include "queue/queue.hpp"

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
    aos::Resolved r = aos::loop::resolve_keys(doc, base, {"slots", "budget", "exec", "endpoint", "timeout_ms"});
    doc = r.value;
    if (!doc.is_object()) {
        throw Error{code::CfgBad, spec + " 要是 JSON 物件"};
    }
    Cfg c;
    c.base = base;
    c.mailbox = aos::join(stack, "mailbox");   // 11-05 固定（AOS_LLM_KERNEL＝kernel 的 stack，寄信的人從 stack 算信箱）
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

// 回信走 reply_to（10-30，medium 決定 3、N-16）：信裡寫了 reply_to＝照 N-16 寄一封回信進去（body＝reply.json 那份、
// in_reply_to＝原信的信件名稱；11-04 起不附檔），寄出的信件名稱記在 <信>/reply_letter.txt（已經有＝上一次寄過了，不寄第二封）。
// 寄不出去（信箱不在、寫不進）不是 kernel 的錯：回「代號 原因」（finish 印一行到 stderr），信照刪（11-04 夜：舊信不留）。沒寫 reply_to＝null。
// reply_to 相對的（11-05 起 aos-post send 存相對信箱根）從 kernel 信箱的根 root 拼回（aos-post 的 reply_to_abs）；絕對的照用。
Json post_reply(const std::string& root, const std::string& dir, const std::string& id, const Json& reply) {
    std::optional<Json> letter = aos::read_json(aos::join(dir, "letter.json"));
    if (!letter || !letter->is_object() || !letter->value("reply_to", Json()).is_string()) {
        return nullptr;
    }
    std::error_code ec;
    if (fs::exists(aos::join(dir, "reply_letter.txt"), ec)) {
        return nullptr;
    }
    try {
        aos::post::Mailbox box =
            aos::post::open(aos::post::reply_to_abs(aos::post::Mailbox{root}, (*letter)["reply_to"].get<std::string>()));
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

// 寄完回信時寄信的人已經不在了（有 sender.flock、沒人鎖）：它寄過的回信還在 reply_to 的 new/（沒人會拿）＝撤回自己寄的那封（N-16 撤回；在 cur/ 以後的不碰）。
void regret_reply(const std::string& root, const std::string& dir) {
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
        aos::post::regret(
            aos::post::open(aos::post::reply_to_abs(aos::post::Mailbox{root}, (*letter)["reply_to"].get<std::string>())), name);
    } catch (const Error&) {
    }
}

// 問腦 proc（11-05 kernel-daemon 03）：kernel 不自己跑，請 daemon 掛成 max: 1 的 loop 型 proc。
// 掛上去的信才有 cur/<id>/proc.json＝{"name": daemon 表上的名字, "exec": endpoint 函數, "mount_letter": 掛信的信件名稱, "mounted_at": epoch 秒, "retries": 重掛過幾次}。
const char* PROC_JSON = "proc.json";

double now_s() {
    return std::chrono::duration<double>(std::chrono::system_clock::now().time_since_epoch()).count();
}

// 跑過的（掛上去過＝cur/<id>/proc.json 在）才算一次、才看 usage；沒跑的（LetterBad、EndpointUnknown、DeadlineMissed、BudgetMissing…）不算。
bool ran(const std::string& dir) {
    std::error_code ec;
    return fs::exists(aos::join(dir, PROC_JSON), ec);
}

// 檔的第一行（沒有＝空）。
std::string first_line(const std::string& path) {
    int err = 0;
    std::optional<std::string> t = aos::read_file(path, err);
    if (!t) {
        return "";
    }
    size_t n = t->find('\n');
    return n == std::string::npos ? *t : t->substr(0, n);
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
    Host host_;
    Table table_;
    long long busy_ = 0;   // 掛上去、還沒收的（在飛）

    void lock();
    void collect();
    void sweep();
    std::vector<Waiting> scan();
    void refuse(const std::string& id, const Json& reply);
    std::optional<Json> pick(Waiting& w);
    void finish(const std::string& id, const Json& reply);
    void mount(const std::string& id, const std::string& exec, Json proc);
    std::optional<Json> settle(const std::string& id, Json proc);
};

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

// 寫好 reply.json、寄回信，然後整封刪掉（cur/<id>/；11-04 夜使用者「舊信根本不用留，就是刪」）。回信寄不出去＝stderr 印一行、照刪、不退。
void Server::finish(const std::string& id, const Json& reply) {
    std::string dir = aos::join(mb_.cur(), id);
    write_reply(dir, reply);
    bool counted = ran(dir);
    Json reply_error = post_reply(mb_.root, dir, id, reply);   // 回信走 reply_to（10-30）
    if (reply_error.is_string()) {
        std::fprintf(stderr, "aos-llm-kernel: %s（信 %s 的回信寄不出去，信照刪）\n",
                     reply_error.get<std::string>().c_str(), id.c_str());
        std::fflush(stderr);
    }
    if (has_sender(dir) && !sender_alive(dir)) {
        regret_reply(mb_.root, dir);   // 同步寄的人已經走了（ask 被打斷）：回信沒人拿，撤回
    }
    if (counted) {
        add_used(stack_, used_, report_of(reply));   // usage 從回信拿（沒有＝只算次數）
    }
    remove_tree(dir);   // 刪不掉（權限）不算錯：下一次 collect 看到 reply_letter.txt 就不重寄
}

// 寄一封掛信：{"procs_added": {"llm_<id>": {"exec": 單子, "max": 1, "stack": 信資料夾}}}（03 § 1）。
// 單子的 cwd＝信資料夾（daemon 存成相對它自己的 stack），stdin／stdout 從 cwd 算＝搬家照樣對；stderr 不寫（daemon 接到 stack 的 stderr.txt）。
void Server::mount(const std::string& id, const std::string& exec, Json proc) {
    std::string dir = aos::join(mb_.cur(), id);
    std::string name = "llm_" + id;
    Json inst = Json::object();
    inst["argv"] = Json::array({"aos-exec", exec});
    inst["cwd"] = dir;
    inst["stdin"] = "request.json";
    inst["stdout"] = "reply.json";
    if (cfg_.timeout_ms) {
        inst["timeout_ms"] = *cfg_.timeout_ms;
    }
    Json spec = Json::object();
    spec["exec"] = inst;
    spec["max"] = 1;
    spec["stack"] = dir;
    Json added = Json::object();
    added[name] = spec;
    Json body = Json::object();
    body["procs_added"] = added;
    proc["name"] = name;
    proc["exec"] = exec;
    proc["mount_letter"] = send_procs(host_, body);   // 寄不進丟錯（呼叫的人回那封信 LaunchFailed）
    proc["mounted_at"] = now_s();
    if (!proc.contains("retries")) {
        proc["retries"] = 0;
    }
    std::optional<std::string> err = aos::write_json(aos::join(dir, PROC_JSON), proc);
    if (err) {
        throw Error{code::WriteFailed, *err};
    }
}

// 一封在飛的信現在怎樣（03 § 2、04 #13）：回 nullopt＝還在飛（佔一格）；回信＝收尾。
//   表上有這列：running／stopping／sleeping＝在飛；stopped 而問腦 loop 收尾了（wake 後 3 秒內跑完也會留 stopped）＝收、順手寄 procs_removed 拔列；
//              stopped 但沒收尾（有人下了 stop）＝在飛（等）
//   表上沒有：state.json 收尾了（done／stopped）＝看 code；state.json 在、沒收尾＝跑到一半死了→重掛；
//            不在＝daemon 還沒套（暫停中、還沒輪到）＝在飛，或拒了（mailbox_warning 提到這封掛信）＝LaunchFailed
std::optional<Json> Server::settle(const std::string& id, Json proc) {
    std::string dir = aos::join(mb_.cur(), id);
    std::string name = proc.value("name", "llm_" + id);
    std::optional<Json> st = aos::read_json(aos::join(dir, "state.json"));
    std::string phase = st && st->is_object() ? st->value("phase", "") : "";
    bool ended = phase == "done" || phase == "stopped";
    if (table_.procs.contains(name)) {
        const Json& row = table_.procs[name];
        if (!row.is_object() || row.value("phase", "") != "stopped" || !ended) {
            return std::nullopt;
        }
        Json rm = Json::object();
        rm["procs_removed"] = Json::array({name});
        try {
            send_procs(host_, rm);
        } catch (const Error&) {
        }
    } else if (!st) {
        std::string letter = proc.value("mount_letter", "");
        if (!letter.empty() && table_.warning.find(letter) != std::string::npos) {
            return error_reply(code::LaunchFailed, "daemon 不採用掛信：" + table_.warning);
        }
        return std::nullopt;
    }
    long long c = -1;
    if (ended && (*st)["code"].is_number_integer()) {
        c = (*st)["code"].get<long long>();
    }
    if (phase == "done" && c == 0) {
        std::optional<Json> got = read_reply(aos::join(dir, "reply.json"));
        if (got) {
            return *got;
        }
        return error_reply(code::ReplyBad, "endpoint 函數的 stdout 讀不懂（要是一行 {\"message\": {...}, \"usage\", \"model\"}）");
    }
    if (phase == "done" && c != 143) {
        std::string why = "endpoint 函數退 " + std::to_string(c);
        std::string line = first_line(aos::join(dir, "reply.json"));   // llm_http 失敗時 stdout 也印同一行
        if (line.empty()) {
            line = first_line(aos::join(dir, "stderr.txt"));
        }
        if (!line.empty()) {
            why += "：" + line;
        }
        return error_reply(code::EndpointFailed, why);
    }
    // 逾時（143）、被收掉（stopped）、死在半路（沒收尾、列也不在）
    double at = proc.value("mounted_at", 0.0);
    if (c == 143 && cfg_.timeout_ms && now_s() - at >= (double)*cfg_.timeout_ms / 1000.0) {
        return error_reply(code::EndpointFailed, "endpoint 函數逾時（" + std::to_string(*cfg_.timeout_ms) + " ms）");
    }
    long long retries = proc.value("retries", 0LL);
    if (retries >= 1) {
        return error_reply(code::EndpointFailed, "問腦跑了兩次都沒結果（被收掉或死在半路）");
    }
    std::error_code ec;
    fs::remove(aos::join(dir, "state.json"), ec);
    fs::remove(aos::join(dir, "reply.json"), ec);
    proc["retries"] = retries + 1;
    try {
        mount(id, proc.value("exec", cfg_.exec), proc);
    } catch (const Error& e) {
        return error_reply(code::LaunchFailed, "重掛寄不出去：" + e.code + " " + e.msg);
    }
    return std::nullopt;
}

// cur/ 裡的：有 proc.json＝在飛（看 settle）；有 reply.json 沒 proc.json＝回信寫好了只差寄（上一次寄到一半）；
// 都沒有＝認領了還沒掛就死＝改名回 new/ 重排。
void Server::collect() {
    for (const std::string& id : names_in(mb_.cur())) {
        std::string dir = aos::join(mb_.cur(), id);
        std::optional<Json> proc = aos::read_json(aos::join(dir, PROC_JSON));
        if (proc && proc->is_object()) {
            std::optional<Json> reply = settle(id, *proc);
            if (reply) {
                finish(id, *reply);
            } else {
                ++busy_;
            }
            continue;
        }
        std::optional<Json> reply = read_reply(aos::join(dir, "reply.json"));
        if (reply) {
            finish(id, *reply);
        } else if (!move(dir, aos::join(mb_.fresh(), id))) {
            remove_tree(dir);
        }
    }
}

// 寄信的人不在了的（<信>/sender.flock 在、但沒人鎖著）：tmp/ 直接刪；new/ 先改名回 tmp/ 再刪（跟撤信同一個做法，不會跟認領撞）。
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
void Server::refuse(const std::string& id, const Json& reply) {
    if (!move(aos::join(mb_.fresh(), id), aos::join(mb_.cur(), id))) {
        return;
    }
    finish(id, reply);
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
            refuse(id, error_reply(code::LetterBad, why));
            continue;
        }
        const Json& body = (*letter)["body"];
        if (body.contains("endpoint") && !body["endpoint"].is_string()) {
            refuse(id, error_reply(code::LetterBad, "信的 body.endpoint 要是字串（代號），不是 " + aos::dumps(body["endpoint"])));
            continue;
        }
        Waiting w;
        w.id = id;
        w.letter = *letter;
        try {
            w.priority = priority_of(*letter);
        } catch (const Error& e) {
            refuse(id, error_reply(code::LetterBad, "信的 " + e.msg));
            continue;
        }
        const Json& req = body["request"];
        if (!req.is_object() || !req.value("messages", Json()).is_array()) {
            refuse(id, error_reply(code::RequestBad, "body.request 要是物件、messages 要是陣列"));
            continue;
        }
        if (req.contains("stream") && !req["stream"].is_null() && req["stream"] != Json(false)) {
            refuse(id, error_reply(code::RequestBad, "串流不做：request 不能寫 stream: true"));
            continue;
        }
        std::optional<Json> bad = pick(w);
        if (bad) {
            refuse(id, *bad);
            continue;
        }
        if (w.priority.deadline && *w.priority.deadline < now) {
            refuse(id, error_reply(code::DeadlineMissed, "輪到之前時限已過，沒跑"));
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

int Server::run() {
    for (const std::string& d : {mb_.root, mb_.tmp(), mb_.fresh(), mb_.cur()}) {
        make_dir(d);
    }
    host_ = find_host();   // 沒 AOS_DAEMON＝DaemonMissing、daemon 沒開 ctl 信箱＝MailboxMissing（kernel 自己的錯，退 1）
    lock();
    q_ = read_queue(stack_);
    q_.runs += 1;
    used_ = read_used(stack_, budget_.window);
    table_ = read_table(host_);
    collect();
    sweep();
    std::vector<Waiting> ws = scan();
    order(ws, q_.runs);

    int got = aos::loop::take_signal();
    if (got == 0) {
        long long n = 0;   // 這次新掛的
        for (const Waiting& w : ws) {
            if (spent(budget_, used_, n + busy_)) {   // 這一窗額度到頂
                if (budget_.wait) {
                    break;   // 留在 new/ 等下一窗（寄信的一直等，由它自己那邊守）
                }
                q_.seen_at_runs.erase(w.id);
                refuse(w.id, error_reply(code::BudgetMissing, "這一窗（" + budget_.window + "）的額度用完了，沒跑"));
                continue;
            }
            if (n + busy_ >= slots_) {
                break;   // 補位到 slots 為止；其餘下一次
            }
            std::string dir = aos::join(mb_.cur(), w.id);
            if (!move(aos::join(mb_.fresh(), w.id), dir)) {
                continue;   // 寄信的剛撤信
            }
            q_.seen_at_runs.erase(w.id);
            Json req = Json::object();
            req["endpoint"] = w.group;
            req["request"] = w.letter["body"]["request"];
            std::optional<std::string> werr = aos::write_json(aos::join(dir, "request.json"), req);
            try {
                if (werr) {
                    throw Error{code::WriteFailed, *werr};
                }
                mount(w.id, w.exec, Json::object());
            } catch (const Error& e) {
                std::error_code ec;
                fs::remove(aos::join(dir, PROC_JSON), ec);
                finish(w.id, error_reply(code::LaunchFailed, "掛不上 daemon：" + e.code + " " + e.msg));
                continue;
            }
            ++n;
        }
    }
    write_queue(stack_, q_);
    if (got != 0) {
        return 128 + got;
    }
    return 0;
}

}  // namespace

int serve(const Cfg& cfg, const std::string& stack) {
    Server s(cfg, stack);
    return s.run();
}

}  // namespace aos::llm_kernel
