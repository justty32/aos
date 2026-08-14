#pragma once

// aos_core 內部用的標頭：每個內建命令的宣告。
//
// 新增一個命令的完整步驟：
//   1. 在 src/core/commands/ 加一個 .cpp，寫一個
//      asio::awaitable<std::int32_t> f(CommandContext&) 形狀的函式。
//   2. 在這裡加一行宣告。
//   3. 在 registry.cpp 的表裡加一列（子命令就加進對應的子表）。
// CMake 是用 glob 掃 src/core/，新檔案不必手動加進建置。

#include "aos/command.hpp"

#include <asio/awaitable.hpp>

#include <cstdint>

namespace aos::builtin {

asio::awaitable<std::int32_t> ping(CommandContext& context);
asio::awaitable<std::int32_t> echo(CommandContext& context);
asio::awaitable<std::int32_t> help(CommandContext& context);

// `aos daemon ...` 這一組。
asio::awaitable<std::int32_t> daemon_status(CommandContext& context);
asio::awaitable<std::int32_t> daemon_stop(CommandContext& context);

// `aos llm ...` 這一組。設定走環境變數，見 llm.cpp。
asio::awaitable<std::int32_t> llm_ask(CommandContext& context);
asio::awaitable<std::int32_t> llm_models(CommandContext& context);
asio::awaitable<std::int32_t> llm_tools(CommandContext& context);

// 沒對上任何名字時的後備：把收到的東西原樣列出來，方便除錯。
asio::awaitable<std::int32_t> describe(CommandContext& context);

}  // namespace aos::builtin
