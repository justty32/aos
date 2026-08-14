#include "aos/client.hpp"

#include "aos/channel.hpp"
#include "input.hpp"

#include <asio/co_spawn.hpp>
#include <asio/io_context.hpp>
#include <asio/local/stream_protocol.hpp>

#include <cstdint>
#include <cstdio>
#include <exception>
#include <string_view>
#include <system_error>

namespace aos {
namespace {

void write_raw(std::FILE* stream, std::string_view bytes) {
    if (bytes.empty()) {
        return;
    }
    // 立刻 flush，否則 `tail -f x | aos echo` 的輸出會卡在 libc 緩衝區裡。
    if (std::fwrite(bytes.data(), 1, bytes.size(), stream) != bytes.size() ||
        std::fflush(stream) != 0) {
        throw std::system_error{errno, std::generic_category(), "寫入輸出失敗"};
    }
}

[[nodiscard]] asio::awaitable<std::int32_t> receive_output(LocalSocket& socket) {
    while (true) {
        const auto frame = co_await read_frame(socket);
        switch (frame.kind) {
        case FrameKind::stdout_chunk:
            write_raw(stdout, frame.payload);
            break;
        case FrameKind::stderr_chunk:
            write_raw(stderr, frame.payload);
            break;
        case FrameKind::exit: {
            const auto exit_code = decode_exit(frame.payload);
            if (!exit_code) {
                throw ProtocolError{exit_code.error()};
            }
            co_return *exit_code;
        }
        default:
            throw ProtocolError{"daemon 回傳了方向錯誤的訊框"};
        }
    }
}

[[nodiscard]] asio::awaitable<std::int32_t>
run_session(LocalSocket& socket, const Request& request) {
    const auto start = encode_request_start(request);
    if (!start) {
        throw ProtocolError{start.error()};
    }
    co_await write_frame(socket, FrameKind::request_start, *start);

    // stdin 邊讀邊送，跟下面收輸出的迴圈同時進行。少了這個併行，
    // stdin 沒 EOF 之前一個字都印不出來。
    const auto executor = co_await asio::this_coro::executor;
    asio::co_spawn(executor, detail::forward_standard_input(socket),
                   detail::report_input_failure);

    co_return co_await receive_output(socket);
}

}  // namespace

int run_client(const Request& request,
               const std::filesystem::path& socket_path) {
    asio::io_context context;
    LocalSocket socket{context};
    socket.connect(asio::local::stream_protocol::endpoint{socket_path.string()});

    std::int32_t exit_code = 1;
    std::exception_ptr failure;
    asio::co_spawn(context, run_session(socket, request),
                   [&](std::exception_ptr error, std::int32_t code) {
                       failure = error;
                       exit_code = code;
                       // daemon 已經回報結束，還在等 stdin 的那條 coroutine
                       // 不必再理會，直接讓 run() 收工。
                       context.stop();
                   });
    context.run();

    if (failure) {
        std::rethrow_exception(failure);
    }
    return exit_code;
}

}  // namespace aos
