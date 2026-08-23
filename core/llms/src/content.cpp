#include <aos/llms.hpp>

#include "llms_internal.hpp"

#include <algorithm>
#include <cctype>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <stdexcept>
#include <string_view>

namespace aos::llms {
namespace {

std::string strip_trailing_slashes(std::string url) {
    while (!url.empty() && url.back() == '/') {
        url.pop_back();
    }
    return url;
}

std::string base64(const std::vector<unsigned char> &input) {
    static constexpr char alphabet[] =
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    std::string output;
    output.reserve(((input.size() + 2) / 3) * 4);
    for (std::size_t i = 0; i < input.size(); i += 3) {
        const unsigned value = static_cast<unsigned>(input[i]) << 16 |
            (i + 1 < input.size() ? static_cast<unsigned>(input[i + 1]) << 8
                                  : 0U) |
            (i + 2 < input.size() ? static_cast<unsigned>(input[i + 2]) : 0U);
        output.push_back(alphabet[(value >> 18) & 63U]);
        output.push_back(alphabet[(value >> 12) & 63U]);
        output.push_back(i + 1 < input.size() ? alphabet[(value >> 6) & 63U]
                                             : '=');
        output.push_back(i + 2 < input.size() ? alphabet[value & 63U] : '=');
    }
    return output;
}

std::string image_mime(const std::string &path) {
    std::string extension = std::filesystem::path(path).extension().string();
    std::ranges::transform(extension, extension.begin(), [](unsigned char ch) {
        return static_cast<char>(std::tolower(ch));
    });
    if (extension == ".jpg" || extension == ".jpeg") return "image/jpeg";
    if (extension == ".gif") return "image/gif";
    if (extension == ".webp") return "image/webp";
    if (extension == ".bmp") return "image/bmp";
    if (extension == ".svg") return "image/svg+xml";
    return "image/png";
}

}  // namespace

std::string normalize_base_url(const std::string &input) {
    std::string url = strip_trailing_slashes(input);
    static constexpr std::string_view suffix = "/chat/completions";
    if (url.ends_with(suffix)) {
        url.erase(url.size() - suffix.size());
    }
    return strip_trailing_slashes(std::move(url));
}

std::string endpoint_root_url(const std::string &input) {
    std::string url = normalize_base_url(input);
    if (url.ends_with("/v1")) {
        url.erase(url.size() - 3);
    }
    return strip_trailing_slashes(std::move(url));
}

std::string resolve_key(const std::optional<std::string> &key) {
    if (key.has_value()) return *key;
    const char *environment = std::getenv("OPENAI_API_KEY");
    return environment != nullptr && environment[0] != '\0' ? environment
                                                               : "hello";
}

std::string encode_image_url(const std::string &path_or_url) {
    if (path_or_url.starts_with("http://") ||
        path_or_url.starts_with("https://")) {
        return path_or_url;
    }
    std::ifstream input(path_or_url, std::ios::binary);
    if (!input) {
        throw std::runtime_error("圖片讀不起來：" + path_or_url);
    }
    const std::vector<unsigned char> bytes{
        std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>()};
    if (input.bad()) {
        throw std::runtime_error("圖片讀取失敗：" + path_or_url);
    }
    return "data:" + image_mime(path_or_url) + ";base64," + base64(bytes);
}

json content_value(const std::optional<std::string> &prompt,
                   const std::vector<std::string> &images) {
    if (images.empty()) {
        return prompt.has_value() ? json(*prompt) : json(nullptr);
    }
    json parts = json::array();
    parts.push_back({{"type", "text"}, {"text", prompt.value_or("")}});
    for (const std::string &image : images) {
        parts.push_back({{"type", "image_url"},
                         {"image_url", {{"url", encode_image_url(image)}}}});
    }
    return parts;
}

std::string build_content_json(const std::optional<std::string> &prompt,
                               const std::vector<std::string> &images) {
    return content_value(prompt, images).dump();
}

}  // namespace aos::llms
