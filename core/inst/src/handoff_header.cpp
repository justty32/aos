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

bool is_space(char ch) {
    return ch == ' ' || ch == '\t' || ch == '\n' || ch == '\r';
}

std::size_t skip_spaces(const std::string &text, std::size_t index) {
    while (index < text.size() && is_space(text[index])) ++index;
    return index;
}

// 掃過一個字串字面值（cursor 指著開頭的引號），只求跳過、不取內容：跳脫序列整組
// 跳過，所以 `"the \"id\" of a batch"` 不會被誤讀成兩個字串。
// （`\uXXXX` 也只需跳過 `\` 與 `u`，剩下四位十六進位字元都不是引號或反斜線。）
bool skip_string(const std::string &text, std::size_t &cursor) {
    if (cursor >= text.size() || text[cursor] != '"') return false;
    ++cursor;
    while (cursor < text.size()) {
        const char ch = text[cursor];
        if (ch == '\\') {
            cursor += 2;
            continue;
        }
        ++cursor;
        if (ch == '"') return true;
    }
    return false;
}

// 取出一個**不含跳脫序列**的字串字面值。碰到跳脫就回 false：我們自己寫出去的
// key 與 id 都不含跳脫，看不懂就當作沒 header（失效方向見標頭）。
bool take_plain_string(const std::string &text, std::size_t &cursor,
                       std::string &out) {
    if (cursor >= text.size() || text[cursor] != '"') return false;
    const std::size_t start = cursor + 1;
    std::size_t index = start;
    while (index < text.size() && text[index] != '"' && text[index] != '\\') {
        ++index;
    }
    if (index >= text.size() || text[index] != '"') return false;
    out.assign(text, start, index - start);
    cursor = index + 1;
    return true;
}

// 掃過一個值。物件／陣列用深度計數跳過，**跳過時仍然把字串整段交給 skip_string**
// ——否則字串裡的 `{`／`]` 會把深度算歪，巢狀的 `"id"` 就漏出來了。
bool skip_value(const std::string &text, std::size_t &cursor) {
    cursor = skip_spaces(text, cursor);
    if (cursor >= text.size()) return false;
    const char first = text[cursor];
    if (first == '"') return skip_string(text, cursor);
    if (first == '{' || first == '[') {
        int depth = 0;
        while (cursor < text.size()) {
            const char ch = text[cursor];
            if (ch == '"') {
                if (!skip_string(text, cursor)) return false;
                continue;  // skip_string 已經把 cursor 推過收尾的引號
            }
            if (ch == '{' || ch == '[') {
                ++depth;
            } else if (ch == '}' || ch == ']') {
                --depth;
                if (depth == 0) {
                    ++cursor;
                    return true;
                }
            }
            ++cursor;
        }
        return false;
    }
    // 數字／true／false／null：掃到分隔符為止。
    const std::size_t start = cursor;
    while (cursor < text.size() && text[cursor] != ',' && text[cursor] != '}' &&
           text[cursor] != ']' && !is_space(text[cursor])) {
        ++cursor;
    }
    return cursor != start;
}

}  // namespace

bool derive_header_paths(const std::string &base, HeaderPaths &paths) {
    constexpr std::string_view suffix = ".json";
    if (base.size() <= suffix.size() ||
        base.compare(base.size() - suffix.size(), suffix.size(), suffix) != 0) {
        return false;
    }
    paths.base = base.substr(0, base.size() - suffix.size()) + "-head.json";
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

std::string encode_header(const std::string &id, bool swept) {
    // id 是 16 位 hex、其餘四欄是常量，沒有任何需要跳脫的字元。
    return "{\"version\":1,\"id\":\"" + id +
           "\",\"origin\":\"aggregated\",\"result\":null,\"swept\":" +
           (swept ? "true" : "false") + "}\n";
}

bool decode_header(const std::string &document, HeaderFields &fields) {
    std::size_t cursor = skip_spaces(document, 0);
    if (cursor >= document.size() || document[cursor] != '{') return false;
    ++cursor;
    cursor = skip_spaces(document, cursor);
    if (cursor < document.size() && document[cursor] == '}') {
        return false;  // 空物件：沒有頂層 id ＝ 沒有可比對的批。
    }

    HeaderFields scanned;
    bool found_id = false;
    for (;;) {
        cursor = skip_spaces(document, cursor);
        std::string key;
        if (!take_plain_string(document, cursor, key)) return false;
        cursor = skip_spaces(document, cursor);
        if (cursor >= document.size() || document[cursor] != ':') return false;
        cursor = skip_spaces(document, cursor + 1);

        const std::size_t value = cursor;
        if (!skip_value(document, cursor)) return false;
        if (key == "id") {
            std::size_t reread = value;
            std::string text;
            // 值必須是字串、非空、且不含跳脫序列，否則不是我們認得的版面。
            if (!take_plain_string(document, reread, text) || text.empty()) {
                return false;
            }
            scanned.id = text;
            found_id = true;
        } else if (key == "swept") {
            const std::string_view text(document.data() + value, cursor - value);
            if (text == "true") {
                scanned.swept = true;
            } else if (text != "false") {
                return false;  // swept 不是布林：不是我們寫的版面。
            }
        }

        cursor = skip_spaces(document, cursor);
        if (cursor >= document.size()) return false;
        if (document[cursor] == ',') {
            ++cursor;
            continue;
        }
        if (document[cursor] == '}') break;
        return false;
    }
    if (!found_id) return false;
    fields = scanned;
    return true;
}

}  // namespace aos::detail
