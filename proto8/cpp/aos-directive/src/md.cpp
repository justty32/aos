// md.cpp：把一份 markdown 照它本來就有的結構讀成 json 值——給路徑拿一格（md_get）、列一層（md_ls）、整份倒成一棵樹（md_tree）。
//
// 逐條照 py/aos/mdpath.py 搬過來（規則以它與 py/tests/md_path_cases.json 為準，文字版在
// thinking 2026-11/21/知識庫-骨架加md-規劃-1121/07-尋址規則.md）；Python 用 regex 的地方這裡手寫掃描，結果要一樣。
// 字串都是 UTF-8 的位元組：Python 的 str.strip()（Unicode 空白）用 py_strip 對齊；_same 只在兩邊都是 ASCII 時才不分大小寫；
// 全形冒號「：」是三個位元組 EF BC 9A。純讀、不寫 md、不讀檔。
#include "aos/directive.hpp"

#include <algorithm>
#include <cstdint>
#include <optional>
#include <utility>

namespace aos {

namespace {

using Lines = std::vector<std::string>;

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
size_t trail_space(const std::string& s, size_t from = 0) {
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

// ---- 四個 regex（FENCE、HEAD、ITEM、SEP） ----

struct Fence {
    std::string mark;
    std::string rest;
};

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

struct Head {
    int level;
    std::optional<std::string> rest;
};

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

struct Item {
    size_t indent;
    size_t marker;
    std::optional<std::string> gap;    // ( +)
    std::optional<std::string> rest;   // (.*)
};

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

// ---- 行、圍欄、標題 ----

Lines split_lines(const std::string& text) {
    Lines out;
    size_t pos = 0;
    while (true) {
        size_t nl = text.find('\n', pos);
        std::string l = text.substr(pos, nl == std::string::npos ? std::string::npos : nl - pos);
        if (!l.empty() && l.back() == '\r') {
            l.pop_back();
        }
        out.push_back(std::move(l));
        if (nl == std::string::npos) {
            break;
        }
        pos = nl + 1;
    }
    return out;
}

// 每一行在不在程式碼區塊裡（圍欄那兩行也算在裡面）。
std::vector<bool> fenced(const Lines& lines) {
    std::vector<bool> out;
    std::string mark;
    for (const std::string& l : lines) {
        std::optional<Fence> m = fence(l);
        if (mark.empty()) {
            if (m) {
                mark = m->mark;
            }
            out.push_back(m.has_value());
        } else {
            out.push_back(true);
            std::string s = py_strip(l);
            if (m && s[0] == mark[0] && m->mark.size() >= mark.size() && only(s, mark[0])) {
                mark.clear();
            }
        }
    }
    return out;
}

std::string title_of(const std::optional<std::string>& rest) {
    std::string t = py_strip(rest.value_or(""));
    size_t e = t.size();
    while (e > 0 && t[e - 1] == '#') {
        --e;
    }
    if (e != t.size() && (e == 0 || t[e - 1] == ' ' || t[e - 1] == '\t')) {
        t = py_rstrip(t.substr(0, e));
    }
    return t;
}

struct H {
    size_t line;
    int level;
    std::string title;
};

std::vector<H> heads_of(const Lines& lines) {
    std::vector<bool> inside = fenced(lines);
    std::vector<H> out;
    for (size_t i = 0; i < lines.size(); ++i) {
        if (!inside[i]) {
            if (std::optional<Head> m = head(lines[i])) {
                out.push_back({i, m->level, title_of(m->rest)});
            }
        }
    }
    return out;
}

// 幾行 → 一段文字：頭尾空行去掉（lead＝false 不去頭）、有字就結尾一個換行。
std::string text_of(const Lines& lines, bool lead = true) {
    size_t a = 0;
    size_t b = lines.size();
    while (b > a && blank(lines[b - 1])) {
        --b;
    }
    while (lead && a < b && blank(lines[a])) {
        ++a;
    }
    if (b <= a) {
        return "";
    }
    std::string out;
    for (size_t i = a; i < b; ++i) {
        out += lines[i];
        out += i + 1 < b ? "\n" : "";
    }
    return out + "\n";
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

// ---- 清單、鍵、表格、json 區塊 ----

Lines sub(const Lines& v, size_t a, size_t b) {
    return Lines(v.begin() + (long)std::min(a, v.size()), v.begin() + (long)std::min(b, v.size()));
}

// 幾行裡的第一個清單 → [項的幾行（已去掉記號與縮排）]；沒有＝nullopt。
std::optional<std::vector<Lines>> list_of(const Lines& lines) {
    std::vector<bool> inside = fenced(lines);
    size_t start = lines.size();
    for (size_t i = 0; i < lines.size(); ++i) {
        if (!inside[i] && item(lines[i]) && indent(lines[i]) <= 3) {
            start = i;
            break;
        }
    }
    if (start == lines.size()) {
        return std::nullopt;
    }
    size_t base = indent(lines[start]);
    std::vector<Lines> items;
    size_t width = 0;
    for (size_t i = start; i < lines.size(); ++i) {
        const std::string& l = lines[i];
        std::optional<Item> m = inside[i] ? std::nullopt : item(l);
        if (m && m->indent == base) {
            width = base + m->marker + (m->gap && !m->rest->empty() ? m->gap->size() : 1);
            items.push_back({m->rest.value_or("")});
        } else if (inside[i] || blank(l) || indent(l) > base) {
            items.back().push_back(blank(l) ? "" : l.substr(std::min(width, indent(l))));
        } else if (i > start && !blank(lines[i - 1]) && !head(l) && !(m && m->indent < base)) {
            items.back().push_back(l.substr(indent(l)));   // 接在有字的行後面、沒縮排的續行
        } else {
            break;
        }
    }
    for (Lines& cur : items) {
        while (cur.size() > 1 && blank(cur.back())) {
            cur.pop_back();
        }
    }
    return items;
}

// 半形冒號後面：行尾、空白，或 `**` 再接行尾或空白（`**鍵:** 值`）才算分隔。
bool colon_end(std::string after) {
    if (after.starts_with("**")) {
        after = after.substr(2);
    }
    return after.empty() || after[0] == ' ' || after[0] == '\t';
}

// 清單項的第一行 → (鍵, 冒號後面的字) 或 nullopt。冒號＝半形後面接空白或行尾，或全形；反引號裡的不算。
std::optional<std::pair<std::string, std::string>> key_of(const std::string& first) {
    bool tick = false;
    size_t pos = std::string::npos;
    size_t len = 1;
    for (size_t i = 0; i < first.size(); ++i) {
        char c = first[i];
        if (c == '`') {
            tick = !tick;
        } else if (!tick && first.compare(i, 3, "\xEF\xBC\x9A") == 0) {
            pos = i;
            len = 3;
            break;
        } else if (!tick && c == ':' && colon_end(first.substr(i + 1))) {
            pos = i;
            break;
        }
    }
    if (pos == std::string::npos) {
        return std::nullopt;
    }
    std::string key = py_strip(first.substr(0, pos));
    std::string rest = first.substr(pos + len);
    if (rest.starts_with("**")) {   // **鍵:** 值
        rest = rest.substr(2);
    }
    rest = py_strip(rest);
    if (key.starts_with("**")) {
        key = key.substr(2);
    }
    if (key.ends_with("**")) {
        key = key.substr(0, key.size() - 2);
    }
    key = py_strip(key);
    if (key.size() >= 2 && key.front() == '`' && key.back() == '`') {
        key = py_strip(key.substr(1, key.size() - 2));
    }
    if (key.empty()) {
        return std::nullopt;
    }
    return std::make_pair(key, rest);
}

std::vector<std::string> cells_of(const std::string& line) {
    std::string s = py_strip(line);
    std::vector<std::string> cells;
    std::string cur;
    for (size_t i = 0; i < s.size(); ++i) {
        if (s[i] == '\\' && i + 1 < s.size() && s[i + 1] == '|') {
            cur += '|';
            ++i;
        } else if (s[i] == '|') {
            cells.push_back(cur);
            cur.clear();
        } else {
            cur += s[i];
        }
    }
    cells.push_back(cur);
    if (s.starts_with("|")) {
        cells.erase(cells.begin());
    }
    if (!cells.empty() && s.ends_with("|") && !s.ends_with("\\|")) {
        cells.pop_back();
    }
    for (std::string& c : cells) {
        c = py_strip(c);
    }
    return cells;
}

// 幾行裡的第一張表 → [[格…]…]（表頭是第 0 列，分隔線不算）；沒有＝nullopt。
std::optional<std::vector<std::vector<std::string>>> table_of(const Lines& lines) {
    std::vector<bool> inside = fenced(lines);
    for (size_t i = 0; i + 1 < lines.size(); ++i) {
        if (inside[i] || inside[i + 1] || lines[i].find('|') == std::string::npos || lines[i + 1].find('-') == std::string::npos ||
            !sep(lines[i + 1])) {
            continue;
        }
        std::vector<std::vector<std::string>> rows{cells_of(lines[i])};
        for (size_t j = i + 2; j < lines.size() && !inside[j] && !blank(lines[j]) && lines[j].find('|') != std::string::npos; ++j) {
            rows.push_back(cells_of(lines[j]));
        }
        return rows;
    }
    return std::nullopt;
}

bool closes(const std::string& l, const std::string& mark) {
    std::optional<Fence> m = fence(l);
    std::string s = py_strip(l);
    return m && s[0] == mark[0] && m->mark.size() >= mark.size() && only(s, mark[0]);
}

// 自己的內文整段只有一個 ```json 區塊 → 值；否則 nullopt。
std::optional<Json> json_block(const Lines& body) {
    size_t a = 0;
    size_t b = body.size();
    while (b > a && blank(body[b - 1])) {
        --b;
    }
    while (a < b && blank(body[a])) {
        ++a;
    }
    if (b - a < 2) {
        return std::nullopt;
    }
    std::optional<Fence> m = fence(body[a]);
    std::string s = py_strip(body[b - 1]);
    if (!m || ascii_lower(py_strip(m->rest)) != "json") {
        return std::nullopt;
    }
    const std::string& mark = m->mark;
    if (!(!s.empty() && s[0] == mark[0] && s.size() >= mark.size() && only(s, mark[0]))) {
        return std::nullopt;
    }
    std::vector<bool> inside = fenced(sub(body, a, b));
    if (!std::all_of(inside.begin(), inside.end(), [](bool x) { return x; })) {
        return std::nullopt;
    }
    std::string src;
    for (size_t i = a + 1; i + 1 < b; ++i) {
        if (closes(body[i], mark)) {
            return std::nullopt;
        }
        src += body[i];
        src += i + 2 < b ? "\n" : "";
    }
    Json v = Json::parse(src, nullptr, false);
    if (v.is_discarded()) {
        return std::nullopt;
    }
    return v;
}

// ---- 一個標題的範圍 ----

// 一個標題的範圍（root＝整份）：lines 全文、a..b 這一節的行、level 級數（root＝0）。
struct Scope {
    const Lines* lines = nullptr;
    const std::vector<H>* heads = nullptr;
    size_t a = 0;
    size_t b = 0;
    int level = 0;

    std::vector<H> inner() const {
        std::vector<H> out;
        for (const H& h : *heads) {
            if ((level ? a < h.line : a <= h.line) && h.line < b && h.level > level) {
                out.push_back(h);
            }
        }
        return out;
    }
    Lines body() const {
        size_t first = a + (level ? 1 : 0);
        std::vector<H> subs = inner();
        return sub(*lines, first, subs.empty() ? b : subs[0].line);
    }
    size_t end(const H& h) const {
        for (const H& x : *heads) {
            if (x.line > h.line && x.line < b && x.level <= h.level) {
                return x.line;
            }
        }
        return b;
    }
    // 直接的小節（跳過小節裡面的）。
    std::vector<H> direct() const {
        std::vector<H> out;
        size_t skip = 0;
        bool any = false;
        for (const H& h : inner()) {
            if (!any || h.line >= skip) {
                out.push_back(h);
                skip = end(h);
                any = true;
            }
        }
        return out;
    }
    Scope at(const H& h) const {
        return Scope{lines, heads, h.line, end(h), h.level};
    }
    std::optional<Scope> child(const std::string& tok) const {
        std::vector<H> subs = inner();
        std::vector<std::string> names;
        for (const H& h : subs) {
            names.push_back(h.title);
        }
        long i = pick(names, tok);
        if (i < 0) {
            return std::nullopt;
        }
        return at(subs[(size_t)i]);
    }
    std::optional<Json> json() const {
        if (!level || !inner().empty()) {
            return std::nullopt;
        }
        return json_block(body());
    }
    Json value() const {
        std::optional<Json> v = json();
        return v ? *v : Json(text_of(sub(*lines, a, b), false));
    }
};

// ---- 往下走 ----

enum class Kind { Scope, Body, Item, Value, Row, Json };

// 走到哪：scope／body（自己的內文）／item（清單的一項）／value（鍵的值）／row（表格的一列）／json（json 區塊裡的值）。
struct Node {
    Kind kind = Kind::Scope;
    Scope scope;
    Lines block;
    std::vector<std::string> row;
    Json value;
};

// 一段文字（自己的內文、清單項、鍵的值）往下一格。
std::optional<Node> block_step(const Lines& lines, const std::string& tok, bool skip_first) {
    Lines rest = skip_first ? sub(lines, 1, lines.size()) : lines;
    std::optional<std::vector<Lines>> items = list_of(rest);
    Node out;
    if (is_int(tok)) {
        size_t n = 0;
        if (items) {
            if (!below(tok, items->size(), n)) {
                return std::nullopt;
            }
            out.kind = Kind::Item;
            out.block = (*items)[n];
            return out;
        }
        std::optional<std::vector<std::vector<std::string>>> rows = table_of(rest);
        if (rows && below(tok, rows->size(), n)) {
            out.kind = Kind::Row;
            out.row = (*rows)[n];
            return out;
        }
        return std::nullopt;
    }
    if (!items) {
        return std::nullopt;
    }
    std::vector<std::string> keys;
    std::vector<std::pair<std::string, const Lines*>> keyed;   // (冒號後面的字, 那一項)
    for (const Lines& it : *items) {
        if (auto k = key_of(it[0])) {
            keys.push_back(k->first);
            keyed.push_back({k->second, &it});
        }
    }
    long i = pick(keys, tok);
    if (i < 0) {
        return std::nullopt;
    }
    const auto& [rest1, it] = keyed[(size_t)i];
    out.kind = Kind::Value;
    if (!rest1.empty()) {
        out.block.push_back(rest1);
    }
    out.block.insert(out.block.end(), it->begin() + 1, it->end());
    return out;
}

std::string block_text(const Lines& lines) {
    std::string t = text_of(lines);
    while (!t.empty() && t.back() == '\n') {
        t.pop_back();
    }
    return t;
}

std::optional<Json> json_step(const Json& v, const std::string& tok) {
    if (v.is_object()) {
        auto it = v.find(tok);
        if (it != v.end()) {
            return *it;
        }
    }
    size_t n = 0;
    if (v.is_array() && is_int(tok) && below(tok, v.size(), n)) {
        return v[n];
    }
    return std::nullopt;
}

std::vector<std::string> numbers(size_t n) {
    std::vector<std::string> out;
    for (size_t i = 0; i < n; ++i) {
        out.push_back(std::to_string(i));
    }
    return out;
}

std::vector<std::string> block_names(const Lines& lines, bool skip_first) {
    Lines rest = skip_first ? sub(lines, 1, lines.size()) : lines;
    if (std::optional<std::vector<Lines>> items = list_of(rest)) {
        std::vector<std::string> out;
        for (size_t i = 0; i < items->size(); ++i) {
            auto k = key_of((*items)[i][0]);
            out.push_back(k ? k->first : std::to_string(i));
        }
        return out;
    }
    std::optional<std::vector<std::vector<std::string>>> rows = table_of(rest);
    return rows ? numbers(rows->size()) : std::vector<std::string>{};
}

std::vector<std::string> json_names(const Json& v) {
    std::vector<std::string> out;
    if (v.is_object()) {
        for (auto it = v.begin(); it != v.end(); ++it) {
            out.push_back(it.key());
        }
    } else if (v.is_array()) {
        out = numbers(v.size());
    }
    return out;
}

// 這一格底下有哪些名字（給 ls 與錯誤訊息）。
std::vector<std::string> names_of(const Node& at) {
    switch (at.kind) {
        case Kind::Scope: {
            if (std::optional<Json> v = at.scope.json()) {
                return json_names(*v);
            }
            Lines body = at.scope.body();
            std::vector<std::string> out;
            if (!text_of(body).empty()) {
                out.push_back("_");
            }
            for (const H& h : at.scope.direct()) {
                out.push_back(h.title);
            }
            for (std::string& n : block_names(body, false)) {
                out.push_back(std::move(n));
            }
            return out;
        }
        case Kind::Body:
        case Kind::Value:
            return block_names(at.block, false);
        case Kind::Item:
            return block_names(at.block, true);
        case Kind::Row:
            return numbers(at.row.size());
        case Kind::Json:
            return json_names(at.value);
    }
    return {};
}

std::string escaped(const std::string& t) {
    std::string out;
    for (char c : t) {
        out += c == '~' ? "~0" : c == '/' ? "~1" : std::string(1, c);
    }
    return out;
}

// 走到底。走不到丟 Error{DirectiveBad, mdpath 的 reason}（呼叫者換成自己的代號）。
Node walk_md(const Lines& lines, const std::vector<H>& heads, const std::vector<std::string>& toks) {
    Node at;
    at.scope = Scope{&lines, &heads, 0, lines.size(), 0};
    for (size_t n = 0; n < toks.size(); ++n) {
        const std::string& tok = toks[n];
        std::optional<Node> nxt;
        if (at.kind == Kind::Scope) {
            std::optional<Json> v = at.scope.json();
            if (tok == "_") {
                nxt = Node{Kind::Body, {}, at.scope.body(), {}, {}};
            } else if (v) {
                if (std::optional<Json> got = json_step(*v, tok)) {
                    nxt = Node{Kind::Json, {}, {}, {}, *got};
                }
            } else if (std::optional<Scope> s = at.scope.child(tok)) {
                nxt = Node{Kind::Scope, *s, {}, {}, {}};
            } else {
                nxt = block_step(at.scope.body(), tok, false);
            }
        } else if (at.kind == Kind::Body || at.kind == Kind::Item || at.kind == Kind::Value) {
            nxt = block_step(at.block, tok, at.kind == Kind::Item);
        } else if (at.kind == Kind::Row) {
            size_t i = 0;
            if (is_int(tok) && below(tok, at.row.size(), i)) {
                nxt = Node{Kind::Json, {}, {}, {}, Json(at.row[i])};
            }
        } else {
            if (std::optional<Json> got = json_step(at.value, tok)) {
                nxt = Node{Kind::Json, {}, {}, {}, *got};
            }
        }
        if (!nxt) {
            std::string here = "the document";
            if (n > 0) {
                here.clear();
                for (size_t k = 0; k < n; ++k) {
                    here += "/" + escaped(toks[k]);
                }
            }
            std::vector<std::string> names = names_of(at);
            std::string has = " (nothing to go into)";
            if (!names.empty()) {
                has = " (it has: ";
                for (size_t k = 0; k < names.size() && k < 20; ++k) {
                    has += (k ? ", " : "") + names[k];
                }
                has += ")";
            }
            throw Error{code::DirectiveBad, here + " has no " + tok + has};
        }
        at = std::move(*nxt);
    }
    return at;
}

}  // namespace

bool md_path(const std::string& file) {
    return file.ends_with(".md");
}

Json md_get(const std::string& text, const std::vector<std::string>& toks) {
    Lines lines = split_lines(text);
    std::vector<H> heads = heads_of(lines);
    Node at = walk_md(lines, heads, toks);
    switch (at.kind) {
        case Kind::Scope:
            return toks.empty() ? Json(text) : at.scope.value();
        case Kind::Body:
            return text_of(at.block);
        case Kind::Item:
        case Kind::Value:
            return block_text(at.block);
        case Kind::Row:
            return Json(at.row);
        case Kind::Json:
            return at.value;
    }
    return nullptr;
}

std::vector<std::string> md_ls(const std::string& text, const std::vector<std::string>& toks) {
    Lines lines = split_lines(text);
    std::vector<H> heads = heads_of(lines);
    return names_of(walk_md(lines, heads, toks));
}

Json md_tree(const std::string& text) {
    Lines lines = split_lines(text);
    std::vector<H> heads = heads_of(lines);
    auto build = [](const Scope& sc, auto& self) -> Json {
        std::vector<H> subs = sc.direct();
        if (std::optional<Json> v = sc.json()) {
            return *v;
        }
        std::string own = text_of(sc.body());
        if (subs.empty() && sc.level) {
            return own;
        }
        Json out = Json::object();
        if (!own.empty()) {
            out["_"] = own;
        }
        for (const H& h : subs) {
            if (h.title != "_" && !out.contains(h.title)) {   // 叫 `_` 的標題尋不到（保留名）
                out[h.title] = self(sc.at(h), self);
            }
        }
        return out;
    };
    return build(Scope{&lines, &heads, 0, lines.size(), 0}, build);
}

}  // namespace aos
