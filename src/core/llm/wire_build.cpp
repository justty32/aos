// 組出要送出去的那包 JSON。純函式，不碰網路。
#include "aos/llm/wire.hpp"

#include <nlohmann/json.hpp>

#include <array>
#include <cstddef>
#include <filesystem>
#include <fstream>
#include <format>
#include <iterator>
#include <string>

namespace aos::llm {
namespace {

using nlohmann::json;

[[nodiscard]] std::string trim_suffix(std::string text, std::string_view tail) {
    if (text.size() >= tail.size() && text.ends_with(tail)) {
        text.resize(text.size() - tail.size());
    }
    return text;
}

[[nodiscard]] std::string trim_trailing_slashes(std::string text) {
    while (!text.empty() && text.back() == '/') {
        text.pop_back();
    }
    return text;
}

[[nodiscard]] std::string guess_mime(const std::filesystem::path& path) {
    // 只認得幾種常見的。猜錯的話端點多半還是讀得懂，因為真正的判斷是看內容。
    static const std::array<std::pair<std::string_view, std::string_view>, 6>
        table{{{".png", "image/png"},
               {".jpg", "image/jpeg"},
               {".jpeg", "image/jpeg"},
               {".gif", "image/gif"},
               {".webp", "image/webp"},
               {".bmp", "image/bmp"}}};
    auto extension = path.extension().string();
    for (char& character : extension) {
        character = static_cast<char>(std::tolower(static_cast<unsigned char>(character)));
    }
    for (const auto& [suffix, mime] : table) {
        if (extension == suffix) {
            return std::string{mime};
        }
    }
    return "image/png";
}

[[nodiscard]] std::string to_base64(std::string_view bytes) {
    static constexpr std::string_view alphabet =
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    std::string out;
    out.reserve((bytes.size() + 2) / 3 * 4);

    for (std::size_t index = 0; index < bytes.size(); index += 3) {
        const std::size_t remaining = bytes.size() - index;
        const auto byte_at = [&](std::size_t offset) -> unsigned {
            return offset < remaining
                       ? static_cast<unsigned char>(bytes[index + offset])
                       : 0U;
        };
        const unsigned triple =
            (byte_at(0) << 16) | (byte_at(1) << 8) | byte_at(2);

        out += alphabet[(triple >> 18) & 0x3F];
        out += alphabet[(triple >> 12) & 0x3F];
        out += remaining > 1 ? alphabet[(triple >> 6) & 0x3F] : '=';
        out += remaining > 2 ? alphabet[triple & 0x3F] : '=';
    }
    return out;
}

// 一則訊息 → API 收得下的形狀。
[[nodiscard]] std::expected<json, std::string> encode_message(
    const Message& message) {
    json out = json::object();
    out["role"] = message.role;

    if (message.images.empty()) {
        // 只叫工具沒說話時，content 要是 null 而不是空字串，有些端點會認真檢查。
        if (message.content.empty() && !message.tool_calls.empty()) {
            out["content"] = nullptr;
        } else {
            out["content"] = message.content;
        }
    } else {
        json parts = json::array();
        parts.push_back({{"type", "text"}, {"text", message.content}});
        for (const std::string& image : message.images) {
            auto url = image_data_url(image);
            if (!url) {
                return std::unexpected{url.error()};
            }
            parts.push_back(
                {{"type", "image_url"}, {"image_url", {{"url", *url}}}});
        }
        out["content"] = std::move(parts);
    }

    if (!message.tool_calls.empty()) {
        json calls = json::array();
        for (const ToolCall& call : message.tool_calls) {
            calls.push_back({{"id", call.id},
                             {"type", "function"},
                             {"function",
                              {{"name", call.name},
                               {"arguments", call.arguments}}}});
        }
        out["tool_calls"] = std::move(calls);
    }

    if (!message.tool_call_id.empty()) {
        out["tool_call_id"] = message.tool_call_id;
    }
    return out;
}

// 有設定的旋鈕才送。沒設定的一律不寫，讓端點用它自己的預設值 ——
// 送一個猜出來的預設值過去，等於偷偷替使用者做了決定。
void write_params(json& body, const Params& params) {
    const auto put = [&body](std::string_view name, const auto& value) {
        if (value.has_value()) {
            body[std::string{name}] = *value;
        }
    };
    put("temperature", params.temperature);
    put("top_p", params.top_p);
    put("max_tokens", params.max_tokens);
    put("seed", params.seed);
    put("presence_penalty", params.presence_penalty);
    put("frequency_penalty", params.frequency_penalty);
    if (!params.stop.empty()) {
        body["stop"] = params.stop;
    }
}

}  // namespace

std::string normalize_base_url(std::string_view url) {
    auto text = trim_trailing_slashes(std::string{url});
    text = trim_suffix(std::move(text), "/chat/completions");
    return trim_trailing_slashes(std::move(text));
}

std::string root_url(std::string_view url) {
    auto text = normalize_base_url(url);
    return trim_suffix(std::move(text), "/v1");
}

std::expected<std::string, std::string> image_data_url(
    std::string_view path_or_url) {
    if (path_or_url.starts_with("http://") ||
        path_or_url.starts_with("https://")) {
        return std::string{path_or_url};
    }

    const std::filesystem::path path{path_or_url};
    std::ifstream file{path, std::ios::binary};
    if (!file) {
        return std::unexpected{std::format("讀不到圖片 {}", path.string())};
    }
    const std::string bytes{std::istreambuf_iterator<char>{file},
                            std::istreambuf_iterator<char>{}};
    if (bytes.empty()) {
        return std::unexpected{std::format("圖片 {} 是空的", path.string())};
    }
    return std::format("data:{};base64,{}", guess_mime(path), to_base64(bytes));
}

std::expected<std::string, std::string> build_payload(
    const PayloadInput& input) {
    json body = json::object();

    if (input.params != nullptr) {
        write_params(body, *input.params);

        if (!input.params->extra.empty()) {
            json extra = json::parse(input.params->extra, nullptr, false);
            if (extra.is_discarded() || !extra.is_object()) {
                return std::unexpected{
                    "params.extra 不是一段合法的 JSON object"};
            }
            for (const auto& [key, value] : extra.items()) {
                body[key] = value;
            }
        }
    }

    json messages = json::array();
    for (const Message& message : input.messages) {
        auto encoded = encode_message(message);
        if (!encoded) {
            return std::unexpected{encoded.error()};
        }
        messages.push_back(std::move(*encoded));
    }

    if (!input.tools.empty()) {
        json tools = json::array();
        for (const ToolSchema& schema : input.tools) {
            json one = json::parse(schema.json, nullptr, false);
            if (one.is_discarded()) {
                return std::unexpected{
                    std::format("工具 {} 的 schema 不是合法 JSON", schema.name)};
            }
            tools.push_back(std::move(one));
        }
        body["tools"] = std::move(tools);

        if (!input.tool_choice.empty()) {
            // "auto" 這種是裸字串，指定某個 function 則是一整段 JSON object。
            json choice = json::parse(input.tool_choice, nullptr, false);
            body["tool_choice"] = choice.is_discarded() || !choice.is_object()
                                      ? json(std::string{input.tool_choice})
                                      : std::move(choice);
        }
    } else if (!input.tool_choice.empty()) {
        // 沒有 tools 就送不出 tool_choice。與其安靜吞掉，不如講出來。
        return std::unexpected{"給了 tool_choice，但沒有任何工具，不會有效果"};
    }

    if (input.stream) {
        // 不開這個，串流回來的 usage 永遠是空的（只有最後那片才帶 usage）。
        body["stream_options"] = {{"include_usage", true}};
    }

    // 這三個由引擎自己管，**最後才寫**，確保蓋得過 params.extra。
    // 理由是踩過：extra 裡塞了 stream 會讓「用哪條路收」跟「實際回來的是什麼」
    // 分岔，症狀是收到一個看不懂的東西。
    body["model"] = std::string{input.model};
    body["messages"] = std::move(messages);
    body["stream"] = input.stream;

    return body.dump();
}

}  // namespace aos::llm
