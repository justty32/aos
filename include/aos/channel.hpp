#pragma once

#include "aos/protocol.hpp"

#include <asio/awaitable.hpp>
#include <asio/local/stream_protocol.hpp>

#include <string_view>

namespace aos {

using LocalSocket = asio::local::stream_protocol::socket;

// 讀不到完整訊框會丟 std::system_error（含 asio::error::eof），
// 訊框內容不合法則丟 ProtocolError。
[[nodiscard]] asio::awaitable<Frame> read_frame(LocalSocket& socket);

// payload 只是個 view，呼叫端必須保證底下的 bytes 活過整個 co_await。
// 最簡單的作法是把來源放在呼叫端 coroutine 的區域變數裡。
asio::awaitable<void> write_frame(LocalSocket& socket, FrameKind kind,
                                  std::string_view payload);

// 超過 maximum_payload_size 的資料自動切成多個 kind 訊框；空資料不送任何訊框。
asio::awaitable<void> write_stream(LocalSocket& socket, FrameKind kind,
                                   std::string_view bytes);

}  // namespace aos
