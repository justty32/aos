// send.cpp：【send】找信箱、讀 body、寄信、撤信（說明見 send.hpp）。
#include "send/send.hpp"

#include "aos/files.hpp"
#include "aos/proc.hpp"

#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <optional>
#include <signal.h>

namespace fs = std::filesystem;

namespace aos::llm {

// $AOS_LLM_KERNEL＝llm kernel 的 stack（11-05 kernel-daemon 07 § 2；合一時＝那台 llm daemon 的 stack），信箱固定在 <stack>/mailbox/。
// 相對路徑的基準點（11-05 edge 別線，照 portable-flow「基準點＝管我的 daemon 的 stack」）：有 $AOS_DAEMON（被 daemon 管著跑）
// ＝相對它；沒有（人直接在殼裡打）＝相對 cwd。
Mailbox kernel() {
    const char* k = std::getenv("AOS_LLM_KERNEL");
    if (k == nullptr || *k == 0) {
        throw Error{code::LlmKernelMissing, "AOS_LLM_KERNEL is not set (the llm kernel stack, e.g. ~/llm_kernel)"};
    }
    std::string path = k;
    const char* d = std::getenv("AOS_DAEMON");
    if (path[0] != '/' && d != nullptr && *d != 0) {
        path = aos::join(d, path);
    }
    std::error_code ec;
    if (!fs::is_directory(path, ec)) {
        throw Error{code::LlmKernelMissing, "AOS_LLM_KERNEL is not a folder: " + path};
    }
    return Mailbox{aos::join(aos::abspath(path), "mailbox")};
}

// 11-05 edge-llm 題 1（使用者「按照推薦」）：$AOS_LLM_KERNEL 那裡沒有在跑的 daemon＝stderr 提醒一行，照樣寄、照樣等。
// 只看那個 stack 的 state.json（daemon 自己寫的窗）：不在＝不是一台 daemon 的 stack；phase 不是 running／stopping、或 pid 不在＝停了。
void warn_idle(const Mailbox& mb) {
    std::string stack = aos::dirname(mb.root);
    std::optional<Json> st = aos::read_json(aos::join(stack, "state.json"));
    std::string why;
    if (!st || !st->is_object()) {
        why = "no llm daemon here (no state.json: never started, pointing at def/, or started without --stack .?)";
    } else {
        std::string phase = st->value("phase", "");
        Json pid = st->value("pid", Json());
        bool alive = pid.is_number_integer() && (::kill((pid_t)pid.get<long long>(), 0) == 0 || errno == EPERM);
        if ((phase != "running" && phase != "stopping") || !alive) {
            why = "llm daemon is not running (state.json phase " + (phase.empty() ? std::string("?") : phase) +
                  (alive ? "" : ", pid gone") + "; see the daemon output for why)";
        }
    }
    if (!why.empty()) {
        aos::warn("aos-llm", stack + ": " + why + "; letter sent anyway, the reply comes once it runs");
    }
}

// --priority 的值：讀得成 JSON 就用它（1、{"level": "high"}），不然當字串（high）。
static Json priority_value(const std::string& s) {
    Json v = Json::parse(s, nullptr, false);
    if (v.is_discarded()) {
        return Json(s);
    }
    return v;
}

Json read_body(const std::optional<std::string>& priority) {
    Json body;
    try {
        body = aos::read_stdin();
    } catch (const Error& e) {
        throw Error{code::RequestBad, "stdin must be one JSON document (the body): " + e.msg};
    }
    const std::string shape = "stdin must be {\"endpoint\"?: name, \"request\": {\"messages\": [...], ...}, \"priority\"?}";
    if (!body.is_object()) {
        throw Error{code::RequestBad, shape + ", got " + aos::dumps(body)};
    }
    if (!body.value("request", Json()).is_object() || !body["request"].value("messages", Json()).is_array()) {
        throw Error{code::RequestBad, shape + " (request must be an object, messages an array)"};
    }
    if (body.contains("endpoint") && !body["endpoint"].is_string()) {
        throw Error{code::RequestBad, shape + " (endpoint must be a string)"};
    }
    if (priority) {
        body["priority"] = priority_value(*priority);
    }
    if (body.contains("priority")) {
        aos::llm_kernel::parse_priority(body["priority"]);   // 壞＝PriorityBad
    }
    return body;
}

std::string send(const Mailbox& mb, const Json& body, const std::string& reply_to) {
    aos::post::init(reply_to);   // 回信信箱（kernel 要寄得進去；建不了丟 MkdirFailed）
    aos::make_dir(mb.tmp());
    aos::make_dir(mb.fresh());
    aos::post::SendOpts opts;
    opts.reply_to = reply_to;
    return aos::post::send(aos::post::open(mb.root), body, opts);
}

std::string send_held(const Mailbox& mb, const Json& body) {
    aos::post::init(reply_box(mb));   // 建不了丟 MkdirFailed
    Json letter = Json::object();
    letter["sender"] = aos::identity();   // 信封（N-16），同 aos-post
    letter["sent_at"] = aos::utc_now_ms();
    letter["reply_to"] = aos::post::reply_to_rel(aos::post::Mailbox{mb.root}, reply_box(mb));   // 相對信箱根＝"reply"（11-05，同 aos-post send）
    letter["body"] = body;

    aos::make_dir(mb.tmp());
    aos::make_dir(mb.fresh());
    std::string id = aos::unique_id();
    std::string t = aos::join(mb.tmp(), "." + id);   // . 開頭＝還在寫，kernel 不碰
    aos::make_dir(t);
    std::error_code ec;
    try {
        aos::llm_kernel::hold_sender(t);   // 拿到行程結束（fd 不關）
    } catch (const Error&) {
        fs::remove_all(t, ec);
        throw;
    }
    std::optional<std::string> err = aos::write_json(aos::join(t, "letter.json"), letter);
    if (err) {
        fs::remove_all(t, ec);
        throw Error{code::WriteFailed, *err};
    }
    std::string n = aos::join(mb.fresh(), id);
    if (std::rename(t.c_str(), n.c_str()) != 0) {
        int e = errno;
        fs::remove_all(t, ec);
        throw Error{code::WriteFailed, "cannot rename " + t + " -> " + n + ": " + std::strerror(e)};
    }
    return id;
}

void regret(const Mailbox& mb, const std::string& name) {
    aos::post::check_name(name);   // 不合 ArgumentsBad
    if (!aos::post::regret(aos::post::open(mb.root), name)) {
        throw Error{code::RegretFailed, "letter " + name + " not in " + mb.fresh() + " (already taken by the kernel, or never there)"};
    }
}

}  // namespace aos::llm
