#include "aos/llm/agentloop.hpp"

#include "aos/blocking.hpp"

#include <format>
#include <utility>

namespace aos::llm {

asio::awaitable<AgentOutcome> run_agent(Bot& bot, std::string instruction,
                                        AgentOptions options) {
    AgentOutcome outcome;

    Bot::Turn turn{.prompt = std::move(instruction), .on_part = options.on_part};

    while (outcome.steps < options.max_steps) {
        ++outcome.steps;

        Reply reply = co_await bot.ask(std::move(turn));
        turn = Bot::Turn{.on_part = options.on_part};

        if (!reply) {
            outcome.err = reply.err;
            co_return outcome;
        }
        outcome.text = reply.text;

        if (reply.calls.empty()) {
            co_return outcome;  // 它不再要工具了，這一輪就是答案
        }

        // 它要的每一個工具都得回一則 tool message，**一個都不能少** ——
        // 少一個的話，下一次送出去會被端點打回票。所以放行被拒、工具不存在，
        // 這些情況也都要回一句話，只是內容不同。
        for (const ToolCall& call : reply.calls) {
            const ToolFunction* function = bot.tools().find(call.name);

            std::string output;
            if (function == nullptr) {
                output = std::format(
                    "Error: 沒有叫做 {} 的工具，不要再叫它了", call.name);
            } else if (options.approve &&
                       !co_await options.approve(call)) {
                output = "Error: 使用者沒有放行這次呼叫";
            } else {
                // 工具是同步的，可能開子行程、可能讀大檔，所以搬到別的執行緒。
                // 複製一份參數進去：那條執行緒不該碰這裡的東西。
                std::string arguments = call.arguments;
                const ToolFunction& run = *function;
                output = co_await run_blocking(
                    [&run, arguments = std::move(arguments)] {
                        return run(arguments);
                    });
            }

            if (options.on_tool) {
                co_await options.on_tool(call, output);
            }
            turn.tool_results.push_back(
                ToolResult{.call_id = call.id, .content = std::move(output)});
        }
    }

    outcome.hit_step_limit = true;
    co_return outcome;
}

}  // namespace aos::llm
