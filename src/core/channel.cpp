#include "aos/channel.hpp"

#include <asio/buffer.hpp>
#include <asio/read.hpp>
#include <asio/use_awaitable.hpp>
#include <asio/write.hpp>

#include <algorithm>
#include <array>
#include <span>

namespace aos {
namespace {

using HeaderBytes = std::array<char, frame_header_size>;

[[nodiscard]] HeaderBytes encode_header(FrameKind kind,
                                        std::size_t payload_size) {
    if (payload_size > maximum_payload_size) {
        throw ProtocolError{"訊框 payload 超過 8 MiB 上限"};
    }
    const auto size = static_cast<std::uint32_t>(payload_size);
    return {
        static_cast<char>((size >> 24U) & 0xffU),
        static_cast<char>((size >> 16U) & 0xffU),
        static_cast<char>((size >> 8U) & 0xffU),
        static_cast<char>(size & 0xffU),
        static_cast<char>(kind),
    };
}

struct Header {
    std::size_t payload_size;
    FrameKind kind;
};

[[nodiscard]] Header decode_header(std::span<const char, frame_header_size> bytes) {
    std::uint32_t size = 0;
    for (const char byte : bytes.first<4>()) {
        size = (size << 8U) | static_cast<unsigned char>(byte);
    }
    if (size > maximum_payload_size) {
        throw ProtocolError{"訊框長度超過 8 MiB 上限"};
    }

    const auto kind = static_cast<FrameKind>(static_cast<unsigned char>(bytes[4]));
    if (!is_known_frame_kind(kind)) {
        throw ProtocolError{"無法辨識訊框種類"};
    }
    return {.payload_size = size, .kind = kind};
}

}  // namespace

asio::awaitable<Frame> read_frame(LocalSocket& socket) {
    HeaderBytes header{};
    co_await asio::async_read(socket, asio::buffer(header), asio::use_awaitable);
    const auto [payload_size, kind] = decode_header(header);

    // payload 直接讀進最終的 string，不再多一次切頭複製。
    std::string payload(payload_size, '\0');
    if (payload_size > 0) {
        co_await asio::async_read(socket, asio::buffer(payload),
                                  asio::use_awaitable);
    }
    co_return Frame{.kind = kind, .payload = std::move(payload)};
}

asio::awaitable<void> write_frame(LocalSocket& socket, FrameKind kind,
                                  std::string_view payload) {
    // header 是這個 coroutine frame 的區域變數，撐得過下面的 co_await。
    const auto header = encode_header(kind, payload.size());
    const std::array<asio::const_buffer, 2> buffers{
        asio::buffer(header),
        asio::buffer(payload.data(), payload.size()),
    };
    co_await asio::async_write(socket, buffers, asio::use_awaitable);
}

asio::awaitable<void> write_stream(LocalSocket& socket, FrameKind kind,
                                   std::string_view bytes) {
    while (!bytes.empty()) {
        const auto count = std::min(bytes.size(), stream_chunk_size);
        co_await write_frame(socket, kind, bytes.substr(0, count));
        bytes.remove_prefix(count);
    }
}

}  // namespace aos
