#include "aos/daemon.hpp"

#include "aos/channel.hpp"
#include "aos/command.hpp"

#include <asio/co_spawn.hpp>
#include <asio/detached.hpp>
#include <asio/io_context.hpp>
#include <asio/redirect_error.hpp>
#include <asio/signal_set.hpp>
#include <asio/use_awaitable.hpp>

#include <algorithm>
#include <cerrno>
#include <csignal>
#include <iostream>
#include <stdexcept>
#include <string_view>

#include <sys/stat.h>
#include <unistd.h>

namespace aos {
namespace {

class SocketPathGuard {
public:
    explicit SocketPathGuard(std::filesystem::path path)
        : path_{std::move(path)} {}
    ~SocketPathGuard() { ::unlink(path_.c_str()); }

    SocketPathGuard(const SocketPathGuard&) = delete;
    SocketPathGuard& operator=(const SocketPathGuard&) = delete;

private:
    std::filesystem::path path_;
};

void prepare_socket_path(asio::io_context& context,
                         const std::filesystem::path& path) {
    struct stat status {};
    if (::lstat(path.c_str(), &status) < 0) {
        if (errno == ENOENT) {
            return;
        }
        throw std::system_error{errno, std::generic_category(),
                                "檢查 socket 路徑失敗"};
    }
    if (!S_ISSOCK(status.st_mode) || status.st_uid != ::getuid()) {
        throw std::runtime_error{"既有路徑不是目前使用者擁有的 socket：" +
                                 path.string()};
    }

    LocalSocket probe{context};
    std::error_code error;
    probe.connect(asio::local::stream_protocol::endpoint{path.string()}, error);
    if (!error) {
        throw std::runtime_error{"已有 aos-daemon 正在監聽 " + path.string()};
    }
    if (error != asio::error::connection_refused) {
        throw std::system_error{error, "檢查既有 socket 失敗"};
    }
    if (::unlink(path.c_str()) < 0) {
        throw std::system_error{errno, std::generic_category(),
                                "移除殘留 socket 失敗"};
    }
}

[[nodiscard]] asio::awaitable<Request> receive_request(LocalSocket& socket) {
    auto first = co_await async_read_frame(socket);
    if (first.kind != FrameKind::request_start) {
        throw std::runtime_error{"連線的第一個訊框不是 request_start"};
    }
    auto request = decode_request_start(first.payload);
    if (!request) {
        throw std::runtime_error{request.error()};
    }

    while (true) {
        auto frame = co_await async_read_frame(socket);
        if (frame.kind == FrameKind::stdin_end) {
            co_return std::move(*request);
        }
        if (frame.kind != FrameKind::stdin_chunk) {
            throw std::runtime_error{"stdin 尚未結束就收到其他訊框"};
        }
        if (frame.payload.size() >
            maximum_frame_size - request->standard_input.size()) {
            throw std::runtime_error{"stdin 超過 8 MiB 上限"};
        }
        request->standard_input += frame.payload;
    }
}

asio::awaitable<void> send_chunks(LocalSocket& socket, FrameKind kind,
                                  std::string_view bytes) {
    while (!bytes.empty()) {
        const auto count = std::min(bytes.size(), stream_chunk_size);
        co_await async_write_frame(socket, kind, bytes.substr(0, count));
        bytes.remove_prefix(count);
    }
}

asio::awaitable<void> send_response(LocalSocket& socket,
                                    const Response& response) {
    co_await send_chunks(socket, FrameKind::stdout_chunk,
                         response.standard_output);
    co_await send_chunks(socket, FrameKind::stderr_chunk,
                         response.standard_error);
    co_await async_write_frame(socket, FrameKind::exit,
                               encode_exit(response.exit_code));
}

asio::awaitable<void> serve(LocalSocket socket) {
    Response response;
    try {
        const auto request = co_await receive_request(socket);
        response = handle_command(request);
    } catch (const std::system_error&) {
        // 連線本身失效時無法再回覆，交給 session completion handler 處理。
        throw;
    } catch (const std::runtime_error& error) {
        response = {
            .exit_code = 2,
            .standard_output = {},
            .standard_error = std::string{error.what()} + '\n',
        };
    }
    co_await send_response(socket, response);
}

void report_session_error(std::exception_ptr failure) {
    if (!failure) {
        return;
    }
    try {
        std::rethrow_exception(failure);
    } catch (const std::system_error& error) {
        if (error.code() != asio::error::eof &&
            error.code() != asio::error::operation_aborted) {
            std::cerr << "aos-daemon：" << error.what() << '\n';
        }
    } catch (const std::exception& error) {
        std::cerr << "aos-daemon：" << error.what() << '\n';
    }
}

asio::awaitable<void>
accept_connections(asio::local::stream_protocol::acceptor& acceptor) {
    auto executor = co_await asio::this_coro::executor;
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
        asio::co_spawn(executor, serve(std::move(socket)), report_session_error);
    }
}

}  // namespace

int run_daemon(const std::filesystem::path& socket_path) {
    asio::io_context context;
    prepare_socket_path(context, socket_path);

    const asio::local::stream_protocol::endpoint endpoint{socket_path.string()};
    asio::local::stream_protocol::acceptor acceptor{context};
    acceptor.open(endpoint.protocol());
    acceptor.bind(endpoint);
    SocketPathGuard path_guard{socket_path};
    if (::chmod(socket_path.c_str(), S_IRUSR | S_IWUSR) < 0) {
        throw std::system_error{errno, std::generic_category(),
                                "設定 socket 權限失敗"};
    }
    acceptor.listen();

    asio::signal_set signals{context, SIGINT, SIGTERM};
    signals.async_wait([&](const std::error_code&, int) {
        std::error_code ignored;
        acceptor.close(ignored);
        context.stop();
    });

    std::exception_ptr accept_failure;
    asio::co_spawn(context, accept_connections(acceptor),
                   [&](std::exception_ptr failure) {
                       accept_failure = failure;
                       if (failure) {
                           context.stop();
                       }
                   });

    std::cout << "aos-daemon 正在監聽 " << socket_path.string() << '\n';
    context.run();
    if (accept_failure) {
        std::rethrow_exception(accept_failure);
    }
    return 0;
}

}  // namespace aos
