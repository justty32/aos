#include "llms_internal.hpp"
#include "sse.hpp"

#include <exception>
#include <utility>

namespace aos::llms {
namespace {

void update_count(const json &object, const char *name,
                  std::optional<std::int64_t> &out) {
    const auto found = object.find(name);
    if (found == object.end() ||
        (!found->is_number_integer() && !found->is_number_unsigned())) {
        return;
    }
    try {
        out = found->get<std::int64_t>();
    } catch (...) {
        /* 串流欄位一律防禦性取用；越界或型別不符就保留舊值。 */
    }
}

void update_usage(const json &response, std::optional<Usage> &current) {
    const auto found = response.find("usage");
    if (found == response.end() || !found->is_object()) return;
    Usage value = current.value_or(Usage{});
    update_count(*found, "prompt_tokens", value.prompt);
    update_count(*found, "completion_tokens", value.completion);
    update_count(*found, "total_tokens", value.total);
    const auto prompt_details = found->find("prompt_tokens_details");
    if (prompt_details != found->end() && prompt_details->is_object()) {
        update_count(*prompt_details, "cached_tokens", value.cached);
    }
    const auto completion_details = found->find("completion_tokens_details");
    if (completion_details != found->end() && completion_details->is_object()) {
        update_count(*completion_details, "reasoning_tokens", value.reasoning);
    }
    current = value;
}

std::string text_field(const json &object, const char *name) {
    const auto found = object.find(name);
    return found != object.end() && found->is_string()
        ? found->get<std::string>() : std::string{};
}

void set_error(Reply &reply, ErrorKind kind, std::string message) {
    if (!reply.err) {
        reply.err = ReplyError{.kind = kind, .message = std::move(message)};
    }
}

void emit(Reply::Impl &impl, ReplyPart part, const std::string &value) {
    if (value.empty()) return;
    if (part == ReplyPart::Think) {
        impl.reasoning_buffer += value;
    } else {
        impl.buffer += value;
    }
    if (impl.part_sink) impl.part_sink(part, value);
    if (part == ReplyPart::Answer && impl.sink) impl.sink(value);
}

void feed_tool_deltas(Reply::Impl &impl, const json &delta) {
    const auto calls = delta.find("tool_calls");
    if (calls == delta.end() || !calls->is_array()) return;
    for (const json &call : *calls) {
        if (!call.is_object()) continue;
        ToolCallDelta part;
        const auto index = call.find("index");
        if (index != call.end() &&
            (index->is_number_unsigned() || index->is_number_integer())) {
            try {
                const auto value = index->get<std::int64_t>();
                if (value >= 0) part.index = static_cast<std::size_t>(value);
            } catch (...) {
                /* 無法表示的 index 當作預設的 0。 */
            }
        }
        part.id = text_field(call, "id");
        const auto function = call.find("function");
        if (function != call.end() && function->is_object()) {
            part.name = text_field(*function, "name");
            part.arguments = text_field(*function, "arguments");
        }
        impl.accumulator.feed(part);
    }
}

void feed_event(Reply &reply, Reply::Impl &impl,
                std::string_view data) noexcept {
    if (reply.err) return;
    try {
        const json chunk = json::parse(data);
        if (!chunk.is_object()) return;

        update_usage(chunk, reply.usage);
        const auto choices = chunk.find("choices");
        /* include_usage 的最後一片只有 usage，沒有 choices。 */
        if (choices == chunk.end() || !choices->is_array() ||
            choices->empty() || !(*choices)[0].is_object()) {
            return;
        }
        const json &choice = (*choices)[0];
        const auto finish_reason = choice.find("finish_reason");
        if (finish_reason != choice.end() && finish_reason->is_string()) {
            const std::string value = finish_reason->get<std::string>();
            if (!value.empty()) reply.finish_reason = value;
        }
        const auto delta = choice.find("delta");
        if (delta == choice.end() || !delta->is_object()) return;

        feed_tool_deltas(impl, *delta);
        std::string thought = text_field(*delta, "reasoning_content");
        if (thought.empty()) thought = text_field(*delta, "reasoning");
        emit(impl, ReplyPart::Think, thought);
        emit(impl, ReplyPart::Answer, text_field(*delta, "content"));
    } catch (const json::parse_error &error) {
        set_error(reply, ErrorKind::Json, error.what());
    } catch (const std::exception &error) {
        set_error(reply, ErrorKind::Response, error.what());
    } catch (...) {
        set_error(reply, ErrorKind::Response,
                  "拆解串流回應時發生未知錯誤");
    }
}

std::string http_message(long status, const std::string &body) {
    std::string message = "HTTP " + std::to_string(status);
    if (!body.empty()) message += ": " + body;
    return message;
}

}  // namespace

Reply detail_ReplyAccess::stream(
    HttpRequest request, StreamTransport transport, std::size_t checkpoint,
    std::function<void(const Reply &)> finish_action) {
    Reply result;
    result.checkpoint = checkpoint;
    result.impl_->finish_action = std::move(finish_action);
    result.impl_->drain_action =
        [request = std::move(request), transport = std::move(transport)](
            Reply &reply) {
            SseParser parser([&reply](std::string_view data) {
                feed_event(reply, *reply.impl_, data);
            });
            HttpResponse response;
            try {
                response = transport(
                    request, [&parser, &reply](std::string_view bytes) {
                        if (!reply.err && !parser.done()) parser.feed(bytes);
                    });
            } catch (const std::exception &error) {
                set_error(reply, ErrorKind::Transport, error.what());
            } catch (...) {
                set_error(reply, ErrorKind::Transport,
                          "串流 transport 發生未知錯誤");
            }
            if (!reply.err) {
                if (!response.error.empty()) {
                    set_error(reply, ErrorKind::Transport, response.error);
                } else if (response.status == 0) {
                    set_error(reply, ErrorKind::Transport,
                              "HTTP transport 沒有回傳狀態碼");
                } else if (response.status < 200 || response.status >= 300) {
                    set_error(reply, ErrorKind::Http,
                              http_message(response.status, response.body));
                }
            }
            reply.finish();
        };
    return result;
}

}  // namespace aos::llms
