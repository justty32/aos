// send.cpp：【send】找信箱、讀 body、寄信、撤信（說明見 send.hpp）。
#include "send/send.hpp"

#include "aos/files.hpp"
#include "aos/proc.hpp"

#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>

namespace fs = std::filesystem;

namespace aos::llm {

// $AOS_LLM_KERNEL＝llm kernel 的 stack（11-05 kernel-daemon 07 § 2；合一時＝那台 llm daemon 的 stack），信箱固定在 <stack>/mailbox/。
Mailbox kernel() {
    const char* k = std::getenv("AOS_LLM_KERNEL");
    if (k == nullptr || *k == 0) {
        throw Error{code::LlmKernelMissing, "沒設定 AOS_LLM_KERNEL（llm kernel 的 stack，例 ~/llm_kernel）"};
    }
    std::error_code ec;
    if (!fs::is_directory(k, ec)) {
        throw Error{code::LlmKernelMissing, std::string("AOS_LLM_KERNEL 指的資料夾不在：") + k};
    }
    return Mailbox{aos::join(aos::abspath(k), "mailbox")};
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
        throw Error{code::RequestBad, "stdin 要是一份 JSON（body）：" + e.msg};
    }
    const std::string shape = "stdin 要是 {\"endpoint\"?: 代號, \"request\": {\"messages\": [...], ...}, \"priority\"?}";
    if (!body.is_object()) {
        throw Error{code::RequestBad, shape + "，不是 " + aos::dumps(body)};
    }
    if (!body.value("request", Json()).is_object() || !body["request"].value("messages", Json()).is_array()) {
        throw Error{code::RequestBad, shape + "（request 要是物件、messages 要是陣列）"};
    }
    if (body.contains("endpoint") && !body["endpoint"].is_string()) {
        throw Error{code::RequestBad, shape + "（endpoint 要是字串）"};
    }
    if (priority) {
        body["priority"] = priority_value(*priority);
    }
    if (body.contains("priority")) {
        aos::llm_kernel::parse_priority(body["priority"]);   // 壞＝PriorityBad
    }
    return body;
}

static void make_dir(const std::string& dir) {
    std::error_code ec;
    fs::create_directories(dir, ec);
    if (ec || !fs::is_directory(dir)) {
        throw Error{code::MkdirFailed, "建不了 " + dir + (ec ? "：" + ec.message() : "")};
    }
}

std::string send(const Mailbox& mb, const Json& body, const std::string& reply_to) {
    aos::post::init(reply_to);   // 回信信箱（kernel 要寄得進去；建不了丟 MkdirFailed）
    make_dir(mb.tmp());
    make_dir(mb.fresh());
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

    make_dir(mb.tmp());
    make_dir(mb.fresh());
    std::string id = aos::unique_id();
    std::string t = aos::join(mb.tmp(), "." + id);   // . 開頭＝還在寫，kernel 不碰
    make_dir(t);
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
        throw Error{code::WriteFailed, "改名不了 " + t + " → " + n + "：" + std::strerror(e)};
    }
    return id;
}

void regret(const Mailbox& mb, const std::string& name) {
    aos::post::check_name(name);   // 不合 ArgumentsBad
    if (!aos::post::regret(aos::post::open(mb.root), name)) {
        throw Error{code::RegretFailed, "信 " + name + " 不在 " + mb.fresh() + "（已被 kernel 認領，或本來就沒有）"};
    }
}

}  // namespace aos::llm
