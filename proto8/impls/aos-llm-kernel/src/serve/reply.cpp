// reply.cpp：【serve】寫回信、寄送與撤回回信、記用量與逐封帳並收掉信件（說明見 serve.hpp）。
#include "serve/serve.hpp"

#include "aos/util/files.hpp"
#include "aos/post.hpp"

#include <chrono>
#include <filesystem>
#include <fstream>

namespace fs = std::filesystem;

namespace aos::llm_kernel {

Json error_reply(const std::string& c, const std::string& msg) {
    Json e = Json::object();
    e["code"] = c;
    e["msg"] = msg;
    Json r = Json::object();
    r["error"] = e;
    return r;
}

namespace {

void write_reply(const std::string& dir, const Json& reply) {
    std::optional<std::string> err = aos::write_json(aos::join(dir, "reply.json"), reply);
    if (err) {
        throw Error{code::WriteFailed, *err};
    }
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
        if (aos::write_text(aos::join(dir, "reply_letter.txt"), sig + "\n", tmp)) {
            return std::string(code::WriteFailed) + " reply sent (" + sig + ") but cannot record it in " + dir + "/reply_letter.txt";
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

// 跑過的（掛上去過＝cur/<id>/proc.json 在）才算一次、才看 usage；沒跑的（LetterBad、EndpointUnknown、DeadlineBad、BudgetMissing…）不算。
bool ran(const std::string& dir) {
    std::error_code ec;
    return fs::exists(aos::join(dir, PROC_JSON), ec);
}

// 掛上去的信的 proc.json 裡一格字串（endpoint＝代號、sender＝寄件人；沒有＝空）。
std::string proc_str(const std::string& dir, const char* key) {
    std::optional<Json> proc = aos::read_json(aos::join(dir, PROC_JSON));
    if (!proc || !proc->is_object() || !proc->value(key, Json()).is_string()) {
        return "";
    }
    return (*proc)[key].get<std::string>();
}

// 逐封帳只留成本與時間，不存請求內容；寫不了只提醒，不影響回信與收信。
void append_ledger(const std::string& stack, const std::string& dir, const std::string& id, const Json& reply) {
    std::string path = aos::join(stack, "ledger.jsonl");
    try {
        std::optional<Json> proc = aos::read_json(aos::join(dir, PROC_JSON));
        Json entry = Json::object();
        entry["id"] = id;
        for (const char* key : {"endpoint", "sender"}) {
            entry[key] = proc && proc->is_object() ? proc->value(key, Json()) : Json();
        }
        entry["model"] = reply.value("model", Json());
        entry["seen_at"] = proc && proc->is_object() ? proc->value("seen_at", Json()) : Json();
        entry["mounted_at"] = proc && proc->is_object() ? proc->value("mounted_at", Json()) : Json();
        double finished = std::chrono::duration<double>(std::chrono::system_clock::now().time_since_epoch()).count();
        entry["finished_at"] = finished;
        entry["elapsed_ms"] = nullptr;
        if (entry["mounted_at"].is_number()) {
            double elapsed = (finished - entry["mounted_at"].get<double>()) * 1000.0;
            if (elapsed < 0) {
                elapsed = 0;
            }
            entry["elapsed_ms"] = static_cast<long long>(elapsed);
        }
        entry["usage"] = reply.value("usage", Json());
        entry["code"] = nullptr;
        if (reply.contains("error")) {
            entry["code"] = reply["error"]["code"];
        }
        entry["child"] = reply.value("child", Json());
        entry["switched"] = false;
        std::ofstream out(path, std::ios::app);
        out << aos::dumps(entry) << '\n';
        out.close();
        if (!out) {
            aos::warn("aos-llm-kernel", "cannot append ledger: " + path);
        }
    } catch (const std::exception& e) {
        aos::warn("aos-llm-kernel", "cannot append ledger: " + path + " (" + e.what() + ")");
    }
}

}  // namespace

// 寫好 reply.json、寄回信，然後整封刪掉（cur/<id>/；11-04 夜使用者「舊信根本不用留，就是刪」）。回信寄不出去＝stderr 提醒行（不退出，11-05 R1）、照刪、不退。
void Server::finish(const std::string& id, const Json& reply) {
    std::string dir = aos::join(mb_.cur(), id);
    write_reply(dir, reply);
    Json body = reply;
    body.erase("child");
    bool counted = ran(dir);
    std::string endpoint = proc_str(dir, "endpoint");
    std::string sender = proc_str(dir, "sender");
    Json reply_error = post_reply(mb_.root, dir, id, body);   // child 只進本層帳，不往上傳
    if (reply_error.is_string()) {
        aos::warn("aos-llm-kernel", "cannot send the reply to letter " + id + " (" + reply_error.get<std::string>() + "); letter deleted anyway");
    }
    if (has_sender(dir) && !sender_alive(dir)) {
        regret_reply(mb_.root, dir);   // 同步寄的人已經走了（ask 被打斷）：回信沒人拿，撤回
    }
    if (counted) {
        append_ledger(stack_, dir, id, reply);
        add_used(stack_, used_, report_of(reply), endpoint, sender);   // usage 從回信拿（沒有＝只算次數）；packs.<代號>、senders.<寄件人> 也記
    }
    aos::remove_tree(dir);   // 刪不掉（權限）不算錯：下一次 collect 看到 reply_letter.txt 就不重寄
}

// 不跑、直接回信（LetterBad、RequestBad、Endpoint*、DeadlineBad、BudgetMissing…）：先認領，認領不到＝寄信的剛撤信，算了。
void Server::refuse(const std::string& id, const Json& reply) {
    if (!aos::move(aos::join(mb_.fresh(), id), aos::join(mb_.cur(), id))) {
        return;
    }
    finish(id, reply);
}

}  // namespace aos::llm_kernel
