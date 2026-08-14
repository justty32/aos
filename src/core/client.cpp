#include "aos/client.hpp"

#include "aos/channel.hpp"

#include <asio/io_context.hpp>
#include <asio/local/stream_protocol.hpp>

#include <algorithm>
#include <array>
#include <iostream>
#include <stdexcept>

#include <unistd.h>

namespace aos {
namespace {

void send_chunked(LocalSocket& socket, FrameKind kind,
                  std::string_view bytes) {
    while (!bytes.empty()) {
        const auto count = std::min(bytes.size(), stream_chunk_size);
        write_frame(socket, kind, bytes.substr(0, count));
        bytes.remove_prefix(count);
    }
}

void send_input(LocalSocket& socket, const Request& request) {
    const auto start = encode_request_start(request);
    if (!start) {
        throw std::runtime_error{start.error()};
    }
    write_frame(socket, FrameKind::request_start, *start);

    std::size_t total = request.standard_input.size();
    if (total > maximum_frame_size) {
        throw std::runtime_error{"stdin 超過 8 MiB 上限"};
    }
    send_chunked(socket, FrameKind::stdin_chunk, request.standard_input);

    // 直接從終端呼叫時不可等待 EOF；pipe 或重新導向才讀取 stdin。
    if (!::isatty(STDIN_FILENO)) {
        std::array<char, stream_chunk_size> buffer{};
        while (std::cin) {
            std::cin.read(buffer.data(),
                          static_cast<std::streamsize>(buffer.size()));
            const auto count = static_cast<std::size_t>(std::cin.gcount());
            if (count > maximum_frame_size - total) {
                throw std::runtime_error{"stdin 超過 8 MiB 上限"};
            }
            write_frame(socket, FrameKind::stdin_chunk,
                        std::string_view{buffer.data(), count});
            total += count;
        }
        if (!std::cin.eof()) {
            throw std::runtime_error{"讀取 stdin 失敗"};
        }
    }
    write_frame(socket, FrameKind::stdin_end, {});
}

[[nodiscard]] int receive_output(LocalSocket& socket) {
    while (true) {
        auto frame = read_frame(socket);
        switch (frame.kind) {
        case FrameKind::stdout_chunk:
            std::cout.write(frame.payload.data(),
                            static_cast<std::streamsize>(frame.payload.size()));
            break;
        case FrameKind::stderr_chunk:
            std::cerr.write(frame.payload.data(),
                            static_cast<std::streamsize>(frame.payload.size()));
            break;
        case FrameKind::exit: {
            const auto exit_code = decode_exit(frame.payload);
            if (!exit_code) {
                throw std::runtime_error{exit_code.error()};
            }
            return *exit_code;
        }
        default:
            throw std::runtime_error{"daemon 回傳了方向錯誤的訊框"};
        }
        if (!std::cout || !std::cerr) {
            throw std::runtime_error{"寫入 stdout 或 stderr 失敗"};
        }
    }
}

}  // namespace

int run_client(Request request, const std::filesystem::path& socket_path) {
    asio::io_context context;
    LocalSocket socket{context};
    socket.connect(asio::local::stream_protocol::endpoint{socket_path.string()});
    send_input(socket, request);
    return receive_output(socket);
}

}  // namespace aos
