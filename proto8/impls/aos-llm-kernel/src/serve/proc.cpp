// proc.cpp：【serve】掛問腦 proc、判斷收尾與透明錯誤、沿用換包旗標重掛並收集各後端在飛信件（說明見 serve.hpp）。
#include "serve/serve.hpp"

#include "aos/util/files.hpp"

#include <chrono>
#include <filesystem>

namespace fs = std::filesystem;

namespace aos::llm_kernel {

// 問腦 proc（11-05 kernel-daemon 03）：kernel 不自己跑，請 daemon 掛成 max: 1 的 loop 型 proc。
// 掛上去的信才有 cur/<id>/proc.json＝{"name": daemon 表上的名字, "exec": endpoint 函數, "mount_letter": 掛信的信件名稱, "mounted_at": epoch 秒, "retries": 重掛過幾次}。
const char* PROC_JSON = "proc.json";

namespace {

double now_s() {
    return std::chrono::duration<double>(std::chrono::system_clock::now().time_since_epoch()).count();
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

// 非零退出的透明錯誤只接受整份單行 JSON，頂層只能有 error；內層的其他鍵照留。
std::optional<Json> read_error(const std::string& path) {
    int err = 0;
    std::optional<std::string> text = aos::read_file(path, err);
    if (!text) {
        return std::nullopt;
    }
    if (!text->empty() && text->back() == '\n') {
        text->pop_back();
        if (!text->empty() && text->back() == '\r') {
            text->pop_back();
        }
    }
    if (text->find_first_of("\r\n") != std::string::npos) {
        return std::nullopt;
    }
    Json reply = Json::parse(*text, nullptr, false);
    if (!reply.is_object() || reply.size() != 1 || !reply.contains("error")) {
        return std::nullopt;
    }
    return reply_of(reply);
}

}  // namespace

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
    // 首次掛上沿用建 request 的同一個時間；重掛只更新本次計時，request 與 seen_at 不動。
    if (!proc.contains("mounted_at") || proc.value("retries", 0LL) > 0) {
        proc["mounted_at"] = now_s();
    }
    if (!proc.contains("retries")) {
        proc["retries"] = 0;
    }
    std::optional<std::string> err = aos::write_json(aos::join(dir, PROC_JSON), proc);
    if (err) {
        throw Error{code::WriteFailed, *err};
    }
}

// 一封在飛的信現在怎樣（03 § 2、04 #13）：回 nullopt＝還在飛（佔一格）；回信＝收尾。
//   表上有這列：running／stopping／sleeping＝在飛；stopped 而問腦 loop 跑完了（state.json done）＝收、順手寄 procs_removed 拔列；
//              stopped 而列上有 reason（11-05：問腦 loop 退非 0，daemon 不再下表、留 stopped＋reason）＝同樣收尾（照下面看 code）、寄 procs_removed；
//              stopped、沒 reason、沒跑完（有人下了 stop）＝在飛（等）
//   表上沒有：state.json 收尾了（done／stopped）＝看 code；state.json 在、沒收尾＝跑到一半死了→重掛；
//            不在＝daemon 還沒套（暫停中、還沒輪到）＝在飛，或拒了（state_flux.json 的 mailbox_warning 提到這封掛信）＝LaunchFailed
//   重掛時列還在（出錯留的 stopped）：先寄 procs_removed、proc.json 記 remount，等 daemon 把列拔了下一次才寄掛信（同名 add 不會把 stopped 的拉起來；
//   直接 procs_started 的話，daemon 還沒套信前下一次 collect 會把舊列的 reason 當成第二次失敗）
std::optional<Json> Server::settle(const std::string& id, Json proc) {
    std::string dir = aos::join(mb_.cur(), id);
    std::string name = proc.value("name", "llm_" + id);
    if (proc.value("remount", false)) {
        if (table_.procs.contains(name)) {
            return std::nullopt;   // 舊列還沒拔：等
        }
        proc.erase("remount");
        try {
            mount(id, proc.value("exec", cfg_.exec), proc);
        } catch (const Error& e) {
            return error_reply(code::LaunchFailed, "remount letter could not be sent: " + e.code + " " + e.msg);
        }
        return std::nullopt;
    }
    std::optional<Json> st = aos::read_window("aos-llm-kernel", aos::join(dir, "state.json"));
    std::string phase = st && st->is_object() ? st->value("phase", "") : "";
    bool ended = phase == "done" || phase == "stopped";
    bool held = table_.procs.contains(name);
    if (held) {
        const Json& row = table_.procs[name];
        bool failed = row.is_object() && row.value("reason", Json()).is_string();   // 11-05：出錯結束 daemon 留的 stopped
        if (!row.is_object() || row.value("phase", "") != "stopped" || (phase != "done" && !failed)) {   // stopped 沒 reason 沒跑完＝有人下了 stop：等
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
            return error_reply(code::LaunchFailed, "daemon rejected the add letter: " + table_.warning);
        }
        return std::nullopt;
    }
    long long c = -1;
    if (ended && (*st)["code"].is_number_integer()) {
        c = (*st)["code"].get<long long>();
    }
    if (phase == "done" && c == 0) {
        std::optional<Json> got = read_reply(aos::join(dir, "reply.json"));
        if (got && !got->contains("error")) {
            return *got;
        }
        return error_reply(code::ReplyBad, "cannot understand the endpoint function's stdout (must be one line {\"message\": {...}, \"usage\", \"model\"})");
    }
    // 逾時：aos-exec 先 TERM（143），不理 TERM 的過了寬限再 KILL（137）——兩種都看 mounted_at＋timeout_ms 過了沒（11-05 edge-llm）
    double at = proc.value("mounted_at", 0.0);
    bool late = cfg_.timeout_ms && now_s() - at >= (double)*cfg_.timeout_ms / 1000.0;
    if (phase == "done" && (c == 143 || c == 137) && late) {
        return error_reply(code::EndpointFailed, "endpoint function timed out (" + std::to_string(*cfg_.timeout_ms) + " ms)");
    }
    if (phase == "done" && c != 0) {
        std::optional<Json> error = read_error(aos::join(dir, "reply.json"));
        if (error) {
            return *error;
        }
    }
    if (phase == "done" && c != 143) {
        std::string why = "endpoint function exited with code " + std::to_string(c);
        std::string line = first_line(aos::join(dir, "reply.json"));   // llm_http 失敗時 stdout 也印同一行
        if (line.empty()) {
            line = first_line(aos::join(dir, "stderr.txt"));
        }
        if (!line.empty()) {
            why += ": " + line;
        }
        return error_reply(code::EndpointFailed, why);
    }
    // 沒到時限的 143、被收掉（stopped）、死在半路（沒收尾、列也不在）＝重掛一次
    long long retries = proc.value("retries", 0LL);
    if (retries >= 1) {
        return error_reply(code::EndpointFailed, "the brain call ran twice without a result (stopped or died midway)");
    }
    std::error_code ec;
    fs::remove(aos::join(dir, "state.json"), ec);
    fs::remove(aos::join(dir, "reply.json"), ec);
    proc["retries"] = retries + 1;
    if (held) {   // 列還在（procs_removed 上面寄了）：等它拔了再掛（見函數頭）
        proc["remount"] = true;
        std::optional<std::string> err = aos::write_json(aos::join(dir, PROC_JSON), proc);
        if (err) {
            return error_reply(code::WriteFailed, *err);
        }
        return std::nullopt;
    }
    try {
        mount(id, proc.value("exec", cfg_.exec), proc);
    } catch (const Error& e) {
        return error_reply(code::LaunchFailed, "cannot send the re-add letter: " + e.code + " " + e.msg);
    }
    return std::nullopt;
}

// cur/ 裡的：有 proc.json＝在飛（看 settle）；有 reply.json 沒 proc.json＝回信寫好了只差寄（上一次寄到一半）；
// 都沒有＝認領了還沒掛就死＝改名回 new/ 重排。
void Server::collect() {
    for (const std::string& id : aos::names_in(mb_.cur(), true)) {
        std::string dir = aos::join(mb_.cur(), id);
        std::optional<Json> proc = aos::read_json(aos::join(dir, PROC_JSON));
        if (proc && proc->is_object()) {
            std::optional<Json> reply = settle(id, *proc);
            if (reply) {
                finish(id, *reply);
            } else {
                ++busy_;
                if (proc->value("endpoint", Json()).is_string()) {
                    const std::string endpoint = (*proc)["endpoint"].get<std::string>();
                    ++pack_busy_[endpoint];
                    std::optional<std::string> backend;
                    if (proc->value("backend", Json()).is_string()) {
                        backend = (*proc)["backend"].get<std::string>();
                    } else if (cfg_.packs.contains(endpoint)) {
                        backend = cfg_.packs.at(endpoint).backend;
                    }
                    if (backend) {
                        ++backend_busy_[*backend];
                        backend_packs_[*backend].insert(endpoint);
                    }
                }
                if (proc->value("sender", Json()).is_string()) {
                    ++sender_busy_[sender_key((*proc)["sender"].get<std::string>(), stack_)];
                }
            }
            continue;
        }
        std::optional<Json> reply = read_reply(aos::join(dir, "reply.json"));
        if (reply) {
            finish(id, *reply);
        } else if (!aos::move(dir, aos::join(mb_.fresh(), id))) {
            aos::remove_tree(dir);
        }
    }
}

}  // namespace aos::llm_kernel
