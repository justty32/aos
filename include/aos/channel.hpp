#pragma once

#include "aos/protocol.hpp"

#include <asio/awaitable.hpp>
#include <asio/local/stream_protocol.hpp>

#include <string_view>

namespace aos {

using LocalSocket = asio::local::stream_protocol::socket;

[[nodiscard]] Frame read_frame(LocalSocket& socket);
void write_frame(LocalSocket& socket, FrameKind kind, std::string_view payload);

[[nodiscard]] asio::awaitable<Frame> async_read_frame(LocalSocket& socket);
asio::awaitable<void> async_write_frame(
    LocalSocket& socket, FrameKind kind, std::string_view payload);

}  // namespace aos
