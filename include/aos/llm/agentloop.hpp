#pragma once

// run_agent —— 「說話 → 叫工具 → 把結果餵回去 → 再說話」自動跑到它不再叫工具。
//
// Bot 自己不會跑工具（bot.hpp 那裡刻意留白），因為「誰去跑、要不要放行、跑多久」
// 是策略，不是模型的事。這個檔就是其中一種策略：全自動、有步數上限、可以插一個
// 放行的關卡。不喜歡就自己照 Bot::ask 寫一個，那才是留白的用意。
//
//   AgentOutcome result = co_await run_agent(bot, "把 a.png 縮到 800 寬", {
//       .on_part = [&](PartKind kind, std::string_view text)
//                      -> asio::awaitable<void> {
//           if (kind == PartKind::answer) { co_await session.write_output(text); }
//       },
//   });
//
// 工具函式是同步的（ToolFunction），所以會在 **另一條執行緒** 上跑
// （見 aos/blocking.hpp），io_context 不會被一個慢工具卡住。

#include "aos/llm/bot.hpp"
#include "aos/llm/message.hpp"
#include "aos/llm/reply.hpp"

#include <asio/awaitable.hpp>

#include <functional>
#include <optional>
#include <string>
#include <string_view>

namespace aos::llm {

struct AgentOptions {
    // 最多來回幾次。上限的存在是因為模型會**繞圈**：叫同一個工具、拿到同樣的
    // 錯誤、再叫一次。沒有上限的話那是一個燒錢的無窮迴圈。
    int max_steps = 12;

    // 串流用。每一步都會接上去。
    PartHandler on_part = nullptr;

    // 每次要跑工具前問一次，回 false 就不跑，改回一句話給模型。
    // 不給就是全部放行。
    std::function<asio::awaitable<bool>(const ToolCall&)> approve = nullptr;

    // 工具跑完了的通知，拿來印進度。
    std::function<asio::awaitable<void>(const ToolCall&, std::string_view)>
        on_tool = nullptr;
};

struct AgentOutcome {
    // 最後一步說的話。
    std::string text;

    // 總共來回了幾次。
    int steps = 0;

    // 撞到 max_steps 才停的。這不是錯誤，但通常表示模型在繞圈。
    bool hit_step_limit = false;

    std::optional<std::string> err;

    [[nodiscard]] explicit operator bool() const { return !err.has_value(); }
};

[[nodiscard]] asio::awaitable<AgentOutcome> run_agent(Bot& bot,
                                                      std::string instruction,
                                                      AgentOptions options = {});

}  // namespace aos::llm
