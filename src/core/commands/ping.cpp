#include "commands.hpp"

namespace aos::builtin {

asio::awaitable<std::int32_t> ping(CommandContext& context) {
    co_await say(context.session, "pong\n");
    co_return 0;
}

}  // namespace aos::builtin
