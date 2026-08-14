#pragma once

#include <cstddef>
#include <cstdint>
#include <expected>
#include <filesystem>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

namespace aos {

// 訊框格式：4 bytes big-endian payload 長度 + 1 byte 種類 + payload。
inline constexpr std::size_t frame_header_size = 5;

// 單一訊框的 payload 上限。整段 stdin／stdout 是串流的，不受這個數字限制。
inline constexpr std::size_t maximum_payload_size = 8U * 1024U * 1024U;

// 串流資料切塊的大小，同時是 client 讀 stdin 的緩衝區大小。
inline constexpr std::size_t stream_chunk_size = 64U * 1024U;

// 對方講的話不符合協定（欄位缺漏、訊框種類不認得、方向錯誤……）。
// 跟 std::system_error 分開：後者代表連線本身壞了，已經無法再回覆對方。
class ProtocolError : public std::runtime_error {
public:
    using std::runtime_error::runtime_error;
};

// 一次命令呼叫的靜態部分。stdin 不在這裡，它是連線上持續流動的訊框。
struct Request {
    std::vector<std::string> arguments;
    std::filesystem::path working_directory;

    bool operator==(const Request&) const = default;
};

enum class FrameKind : std::uint8_t {
    request_start = 1,
    stdin_chunk = 2,
    stdin_end = 3,
    stdout_chunk = 4,
    stderr_chunk = 5,
    exit = 6,
};

struct Frame {
    FrameKind kind{};
    std::string payload;
};

// 控制訊息使用 JSON；三條標準串流則直接放原始 bytes。
[[nodiscard]] std::expected<std::string, std::string>
encode_request_start(const Request& request);

[[nodiscard]] std::expected<Request, std::string>
decode_request_start(std::string_view payload);

[[nodiscard]] std::string encode_exit(std::int32_t exit_code);

[[nodiscard]] std::expected<std::int32_t, std::string>
decode_exit(std::string_view payload);

[[nodiscard]] bool is_known_frame_kind(FrameKind kind);

}  // namespace aos
