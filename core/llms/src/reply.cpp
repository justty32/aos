#include <aos/llms.hpp>

#include "llms_internal.hpp"

#include <new>
#include <stdexcept>
#include <utility>

namespace aos::llms {
namespace {

std::optional<std::int64_t> optional_count(const json &object,
                                           const char *name) {
    const auto found = object.find(name);
    if (found == object.end() || found->is_null()) return std::nullopt;
    if (!found->is_number_integer() && !found->is_number_unsigned()) {
        throw std::invalid_argument(std::string("usage.") + name + " 不是整數");
    }
    return found->get<std::int64_t>();
}

std::optional<Usage> parse_usage(const json &response) {
    const auto found = response.find("usage");
    if (found == response.end() || found->is_null()) return std::nullopt;
    if (!found->is_object()) {
        throw std::invalid_argument("usage 不是 object");
    }
    Usage result;
    result.prompt = optional_count(*found, "prompt_tokens");
    result.completion = optional_count(*found, "completion_tokens");
    result.total = optional_count(*found, "total_tokens");
    const auto prompt_details = found->find("prompt_tokens_details");
    if (prompt_details != found->end() && !prompt_details->is_null()) {
        if (!prompt_details->is_object()) {
            throw std::invalid_argument(
                "usage.prompt_tokens_details 不是 object");
        }
        result.cached = optional_count(*prompt_details, "cached_tokens");
    }
    const auto completion_details = found->find("completion_tokens_details");
    if (completion_details != found->end() && !completion_details->is_null()) {
        if (!completion_details->is_object()) {
            throw std::invalid_argument(
                "usage.completion_tokens_details 不是 object");
        }
        result.reasoning =
            optional_count(*completion_details, "reasoning_tokens");
    }
    return result;
}

std::string optional_text(const json &object, const char *name) {
    const auto found = object.find(name);
    if (found == object.end() || found->is_null()) return {};
    if (!found->is_string()) {
        throw std::invalid_argument(std::string(name) + " 不是字串或 null");
    }
    return found->get<std::string>();
}

std::vector<RawToolCall> parse_calls(const json &message) {
    const auto found = message.find("tool_calls");
    if (found == message.end() || found->is_null()) return {};
    if (!found->is_array()) {
        throw std::invalid_argument("message.tool_calls 不是 array");
    }
    std::vector<RawToolCall> result;
    result.reserve(found->size());
    for (const json &call : *found) {
        if (!call.is_object()) {
            throw std::invalid_argument("tool_calls 項目不是 object");
        }
        const auto id = call.find("id");
        const auto function = call.find("function");
        if (id == call.end() || !id->is_string() || function == call.end() ||
            !function->is_object()) {
            throw std::invalid_argument("tool call 缺少 id 或 function");
        }
        const auto name = function->find("name");
        const auto arguments = function->find("arguments");
        if (name == function->end() || !name->is_string() ||
            arguments == function->end() || !arguments->is_string()) {
            throw std::invalid_argument(
                "tool call 的 function 缺少 name 或 arguments");
        }
        result.push_back({.id = id->get<std::string>(),
                          .name = name->get<std::string>(),
                          .arguments = arguments->get<std::string>()});
    }
    return result;
}

void set_stream_error(Reply &reply, ErrorKind kind, std::string message) {
    if (!reply.err) {
        reply.err = ReplyError{.kind = kind, .message = std::move(message)};
    }
}

} // namespace

const char *to_string(ReplyPart part) noexcept {
    switch (part) {
    case ReplyPart::Think:
        return "think";
    case ReplyPart::Answer:
        return "answer";
    }
    return "unknown";
}

Reply::Reply() : impl_(std::make_unique<Impl>()) {}
Reply::Reply(Reply &&) noexcept = default;
Reply &Reply::operator=(Reply &&other) noexcept {
    if (this == &other) return *this;
    try {
        finish();
    } catch (...) {
        /* move assignment 也不能讓舊串流漏掉收尾。 */
    }
    impl_ = std::move(other.impl_);
    text = std::move(other.text);
    calls = std::move(other.calls);
    reasoning = std::move(other.reasoning);
    finish_reason = std::move(other.finish_reason);
    usage = std::move(other.usage);
    err = std::move(other.err);
    checkpoint = other.checkpoint;
    return *this;
}
Reply::~Reply() {
    if (!impl_) return;
    try {
        finish();
    } catch (...) {
        /* 解構不可丟例外；finish() 已盡力關閉並回復 history。 */
    }
}

Reply::operator bool() const noexcept { return !err.has_value(); }

void Reply::set_sink(ReplySink sink) {
    if (impl_->started) {
        throw std::logic_error("串流開始後不能更換 sink");
    }
    impl_->sink = std::move(sink);
}

void Reply::set_part_sink(ReplyPartSink sink) {
    if (impl_->started) {
        throw std::logic_error("串流開始後不能更換 parts sink");
    }
    impl_->part_sink = std::move(sink);
}

const std::string &Reply::all_text() {
    if (!impl_->done && impl_->drain_action) {
        impl_->started = true;
        try {
            impl_->drain_action(*this);
        } catch (const std::bad_alloc &) {
            throw;
        } catch (const std::exception &error) {
            set_stream_error(*this, ErrorKind::Response, error.what());
        } catch (...) {
            set_stream_error(*this, ErrorKind::Response,
                             "讀取回應時發生未知錯誤");
        }
    }
    finish();
    return text;
}

void Reply::finish() {
    if (!impl_ || impl_->done) return;
    impl_->done = true;
    if (impl_->close_action) {
        try {
            impl_->close_action();
        } catch (...) {
            /* 關閉連線失敗不覆蓋真正的回應。 */
        }
    }
    if (!impl_->accumulator.empty()) {
        impl_->raw_calls = impl_->accumulator.raw();
    }
    text = impl_->buffer;
    reasoning = impl_->reasoning_buffer.empty()
                    ? std::nullopt
                    : std::optional<std::string>(impl_->reasoning_buffer);
    calls.clear();
    calls.reserve(impl_->raw_calls.size());
    for (const RawToolCall &raw : impl_->raw_calls) {
        calls.push_back(tool_call_entry(raw));
    }
    if (impl_->finish_action) {
        try {
            impl_->finish_action(*this);
        } catch (const std::bad_alloc &) {
            throw;
        } catch (const std::exception &error) {
            err =
                ReplyError{.kind = ErrorKind::Response,
                           .message = "收尾失敗：" + std::string(error.what())};
        } catch (...) {
            err =
                ReplyError{.kind = ErrorKind::Response, .message = "收尾失敗"};
        }
    }
}

Reply detail_ReplyAccess::make_error(ErrorKind kind, std::string message,
                                     std::size_t checkpoint) {
    Reply result;
    result.err = ReplyError{.kind = kind, .message = std::move(message)};
    result.checkpoint = checkpoint;
    result.impl_->done = true;
    return result;
}

Reply detail_ReplyAccess::absorb(
    const json &response, std::size_t checkpoint,
    std::function<void(const Reply &)> finish_action) {
    if (!response.is_object()) {
        throw std::invalid_argument("回應最外層不是 object");
    }
    const auto choices = response.find("choices");
    if (choices == response.end() || !choices->is_array() || choices->empty() ||
        !(*choices)[0].is_object()) {
        throw std::invalid_argument("回應缺少 choices[0]");
    }
    const json &choice = (*choices)[0];
    const auto message = choice.find("message");
    if (message == choice.end() || !message->is_object()) {
        throw std::invalid_argument("回應缺少 choices[0].message");
    }

    Reply result;
    result.checkpoint = checkpoint;
    const auto finish_reason = choice.find("finish_reason");
    if (finish_reason != choice.end() && !finish_reason->is_null()) {
        if (!finish_reason->is_string()) {
            throw std::invalid_argument("finish_reason 不是字串或 null");
        }
        result.finish_reason = finish_reason->get<std::string>();
    }
    result.usage = parse_usage(response);
    result.impl_->buffer = optional_text(*message, "content");
    result.impl_->reasoning_buffer =
        optional_text(*message, "reasoning_content");
    if (result.impl_->reasoning_buffer.empty()) {
        result.impl_->reasoning_buffer = optional_text(*message, "reasoning");
    }
    result.impl_->raw_calls = parse_calls(*message);
    result.impl_->finish_action = std::move(finish_action);
    result.finish();
    return result;
}

} // namespace aos::llms
