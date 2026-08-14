#include "commands.hpp"

#include <chrono>
#include <format>

namespace aos::builtin {

// 重點是證明 daemon 真的是常駐的：連續跑兩次，uptime 會變大、served 會累加，
// 因為 Runtime 活在整個 daemon 生命週期裡，而不是每條連線各一份。
asio::awaitable<std::int32_t> daemon_status(CommandContext& context) {
    const auto uptime = std::chrono::duration_cast<std::chrono::seconds>(
        context.runtime.uptime());

    co_await say(context.session,
                 std::format("uptime = {}\nserved  = {} 次請求\n", uptime,
                             context.runtime.served_requests()));
    co_return 0;
}

asio::awaitable<std::int32_t> daemon_stop(CommandContext& context) {
    // 只是停止接受新連線。這條連線自己還要把回應寫完，所以不能硬砍 io_context。
    context.runtime.request_stop();
    co_await say(context.session, "aos-daemon 收工中\n");
    co_return 0;
}

}  // namespace aos::builtin
