#include "aos/llm/bot.hpp"

#include <utility>

namespace aos::llm {
namespace {

const std::vector<ToolCall> no_calls;

}  // namespace

std::span<const ToolCall> Bot::pending_calls() const {
    if (history_.empty() || history_.back().role != "assistant") {
        return no_calls;
    }
    return history_.back().tool_calls;
}

asio::awaitable<Reply> Bot::ask(Turn turn) {
    // 這一輪開始時 history 有多長。整輪落空時要退回這裡 ——
    // 沒問成的話，別在記憶裡留下一個沒人回答的問題。
    const std::size_t checkpoint = history_.size();

    if (auto refusal = co_await llm_.check(!turn.images.empty(),
                                           !tools_.empty(), turn.tool_choice)) {
        Reply reply;
        reply.err = std::move(*refusal);
        co_return reply;
    }

    // 這次真正送出去的訊息 = 人格 + 記憶 + 這一輪新加的。
    std::vector<Message> outgoing;
    outgoing.reserve(history_.size() + turn.tool_results.size() + 2);
    if (!system_.empty()) {
        outgoing.push_back(Message{.role = "system", .content = system_});
    }
    outgoing.insert(outgoing.end(), history_.begin(), history_.end());

    // 新訊息同時進「這次要送的」和（需要的話）「記憶」。
    const auto add = [&](Message message) {
        if (turn.remember) {
            history_.push_back(message);
        }
        outgoing.push_back(std::move(message));
    };

    for (ToolResult& result : turn.tool_results) {
        add(Message{.role = "tool",
                    .content = std::move(result.content),
                    .tool_call_id = std::move(result.call_id)});
    }
    if (!turn.prompt.empty() || !turn.images.empty()) {
        add(Message{.role = "user",
                    .content = std::move(turn.prompt),
                    .images = std::move(turn.images)});
    }

    Reply reply = co_await llm_.ask({
        .messages = outgoing,
        .tools = tools_.schemas,
        .tool_choice = turn.tool_choice,
        .on_part = std::move(turn.on_part),
    });

    if (!turn.remember) {
        co_return reply;
    }

    if (!reply.spoke()) {
        // 整輪落空（還沒開口就斷線）：把這輪送出去的訊息一起收回來，
        // 不然下次會帶著一個沒被回答的問題再問一次。
        history_.resize(checkpoint);
        co_return reply;
    }

    // 有 tool_calls 的一輪要**連工具一起寫回去**，形狀跟端點收的一模一樣，
    // 下一輪送 tool 結果才對得起來。
    history_.push_back(Message{.role = "assistant",
                               .content = reply.text,
                               .tool_calls = reply.calls});
    co_return reply;
}

}  // namespace aos::llm
