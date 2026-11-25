// directive/md_blocks.cpp: lines, code fences, headings, lists, keys, tables and the json fence of a markdown text (part of proto8 aos-directive src/md.cpp).
#include "directive/md.hpp"

#include <algorithm>

namespace aos::md {

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
std::string text_of(const Lines& lines, bool lead) {
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

// ---- 清單、鍵、表格、json 區塊 ----

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

}  // namespace aos::md
