#include "connection.hpp"

#include "aos/command.hpp"

#include <cstdint>
#include <exception>
#include <format>
#include <print>
#include <system_error>
#include <utility>

namespace aos::detail {
namespace {

[[nodiscard]] asio::awaitable<Request> receive_request(LocalSocket& socket) {
    const auto frame = co_await read_frame(socket);
    if (frame.kind != FrameKind::request_start) {
        throw ProtocolError{"連線的第一個訊框不是 request_start"};
    }
    auto request = decode_request_start(frame.payload);
    if (!request) {
        throw ProtocolError{request.error()};
    }
    co_return std::move(*request);
}

}  // namespace

asio::awaitable<std::string> ConnectionSession::read_input() {
    if (input_ended_) {
        co_return std::string{};
    }
    auto frame = co_await read_frame(socket_);
    if (frame.kind == FrameKind::stdin_end) {
        input_ended_ = true;
        co_return std::string{};
    }
    if (frame.kind != FrameKind::stdin_chunk) {
        throw ProtocolError{"stdin 尚未結束就收到其他訊框"};
    }
    co_return std::move(frame.payload);
}

asio::awaitable<void> ConnectionSession::write_output(std::string_view text) {
    co_await write_stream(socket_, FrameKind::stdout_chunk, text);
}

asio::awaitable<void> ConnectionSession::write_error(std::string_view text) {
    co_await write_stream(socket_, FrameKind::stderr_chunk, text);
}

asio::awaitable<void> ConnectionSession::drain_input() {
    while (!input_ended_) {
        co_await read_input();
    }
}

asio::awaitable<void> serve(LocalSocket socket, Runtime& runtime) {
    ConnectionSession session{socket};
    std::int32_t exit_code = 0;

    // catch 區塊裡不能 co_await，所以先把訊息接出來，離開 catch 再回覆。
    std::string protocol_error;
    try {
        const auto request = co_await receive_request(socket);
        exit_code = co_await handle_command(request, session, runtime);
        co_await session.drain_input();
    } catch (const ProtocolError& error) {
        // 協定層的錯誤還能回覆對方；傳輸層壞掉（system_error）就直接往上拋，
        // 交給 report_session_error。
        protocol_error = std::format("{}\n", error.what());
    }
    if (!protocol_error.empty()) {
        co_await complain(session, std::move(protocol_error));
        exit_code = 2;
    }

    co_await write_frame(socket, FrameKind::exit, encode_exit(exit_code));
}

void report_session_error(std::exception_ptr failure) {
    if (!failure) {
        return;
    }
    try {
        std::rethrow_exception(failure);
    } catch (const std::system_error& error) {
        // client 中途離線是正常的，不值得吵。
        if (error.code() != asio::error::eof &&
            error.code() != asio::error::broken_pipe &&
            error.code() != asio::error::operation_aborted) {
            std::println(stderr, "aos-daemon：{}", error.what());
        }
    } catch (const std::exception& error) {
        std::println(stderr, "aos-daemon：{}", error.what());
    }
}

}  // namespace aos::detail
