#include "aos/protocol.hpp"

#include <nlohmann/json.hpp>

#include <exception>
#include <format>

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
        return invalid(std::format("request JSON 編碼失敗：{}", error.what()));
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

        const auto arguments = document.find("arguments");
        const auto working_directory = document.find("working_directory");
        if (arguments == document.end() || !arguments->is_array() ||
            working_directory == document.end() ||
            !working_directory->is_string()) {
            return invalid("request JSON 缺少必要欄位");
        }

        return Request{
            .arguments = arguments->get<std::vector<std::string>>(),
            .working_directory = working_directory->get<std::string>(),
        };
    } catch (const std::exception& error) {
        return invalid(std::format("request JSON 內容錯誤：{}", error.what()));
    }
}

std::string encode_exit(std::int32_t exit_code) {
    return Json{{"exit_code", exit_code}}.dump();
}

std::expected<std::int32_t, std::string>
decode_exit(std::string_view payload) {
    try {
        const auto document = Json::parse(payload, nullptr, false);
        if (document.is_discarded() || !document.is_object()) {
            return invalid("exit frame 不是有效的 JSON");
        }
        const auto exit_code = document.find("exit_code");
        if (exit_code == document.end() || !exit_code->is_number_integer()) {
            return invalid("exit frame 缺少 exit_code");
        }
        return exit_code->get<std::int32_t>();
    } catch (const std::exception& error) {
        return invalid(std::format("exit JSON 內容錯誤：{}", error.what()));
    }
}

bool is_known_frame_kind(FrameKind kind) {
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
