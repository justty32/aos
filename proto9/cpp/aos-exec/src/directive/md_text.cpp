// directive/md_text.cpp: Python-str-like helpers on UTF-8 bytes and the four line scanners FENCE, HEAD, ITEM, SEP (part of proto8 aos-directive src/md.cpp).
#include "directive/md.hpp"

#include <algorithm>

namespace aos::md {

// ---- Python str 的小動作（UTF-8 位元組上） ----

// Python str.isspace() 認的字元。
bool py_space(uint32_t c) {
    return (c >= 0x09 && c <= 0x0D) || (c >= 0x1C && c <= 0x20) || c == 0x85 || c == 0xA0 || c == 0x1680 ||
           (c >= 0x2000 && c <= 0x200A) || c == 0x2028 || c == 0x2029 || c == 0x202F || c == 0x205F || c == 0x3000;
}

// s[i] 起的一個字元：（code point, 位元組數）；不合法的 UTF-8＝那一個位元組自己（不算空白）。
std::pair<uint32_t, size_t> decode(const std::string& s, size_t i) {
    unsigned char c = (unsigned char)s[i];
    size_t n = c < 0x80 ? 1 : (c >> 5) == 0x6 ? 2 : (c >> 4) == 0xE ? 3 : (c >> 3) == 0x1E ? 4 : 0;
    if (n == 0 || i + n > s.size()) {
        return {0xFFFFFFFF, 1};
    }
    uint32_t cp = n == 1 ? c : n == 2 ? (c & 0x1F) : n == 3 ? (c & 0x0F) : (c & 0x07);
    for (size_t k = 1; k < n; ++k) {
        unsigned char x = (unsigned char)s[i + k];
        if ((x & 0xC0) != 0x80) {
            return {0xFFFFFFFF, 1};
        }
        cp = (cp << 6) | (x & 0x3F);
    }
    return {cp, n};
}

// 開頭幾個位元組是 Unicode 空白。
size_t lead_space(const std::string& s) {
    size_t i = 0;
    while (i < s.size()) {
        auto [cp, n] = decode(s, i);
        if (!py_space(cp)) {
            break;
        }
        i += n;
    }
    return i;
}

// 結尾幾個位元組是 Unicode 空白（從 from 往前看，不越過 from）。
size_t trail_space(const std::string& s, size_t from) {
    size_t end = s.size();
    while (end > from) {
        size_t st = end - 1;
        while (st > from && end - st < 4 && ((unsigned char)s[st] & 0xC0) == 0x80) {
            --st;
        }
        auto [cp, n] = decode(s, st);
        if (st + n != end || !py_space(cp)) {
            break;
        }
        end = st;
    }
    return s.size() - end;
}

std::string py_strip(const std::string& s) {
    size_t a = lead_space(s);
    if (a == s.size()) {
        return "";
    }
    return s.substr(a, s.size() - a - trail_space(s, a));
}

std::string py_rstrip(const std::string& s) {
    return s.substr(0, s.size() - trail_space(s));
}

bool blank(const std::string& s) {
    return lead_space(s) == s.size();
}

bool is_ascii(const std::string& s) {
    return std::all_of(s.begin(), s.end(), [](char c) { return (unsigned char)c < 0x80; });
}

std::string ascii_lower(std::string s) {
    for (char& c : s) {
        if (c >= 'A' && c <= 'Z') {
            c = (char)(c - 'A' + 'a');
        }
    }
    return s;
}

bool only(const std::string& s, char c) {
    return std::all_of(s.begin(), s.end(), [c](char x) { return x == c; });
}

size_t indent(const std::string& l) {
    size_t i = 0;
    while (i < l.size() && l[i] == ' ') {
        ++i;
    }
    return i;
}

// INT：^(0|[1-9][0-9]*)$
bool is_int(const std::string& t) {
    if (t.empty() || (t.size() > 1 && t[0] == '0')) {
        return false;
    }
    return std::all_of(t.begin(), t.end(), [](char c) { return c >= '0' && c <= '9'; });
}

// t（is_int 過的）< n；太長的數字一律算超出。
bool below(const std::string& t, size_t n, size_t& out) {
    if (t.size() > 18) {
        return false;
    }
    out = (size_t)std::stoull(t);
    return out < n;
}


// FENCE：^ {0,3}(`{3,}|~{3,})(.*)$
std::optional<Fence> fence(const std::string& l) {
    size_t i = 0;
    while (i < 3 && i < l.size() && l[i] == ' ') {
        ++i;
    }
    if (i >= l.size() || (l[i] != '`' && l[i] != '~')) {
        return std::nullopt;
    }
    size_t j = i;
    while (j < l.size() && l[j] == l[i]) {
        ++j;
    }
    if (j - i < 3) {
        return std::nullopt;
    }
    return Fence{l.substr(i, j - i), l.substr(j)};
}

// HEAD：^ {0,3}(#{1,6})(?:[ \t]+(.*))?$
std::optional<Head> head(const std::string& l) {
    size_t i = 0;
    while (i < 3 && i < l.size() && l[i] == ' ') {
        ++i;
    }
    size_t j = i;
    while (j < l.size() && l[j] == '#') {
        ++j;
    }
    if (j == i || j - i > 6) {
        return std::nullopt;
    }
    if (j == l.size()) {
        return Head{(int)(j - i), std::nullopt};
    }
    if (l[j] != ' ' && l[j] != '\t') {
        return std::nullopt;
    }
    size_t k = j;
    while (k < l.size() && (l[k] == ' ' || l[k] == '\t')) {
        ++k;
    }
    return Head{(int)(j - i), l.substr(k)};
}

// ITEM：^( *)([-*+]|[0-9]{1,9}[.)])(?:( +)(.*))?$
std::optional<Item> item(const std::string& l) {
    size_t i = indent(l);
    if (i >= l.size()) {
        return std::nullopt;
    }
    size_t j = i;
    if (l[i] == '-' || l[i] == '*' || l[i] == '+') {
        j = i + 1;
    } else {
        while (j < l.size() && l[j] >= '0' && l[j] <= '9') {
            ++j;
        }
        if (j == i || j - i > 9 || j >= l.size() || (l[j] != '.' && l[j] != ')')) {
            return std::nullopt;
        }
        ++j;
    }
    Item m{i, j - i, std::nullopt, std::nullopt};
    if (j == l.size()) {
        return m;
    }
    if (l[j] != ' ') {
        return std::nullopt;
    }
    size_t k = j;
    while (k < l.size() && l[k] == ' ') {
        ++k;
    }
    m.gap = l.substr(j, k - j);
    m.rest = l.substr(k);
    return m;
}

// SEP：^[ \t]*\|?[ \t]*:?-+:?[ \t]*(\|[ \t]*:?-+:?[ \t]*)*\|?[ \t]*$
bool sep(const std::string& l) {
    size_t i = 0;
    size_t n = l.size();
    auto ws = [&] {
        while (i < n && (l[i] == ' ' || l[i] == '\t')) {
            ++i;
        }
    };
    auto cell = [&] {   // :?-+:?
        size_t at = i;
        if (i < n && l[i] == ':') {
            ++i;
        }
        size_t d = i;
        while (i < n && l[i] == '-') {
            ++i;
        }
        if (i == d) {
            i = at;
            return false;
        }
        if (i < n && l[i] == ':') {
            ++i;
        }
        return true;
    };
    ws();
    if (i < n && l[i] == '|') {
        ++i;
    }
    ws();
    if (!cell()) {
        return false;
    }
    ws();
    while (i < n && l[i] == '|') {
        ++i;
        ws();
        if (i == n) {
            return true;   // 結尾的 |
        }
        if (!cell()) {
            return false;
        }
        ws();
    }
    return i == n;
}

bool same(const std::string& a, const std::string& b) {
    return is_ascii(a) && is_ascii(b) ? ascii_lower(a) == ascii_lower(b) : a == b;
}

// names 裡第一個等於 tok 的位置；沒有就第一個 ASCII 不分大小寫相等的；都沒有＝-1。
long pick(const std::vector<std::string>& names, const std::string& tok) {
    for (size_t i = 0; i < names.size(); ++i) {
        if (names[i] == tok) {
            return (long)i;
        }
    }
    for (size_t i = 0; i < names.size(); ++i) {
        if (same(names[i], tok)) {
            return (long)i;
        }
    }
    return -1;
}

Lines sub(const Lines& v, size_t a, size_t b) {
    return Lines(v.begin() + (long)std::min(a, v.size()), v.begin() + (long)std::min(b, v.size()));
}

}  // namespace aos::md
