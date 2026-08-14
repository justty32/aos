#include "aos/protocol.hpp"

#include <nlohmann/json.hpp>

#include <exception>

namespace aos {
namespace {

using Json = nlohmann::json;
constexpr int protocol_version = 1;

[[nodiscard]] std::unexpected<std::string> invalid(std::string message) {
    return std::unexpected{std::move(message)};
}

}  // namespace

std::expected<std::string, std::string>
encode_request_start(const Request& request) {
    try {
        return Json{
            {"version", protocol_version},
            {"arguments", request.arguments},
            {"working_directory", request.working_directory.native()},
        }.dump();
    } catch (const std::exception& error) {
        return invalid("request JSON 編碼失敗：" + std::string{error.what()});
    }
}

std::expected<Request, std::string>
decode_request_start(std::string_view payload) {
    try {
        const auto document = Json::parse(payload, nullptr, false);
        if (document.is_discarded() || !document.is_object()) {
            return invalid("request 不是有效的 JSON object");
        }
        if (document.value("version", 0) != protocol_version) {
            return invalid("不支援的 AOS 協定版本");
        }
        if (!document.contains("arguments") ||
            !document["arguments"].is_array() ||
            !document.contains("working_directory") ||
            !document["working_directory"].is_string()) {
            return invalid("request JSON 缺少必要欄位");
        }

        Request request;
        request.arguments = document["arguments"].get<std::vector<std::string>>();
        request.working_directory =
            document["working_directory"].get<std::string>();
        return request;
    } catch (const std::exception& error) {
        return invalid("request JSON 內容錯誤：" + std::string{error.what()});
    }
}

std::string encode_exit(std::int32_t exit_code) {
    return Json{{"exit_code", exit_code}}.dump();
}

std::expected<std::int32_t, std::string>
decode_exit(std::string_view payload) {
    try {
        const auto document = Json::parse(payload, nullptr, false);
        if (document.is_discarded() || !document.is_object() ||
            !document.contains("exit_code") ||
            !document["exit_code"].is_number_integer()) {
            return invalid("exit frame 不是有效的 JSON");
        }
        return document["exit_code"].get<std::int32_t>();
    } catch (const std::exception& error) {
        return invalid("exit JSON 內容錯誤：" + std::string{error.what()});
    }
}

bool is_valid(FrameKind kind) {
    switch (kind) {
    case FrameKind::request_start:
    case FrameKind::stdin_chunk:
    case FrameKind::stdin_end:
    case FrameKind::stdout_chunk:
    case FrameKind::stderr_chunk:
    case FrameKind::exit:
        return true;
    }
    return false;
}

}  // namespace aos
