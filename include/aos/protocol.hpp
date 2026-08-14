#pragma once

#include <cstddef>
#include <cstdint>
#include <expected>
#include <filesystem>
#include <string>
#include <string_view>
#include <vector>

namespace aos {

inline constexpr std::size_t maximum_frame_size = 8U * 1024U * 1024U;
inline constexpr std::size_t stream_chunk_size = 64U * 1024U;

struct Request {
    std::vector<std::string> arguments;
    std::filesystem::path working_directory;
    std::string standard_input;

    bool operator==(const Request&) const = default;
};

struct Response {
    std::int32_t exit_code{};
    std::string standard_output;
    std::string standard_error;

    bool operator==(const Response&) const = default;
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
    FrameKind kind;
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

[[nodiscard]] bool is_valid(FrameKind kind);

}  // namespace aos
