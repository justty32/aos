#pragma once

// Bot —— 人格、記憶、能力，加一顆思考引擎。
//
//   人格   system，每次送出時排在最前面，不佔記憶
//   記憶   history，對話記錄（含 assistant 的 tool_calls 和工具結果）
//   能力   tools，它能開口要求哪些工具 —— 但**執行不歸它管**
//   引擎   llm，拿什麼在想（engine.hpp）
//
//   Bot bot{Llm{{.model = "deepseek-chat"}}, "請簡短回答。"};
//   Reply reply = co_await bot.ask({.prompt = "你好"});
//   std::println("{}", reply.text);
//
// ask() 永遠回一個 Reply，不丟例外。bot 只會說話和開口要工具；工具是誰去跑的、
// 跑出什麼，由呼叫端決定之後餵回來（或交給 agentloop.hpp 自動跑）。

#include "aos/llm/engine.hpp"
#include "aos/llm/message.hpp"
#include "aos/llm/reply.hpp"
#include "aos/llm/tool.hpp"

#include <asio/awaitable.hpp>

#include <span>
#include <string>
#include <utility>
#include <vector>

namespace aos::llm {

class Bot {
public:
    explicit Bot(Llm llm, std::string system = {}, ToolSet tools = {})
        : llm_{std::move(llm)},
          system_{std::move(system)},
          tools_{std::move(tools)} {}

    [[nodiscard]] Llm& llm() { return llm_; }
    [[nodiscard]] const ToolSet& tools() const { return tools_; }
    void set_tools(ToolSet tools) { tools_ = std::move(tools); }

    [[nodiscard]] std::span<const Message> history() const { return history_; }

    // 清空記憶。人格、能力、引擎都不動。
    void reset() { history_.clear(); }

    // 它要求了、但你還沒把結果餵回去的工具呼叫。沒欠就是空的。
    //
    // 欠著的時候直接再問一句話會被端點打回票：帶 tool_calls 的 assistant
    // message 後面一定要接上對應的 tool message。
    [[nodiscard]] std::span<const ToolCall> pending_calls() const;

    // 說給它聽的東西有三種，可以同時給，會照 tool_results → prompt 的順序排。
    struct Turn {
        std::string prompt;

        // 本機路徑或 http(s) 網址。
        std::vector<std::string> images;

        // 等於跟它說「你要的那幾個工具跑出了這些」。
        std::vector<ToolResult> tool_results;

        // "auto" / "none" / "required"，或一整段指定 function 的 JSON。
        std::string tool_choice;

        // false 就不寫進 history（問一句不想留下的話）。
        bool remember = true;

        // 給了就是串流。
        PartHandler on_part = nullptr;
    };

    [[nodiscard]] asio::awaitable<Reply> ask(Turn turn);

private:
    Llm llm_;
    std::string system_;
    ToolSet tools_;
    std::vector<Message> history_;  // 不含 system，送出時才在最前面補上
};

}  // namespace aos::llm
