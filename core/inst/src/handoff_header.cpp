#define _POSIX_C_SOURCE 200809L

// handoff 層：批 header sidecar 的編解與批 id 摘要。介面與理由見 handoff_header.hpp。

#include "handoff_header.hpp"

#include <cstddef>
#include <string_view>

namespace aos::detail {
namespace {

constexpr std::uint64_t kFnvPrime = 0x100000001b3ULL;

std::uint64_t fnv1a(std::uint64_t state, const char *data, std::size_t size) {
    for (std::size_t index = 0; index < size; ++index) {
        state ^= static_cast<unsigned char>(data[index]);
        state *= kFnvPrime;
    }
    return state;
}

std::string hex16(std::uint64_t value) {
    constexpr std::string_view digits = "0123456789abcdef";
    std::string text(16, '0');
    for (std::size_t index = 16; index-- > 0;) {
        text[index] = digits[value & 0xf];
        value >>= 4;
    }
    return text;
}

std::size_t skip_spaces(const std::string &text, std::size_t index) {
    while (index < text.size() &&
           (text[index] == ' ' || text[index] == '\t' || text[index] == '\n' ||
            text[index] == '\r')) {
        ++index;
    }
    return index;
}

}  // namespace

bool derive_header_paths(const std::string &base, HeaderPaths &paths) {
    constexpr std::string_view suffix = ".json";
    if (base.size() <= suffix.size() ||
        base.compare(base.size() - suffix.size(), suffix.size(), suffix) != 0) {
        return false;
    }
    paths.base = base.substr(0, base.size() - suffix.size()) + "-head.json";
    paths.temp = paths.base + ".temp";
    return true;
}

void BatchDigest::add(const std::string &name, const std::string &content) {
    // 兩個 '\0' 是欄位分隔：檔名與內容都可能含任意位元組，沒有分隔的話
    //（"a" + "bc"）與（"ab" + "c"）會撞成同一個摘要。
    const char terminator = '\0';
    state_ = fnv1a(state_, name.data(), name.size());
    state_ = fnv1a(state_, &terminator, 1);
    state_ = fnv1a(state_, content.data(), content.size());
    state_ = fnv1a(state_, &terminator, 1);
}

std::string BatchDigest::id() const { return hex16(state_); }

std::string encode_header(const std::string &id) {
    // id 是 16 位 hex、其餘三欄是常量，沒有任何需要跳脫的字元。
    return "{\"version\":1,\"id\":\"" + id +
           "\",\"origin\":\"aggregated\",\"result\":null}\n";
}

bool decode_header_id(const std::string &document, std::string &id) {
    constexpr std::string_view key = "\"id\"";
    std::size_t index = document.find(key);
    while (index != std::string::npos) {
        std::size_t cursor = skip_spaces(document, index + key.size());
        if (cursor < document.size() && document[cursor] == ':') {
            cursor = skip_spaces(document, cursor + 1);
            if (cursor >= document.size() || document[cursor] != '"') {
                return false;  // 有 id 欄但值不是字串：不是我們寫的版面。
            }
            const std::size_t start = cursor + 1;
            const std::size_t end = document.find_first_of("\"\\", start);
            // 跳脫序列不出現在我們寫的 id 裡；碰到就當作不認得，不去解跳脫。
            if (end == std::string::npos || document[end] != '"' ||
                end == start) {
                return false;
            }
            id.assign(document, start, end - start);
            return true;
        }
        // `"id"` 出現在別的位置（例如某個欄位的值）：繼續往後找真正的 key。
        index = document.find(key, index + key.size());
    }
    return false;
}

}  // namespace aos::detail
