// 把端點回來的東西拆成 Reply。純函式加一個累積器，不碰網路。
#include "aos/llm/wire.hpp"

#include <nlohmann/json.hpp>

#include <format>
#include <string>
#include <utility>

namespace aos::llm {
namespace {

using nlohmann::json;

// 缺欄位、型別不對、是 null，都當成「沒有」。端點之間的差異多半就在這裡，
// 為了一個少掉的欄位丟例外只會讓整條斷掉。
template <typename T>
[[nodiscard]] std::optional<T> pick(const json& object, std::string_view key) {
    const auto found = object.find(key);
    if (found == object.end() || found->is_null()) {
        return std::nullopt;
    }
    if constexpr (std::is_same_v<T, std::string>) {
        if (!found->is_string()) {
            return std::nullopt;
        }
    } else {
        if (!found->is_number_integer()) {
            return std::nullopt;
        }
    }
    return found->get<T>();
}

[[nodiscard]] std::string text_at(const json& object, std::string_view key) {
    return pick<std::string>(object, key).value_or(std::string{});
}

// 思考內容有兩個欄位名在流通，兩個都讀。
[[nodiscard]] std::string thought_of(const json& object) {
    auto value = text_at(object, "reasoning_content");
    return value.empty() ? text_at(object, "reasoning") : value;
}

[[nodiscard]] std::optional<Usage> read_usage(const json& parent) {
    const auto found = parent.find("usage");
    if (found == parent.end() || !found->is_object()) {
        return std::nullopt;
    }
    Usage usage;
    usage.prompt = pick<int>(*found, "prompt_tokens");
    usage.completion = pick<int>(*found, "completion_tokens");
    usage.total = pick<int>(*found, "total_tokens");

    const auto prompt_details = found->find("prompt_tokens_details");
    if (prompt_details != found->end() && prompt_details->is_object()) {
        usage.cached = pick<int>(*prompt_details, "cached_tokens");
    }
    const auto completion_details = found->find("completion_tokens_details");
    if (completion_details != found->end() && completion_details->is_object()) {
        usage.reasoning = pick<int>(*completion_details, "reasoning_tokens");
    }
    return usage;
}

[[nodiscard]] std::vector<ToolCall> read_tool_calls(const json& message) {
    std::vector<ToolCall> calls;
    const auto found = message.find("tool_calls");
    if (found == message.end() || !found->is_array()) {
        return calls;
    }
    for (const json& entry : *found) {
        if (!entry.is_object()) {
            continue;
        }
        const auto function = entry.find("function");
        if (function == entry.end() || !function->is_object()) {
            continue;
        }
        calls.push_back(ToolCall{
            .id = text_at(entry, "id"),
            .name = text_at(*function, "name"),
            .arguments = text_at(*function, "arguments"),
        });
    }
    return calls;
}

// 端點回錯誤時的形狀：{"error": {"message": "..."}}，也有直接給字串的。
[[nodiscard]] std::optional<std::string> read_error(const json& body) {
    const auto found = body.find("error");
    if (found == body.end() || found->is_null()) {
        return std::nullopt;
    }
    if (found->is_string()) {
        return found->get<std::string>();
    }
    if (found->is_object()) {
        auto message = text_at(*found, "message");
        return message.empty() ? found->dump() : message;
    }
    return found->dump();
}

}  // namespace

Reply parse_completion(std::string_view body) {
    Reply reply;

    const json parsed = json::parse(body, nullptr, false);
    if (parsed.is_discarded() || !parsed.is_object()) {
        reply.err = std::format("回應不是合法的 JSON object：{}",
                                body.substr(0, 200));
        return reply;
    }
    if (auto failure = read_error(parsed)) {
        reply.err = std::move(*failure);
        return reply;
    }

    const auto choices = parsed.find("choices");
    if (choices == parsed.end() || !choices->is_array() || choices->empty()) {
        reply.err = "回應裡沒有 choices";
        return reply;
    }

    const json& choice = choices->front();
    reply.finish_reason = text_at(choice, "finish_reason");
    reply.usage = read_usage(parsed);

    const auto message = choice.find("message");
    if (message == choice.end() || !message->is_object()) {
        reply.err = "choices[0] 裡沒有 message";
        return reply;
    }
    reply.text = text_at(*message, "content");
    reply.reasoning = thought_of(*message);
    reply.calls = read_tool_calls(*message);
    return reply;
}

std::vector<StreamAccumulator::Part> StreamAccumulator::feed(
    std::string_view bytes) {
    pending_.append(bytes);

    // 收到的每一段都可能切在半行中間，所以只處理已經完整的行，剩下的留著。
    const std::size_t before_text = text_.size();
    const std::size_t before_reasoning = reasoning_.size();

    std::size_t start = 0;
    for (;;) {
        const std::size_t line_end = pending_.find('\n', start);
        if (line_end == std::string::npos) {
            break;
        }
        std::string_view line{pending_.data() + start, line_end - start};
        if (!line.empty() && line.back() == '\r') {
            line.remove_suffix(1);
        }
        eat_line(line);
        start = line_end + 1;
    }
    pending_.erase(0, start);

    std::vector<Part> parts;
    if (reasoning_.size() > before_reasoning) {
        parts.push_back(Part{.kind = PartKind::think,
                             .text = reasoning_.substr(before_reasoning)});
    }
    if (text_.size() > before_text) {
        parts.push_back(
            Part{.kind = PartKind::answer, .text = text_.substr(before_text)});
    }
    return parts;
}

void StreamAccumulator::eat_line(std::string_view line) {
    // SSE 的空行是事件邊界，註解以 ':' 開頭。兩種都沒有內容。
    if (line.empty() || line.starts_with(':')) {
        return;
    }
    if (!line.starts_with("data:")) {
        return;  // event: / id: / retry: 這幾種我們用不到
    }
    line.remove_prefix(5);
    while (!line.empty() && line.front() == ' ') {
        line.remove_prefix(1);
    }
    if (line == "[DONE]") {
        saw_done_ = true;
        return;
    }

    const json chunk = json::parse(line, nullptr, false);
    if (chunk.is_discarded() || !chunk.is_object()) {
        error_ = std::format("串流裡有一行看不懂：{}", line.substr(0, 200));
        return;
    }
    if (auto failure = read_error(chunk)) {
        error_ = std::move(*failure);
        return;
    }

    // 開了 include_usage 的話，最後一片只帶 usage、沒有 choices。
    if (auto usage = read_usage(chunk)) {
        usage_ = std::move(usage);
    }
    const auto choices = chunk.find("choices");
    if (choices == chunk.end() || !choices->is_array() || choices->empty()) {
        return;
    }

    const json& choice = choices->front();
    if (auto reason = pick<std::string>(choice, "finish_reason");
        reason && !reason->empty()) {
        finish_reason_ = std::move(*reason);
    }

    const auto delta = choice.find("delta");
    if (delta == choice.end() || !delta->is_object()) {
        return;
    }
    reasoning_ += thought_of(*delta);
    text_ += text_at(*delta, "content");

    // 工具呼叫是碎片：id 和 name 通常只在第一片出現，arguments 一小段一小段接。
    const auto tool_calls = delta->find("tool_calls");
    if (tool_calls == delta->end() || !tool_calls->is_array()) {
        return;
    }
    for (const json& entry : *tool_calls) {
        if (!entry.is_object()) {
            continue;
        }
        ToolCall& slot = calls_[pick<int>(entry, "index").value_or(0)];
        if (auto id = pick<std::string>(entry, "id"); id && !id->empty()) {
            slot.id = std::move(*id);
        }
        const auto function = entry.find("function");
        if (function == entry.end() || !function->is_object()) {
            continue;
        }
        if (auto name = pick<std::string>(*function, "name");
            name && !name->empty()) {
            slot.name = std::move(*name);
        }
        slot.arguments += text_at(*function, "arguments");
    }
}

Reply StreamAccumulator::finish() {
    Reply reply;
    reply.text = std::move(text_);
    reply.reasoning = std::move(reasoning_);
    reply.finish_reason = std::move(finish_reason_);
    reply.usage = std::move(usage_);
    for (auto& [index, call] : calls_) {
        reply.calls.push_back(std::move(call));
    }
    if (error_) {
        reply.err = std::move(error_);
    } else if (!saw_done_ && !reply.spoke()) {
        // 一個字都沒收到又沒看到結束標記：這不是「模型沒話說」，是斷線。
        reply.err = "串流還沒開始就結束了";
    }
    return reply;
}

std::vector<std::pair<std::string, Caps>> parse_model_info(
    std::string_view body) {
    std::vector<std::pair<std::string, Caps>> table;

    const json parsed = json::parse(body, nullptr, false);
    if (parsed.is_discarded() || !parsed.is_object()) {
        return table;
    }
    const auto data = parsed.find("data");
    if (data == parsed.end() || !data->is_array()) {
        return table;
    }

    for (const json& entry : *data) {
        if (!entry.is_object()) {
            continue;
        }
        auto name = pick<std::string>(entry, "model_name");
        if (!name || name->empty()) {
            continue;
        }
        const auto info = entry.find("model_info");
        if (info == entry.end() || !info->is_object()) {
            table.emplace_back(std::move(*name), Caps{});
            continue;
        }
        // 讀不到就是 nullopt（不知道），不是 false。三態不能壓成兩態。
        const auto flag =
            [&info](std::string_view key) -> std::optional<bool> {
            const auto found = info->find(key);
            if (found == info->end() || !found->is_boolean()) {
                return std::nullopt;
            }
            return found->get<bool>();
        };
        table.emplace_back(
            std::move(*name),
            Caps{
                .tools = flag("supports_function_calling"),
                .tool_choice = flag("supports_tool_choice"),
                .parallel_tools = flag("supports_parallel_function_calling"),
                .vision = flag("supports_vision"),
                .reasoning = flag("supports_reasoning"),
                .json_schema = flag("supports_response_schema"),
                .caching = flag("supports_prompt_caching"),
            });
    }
    return table;
}

}  // namespace aos::llm
