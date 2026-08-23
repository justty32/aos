#include <aos/llms.hpp>

#include "llms_internal.hpp"

#include <map>
#include <utility>

namespace aos::llms {

struct ToolCallAccumulator::Impl {
    std::map<std::size_t, RawToolCall> parts;
};

ToolCallAccumulator::ToolCallAccumulator() : impl_(std::make_unique<Impl>()) {}
ToolCallAccumulator::ToolCallAccumulator(ToolCallAccumulator &&) noexcept =
    default;
ToolCallAccumulator &ToolCallAccumulator::operator=(
    ToolCallAccumulator &&) noexcept = default;
ToolCallAccumulator::~ToolCallAccumulator() = default;

void ToolCallAccumulator::feed(const ToolCallDelta &delta) {
    RawToolCall &slot = impl_->parts[delta.index];
    if (!delta.id.empty()) slot.id = delta.id;
    if (!delta.name.empty()) slot.name = delta.name;
    slot.arguments += delta.arguments;
}

bool ToolCallAccumulator::empty() const noexcept {
    return impl_->parts.empty();
}

std::vector<RawToolCall> ToolCallAccumulator::raw() const {
    std::vector<RawToolCall> result;
    result.reserve(impl_->parts.size());
    for (const auto &[index, call] : impl_->parts) {
        static_cast<void>(index);
        result.push_back(call);
    }
    return result;
}

ToolCall tool_call_entry(const RawToolCall &raw) {
    ToolCall result{.id = raw.id, .name = raw.name};
    const json parsed = json::parse(raw.arguments, nullptr, false);
    if (parsed.is_discarded()) {
        result.args.clear();
        result.args_raw = raw.arguments;
    } else {
        result.args = raw.arguments;
    }
    return result;
}

json raw_calls_history(const std::string &content,
                       const std::vector<RawToolCall> &calls) {
    json message = {{"role", "assistant"}};
    if (calls.empty()) {
        message["content"] = content;
        return message;
    }
    message["content"] = content.empty() ? json(nullptr) : json(content);
    message["tool_calls"] = json::array();
    for (const RawToolCall &call : calls) {
        message["tool_calls"].push_back(
            {{"id", call.id},
             {"type", "function"},
             {"function", {{"name", call.name},
                            {"arguments", call.arguments}}}});
    }
    return message;
}

std::string tool_calls_history_json(
    const std::string &content, const std::vector<RawToolCall> &calls) {
    return raw_calls_history(content, calls).dump();
}

}  // namespace aos::llms
