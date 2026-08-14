#include "aos/channel.hpp"

#include <asio/buffer.hpp>
#include <asio/read.hpp>
#include <asio/use_awaitable.hpp>
#include <asio/write.hpp>

#include <array>
#include <stdexcept>

namespace aos {
namespace {

[[nodiscard]] std::array<char, 5>
make_header(FrameKind kind, std::size_t payload_size) {
    if (payload_size > maximum_frame_size - 1) {
        throw std::runtime_error{"訊框超過 8 MiB 上限"};
    }
    const auto size = static_cast<std::uint32_t>(payload_size + 1);
    return {
        static_cast<char>((size >> 24U) & 0xffU),
        static_cast<char>((size >> 16U) & 0xffU),
        static_cast<char>((size >> 8U) & 0xffU),
        static_cast<char>(size & 0xffU),
        static_cast<char>(kind),
    };
}

[[nodiscard]] std::uint32_t decode_size(const std::array<char, 4>& header) {
    std::uint32_t size{};
    for (const char byte : header) {
        size = (size << 8U) | static_cast<unsigned char>(byte);
    }
    if (size == 0 || size > maximum_frame_size) {
        throw std::runtime_error{"訊框長度無效"};
    }
    return size;
}

[[nodiscard]] Frame decode_body(std::string body) {
    const auto kind = static_cast<FrameKind>(
        static_cast<unsigned char>(body.front()));
    if (!is_valid(kind)) {
        throw std::runtime_error{"無法辨識訊框種類"};
    }
    return {.kind = kind, .payload = body.substr(1)};
}

[[nodiscard]] auto buffers(const std::array<char, 5>& header,
                           std::string_view payload) {
    return std::array<asio::const_buffer, 2>{
        asio::buffer(header),
        asio::buffer(payload.data(), payload.size()),
    };
}

}  // namespace

Frame read_frame(LocalSocket& socket) {
    std::array<char, 4> header{};
    asio::read(socket, asio::buffer(header));
    std::string body(decode_size(header), '\0');
    asio::read(socket, asio::buffer(body));
    return decode_body(std::move(body));
}

void write_frame(LocalSocket& socket, FrameKind kind,
                 std::string_view payload) {
    const auto header = make_header(kind, payload.size());
    asio::write(socket, buffers(header, payload));
}

asio::awaitable<Frame> async_read_frame(LocalSocket& socket) {
    std::array<char, 4> header{};
    co_await asio::async_read(socket, asio::buffer(header), asio::use_awaitable);
    std::string body(decode_size(header), '\0');
    co_await asio::async_read(socket, asio::buffer(body), asio::use_awaitable);
    co_return decode_body(std::move(body));
}

asio::awaitable<void> async_write_frame(
    LocalSocket& socket, FrameKind kind, std::string_view payload) {
    const auto header = make_header(kind, payload.size());
    co_await asio::async_write(socket, buffers(header, payload),
                               asio::use_awaitable);
}

}  // namespace aos
