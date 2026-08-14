#include "commands.hpp"

namespace aos::builtin {

asio::awaitable<std::int32_t> help(CommandContext& context) {
    // 明確要求的說明是正常輸出，走 stdout。
    co_await say(context.session, render_command_list({}, commands()));
    co_return 0;
}

}  // namespace aos::builtin
