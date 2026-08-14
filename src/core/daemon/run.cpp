#include "aos/daemon.hpp"

#include "aos/runtime.hpp"
#include "connection.hpp"
#include "socket_setup.hpp"

#include <asio/co_spawn.hpp>
#include <asio/io_context.hpp>
#include <asio/local/stream_protocol.hpp>
#include <asio/redirect_error.hpp>
#include <asio/signal_set.hpp>
#include <asio/use_awaitable.hpp>

#include <csignal>
#include <exception>
#include <print>
#include <system_error>
#include <utility>

#include <sys/stat.h>

namespace aos {
namespace {

asio::awaitable<void>
accept_connections(asio::local::stream_protocol::acceptor& acceptor,
                   Runtime& runtime) {
    const auto executor = co_await asio::this_coro::executor;
    while (true) {
        std::error_code error;
        auto socket = co_await acceptor.async_accept(
            asio::redirect_error(asio::use_awaitable, error));
        if (error == asio::error::operation_aborted) {
            co_return;
        }
        if (error) {
            throw std::system_error{error, "接受連線失敗"};
        }
        // 每條連線獨立跑，慢的命令不會擋住別人。
        asio::co_spawn(executor, detail::serve(std::move(socket), runtime),
                       detail::report_session_error);
    }
}

}  // namespace

int run_daemon(const std::filesystem::path& socket_path) {
    asio::io_context context;
    detail::prepare_socket_path(context, socket_path);

    const asio::local::stream_protocol::endpoint endpoint{socket_path.string()};
    asio::local::stream_protocol::acceptor acceptor{context};
    acceptor.open(endpoint.protocol());
    acceptor.bind(endpoint);
    detail::SocketPathGuard path_guard{socket_path};

    // 只有自己讀得到寫得到，別的使用者連不進來。
    if (::chmod(socket_path.c_str(), S_IRUSR | S_IWUSR) < 0) {
        throw std::system_error{errno, std::generic_category(),
                                "設定 socket 權限失敗"};
    }
    acceptor.listen();

    // 這份狀態活過每一條連線，所以命令可以在這裡累積跨呼叫的東西。
    Runtime runtime{context};

    // 停止接受新連線就等於收工：accept_connections 會返回，等在跑的連線做完，
    // io_context 沒事可做，run() 自然回來。`aos daemon stop` 走的也是這條路。
    const auto stop_accepting = [&acceptor] {
        std::error_code ignored;
        acceptor.close(ignored);
    };
    runtime.set_stop_handler(stop_accepting);

    asio::signal_set signals{context, SIGINT, SIGTERM};
    signals.async_wait([&](const std::error_code&, int) { stop_accepting(); });

    std::exception_ptr accept_failure;
    asio::co_spawn(context, accept_connections(acceptor, runtime),
                   [&](std::exception_ptr failure) {
                       accept_failure = failure;
                       if (failure) {
                           context.stop();
                       }
                   });

    std::println("aos-daemon 正在監聽 {}", socket_path.string());
    context.run();
    if (accept_failure) {
        std::rethrow_exception(accept_failure);
    }
    return 0;
}

}  // namespace aos
