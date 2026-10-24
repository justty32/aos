// splice.cpp：【doc】只重寫有變的那一塊，其他照原文一個字都不動（diff 小、手排的格式留著）。
//
// 1. 從根往下找「變的那一塊」：新舊兩邊都是物件且 key 一樣（順序也一樣）、或都是陣列且一樣長，而且只有一個孩子不同
//    ＝往那個孩子走；不然就停在這裡（加 key、刪 key、append、整個換＝停在那個容器或那個值）。
// 2. 在原文裡找到那一塊的起訖（自己掃 JSON：字串、數字、true／false／null、物件、陣列）。
// 3. 那一塊原本在一行裡＝新的也寫一行（aos 的 dumps：", "、": "）；原本跨行＝照檔的縮排展開，
//    第二行起每行前面補上那一塊開頭那一行的前導空白。
// 找不到（例如物件裡有重複的 key）就回 nullopt，呼叫者整份重排。
#include "doc/doc.hpp"

#include <iterator>

namespace aos::json {

namespace {

struct Scan {
    const std::string& s;
    size_t i = 0;
    bool ok = true;

    void ws() {
        while (i < s.size() && (s[i] == ' ' || s[i] == '\t' || s[i] == '\n' || s[i] == '\r')) {
            i += 1;
        }
    }
    void string() {
        i += 1;   // "
        while (i < s.size() && s[i] != '"') {
            i += s[i] == '\\' ? 2 : 1;
        }
        i += 1;
    }
    void value() {
        ws();
        if (i >= s.size()) {
            ok = false;
            return;
        }
        char c = s[i];
        if (c == '"') {
            string();
        } else if (c == '{' || c == '[') {
            char close = c == '{' ? '}' : ']';
            i += 1;
            ws();
            if (i < s.size() && s[i] == close) {
                i += 1;
                return;
            }
            while (ok && i < s.size()) {
                if (c == '{') {
                    ws();
                    string();
                    ws();
                    i += 1;   // :
                }
                value();
                ws();
                if (i < s.size() && s[i] == ',') {
                    i += 1;
                    continue;
                }
                if (i < s.size() && s[i] == close) {
                    i += 1;
                    return;
                }
                ok = false;
            }
            ok = false;
        } else {
            while (i < s.size() && std::string(",]} \t\r\n").find(s[i]) == std::string::npos) {
                i += 1;
            }
        }
    }
    // 現在停在一個容器的開頭：列出每個成員（key 或值的開頭、值的起訖、物件的 key）與收尾括號的位置。
    struct Member {
        size_t start;
        size_t vstart;
        size_t vend;
        std::string key;
    };
    std::vector<Member> members(size_t& close) {
        std::vector<Member> out;
        char c = s[i];
        i += 1;
        ws();
        while (ok && i < s.size() && s[i] != '}' && s[i] != ']') {
            Member m{i, i, i, ""};
            if (c == '{') {
                string();
                Json key = Json::parse(s.substr(m.start, i - m.start), nullptr, false);
                m.key = key.is_string() ? key.get<std::string>() : "";
                ws();
                i += 1;   // :
                ws();
                m.vstart = i;
            }
            value();
            m.vend = i;
            out.push_back(m);
            ws();
            if (i < s.size() && s[i] == ',') {
                i += 1;
                ws();
            }
        }
        close = i;
        if (i >= s.size()) {
            ok = false;
        }
        i += 1;
        return out;
    }
    // 找孩子 tok，停在孩子的值開頭。物件裡同名的 key 出現兩次＝失敗。
    bool enter(const std::string& tok, bool is_obj) {
        if (s[i] != (is_obj ? '{' : '[')) {
            return false;
        }
        size_t close = 0;
        std::vector<Member> ms = members(close);
        int hits = 0;
        for (size_t k = 0; k < ms.size(); ++k) {
            if ((is_obj && ms[k].key == tok) || (!is_obj && std::to_string(k) == tok)) {
                i = ms[k].vstart;
                hits += 1;
            }
        }
        return ok && hits == 1;
    }
};


// pos 那一行的前導空白。
std::string pad_of(const std::string& body, size_t pos) {
    size_t line = body.rfind('\n', pos == 0 ? 0 : pos - 1);
    line = (line == std::string::npos || pos == 0) ? 0 : line + 1;
    size_t lead = line;
    while (lead < pos && (body[lead] == ' ' || body[lead] == '\t')) {
        lead += 1;
    }
    return body.substr(line, lead - line);
}

// 一個值寫成字：flat＝一行；不然照檔的縮排展開，第二行起前面補 pad。
std::string render(const File& f, const Json& v, bool flat, const std::string& pad) {
    if (flat) {
        return aos::dumps(v);
    }
    std::string text;
    for (char c : v.dump(f.indent, f.indent_char)) {
        text += c;
        if (c == '\n') {
            text += pad;
        }
    }
    return text;
}

// 同一種容器、只多一個（接在最後）或只少一個成員：只插入或拿掉那一個，其他成員的原文不動。sc 停在容器開頭。
std::optional<std::string> add_or_remove(const File& f, Scan& sc, const Json& a, const Json& b) {
    bool obj = a.is_object() && b.is_object();
    if (!obj && !(a.is_array() && b.is_array())) {
        return std::nullopt;
    }
    size_t start = sc.i;
    size_t close = 0;
    std::vector<Scan::Member> ms = sc.members(close);
    if (!sc.ok || ms.size() != a.size()) {
        return std::nullopt;
    }
    const std::string& t = f.body;
    auto key_at = [](const Json& j, size_t k) { return j.is_object() ? std::next(j.begin(), (long)k).key() : std::string(); };
    auto val_at = [](const Json& j, size_t k) { return *std::next(j.begin(), (long)k); };
    if (b.size() == a.size() + 1) {
        for (size_t k = 0; k < a.size(); ++k) {
            if (key_at(a, k) != key_at(b, k) || val_at(a, k) != val_at(b, k)) {
                return std::nullopt;
            }
        }
        size_t n = a.size();
        bool flat = t.substr(start, close - start).find('\n') == std::string::npos;
        if (flat || ms.empty()) {
            if (!flat) {
                return std::nullopt;
            }
            std::string m = (ms.empty() ? "" : ", ") + (obj ? aos::dumps(key_at(b, n)) + ": " : std::string()) +
                            aos::dumps(val_at(b, n));
            return t.substr(0, close) + m + t.substr(close);
        }
        std::string pad = pad_of(t, ms.back().start);
        std::string m = ",\n" + pad + (obj ? aos::dumps(key_at(b, n)) + ": " : std::string()) +
                        render(f, val_at(b, n), false, pad);
        return t.substr(0, ms.back().vend) + m + t.substr(ms.back().vend);
    }
    if (a.size() == b.size() + 1) {
        size_t r = 0;
        while (r < b.size() && key_at(a, r) == key_at(b, r) && val_at(a, r) == val_at(b, r)) {
            r += 1;
        }
        for (size_t k = r; k < b.size(); ++k) {
            if (key_at(a, k + 1) != key_at(b, k) || val_at(a, k + 1) != val_at(b, k)) {
                return std::nullopt;
            }
        }
        if (ms.size() == 1) {
            return t.substr(0, start + 1) + t.substr(close);
        }
        if (r > 0) {
            return t.substr(0, ms[r - 1].vend) + t.substr(ms[r].vend);
        }
        return t.substr(0, ms[0].start) + t.substr(ms[1].start);
    }
    return std::nullopt;
}

}  // namespace

std::optional<std::string> splice(const File& f, const Json& before, const Json& after) {
    std::vector<std::string> path;
    const Json* a = &before;
    const Json* b = &after;
    while (true) {
        bool same_shape = (a->is_object() && b->is_object() && a->size() == b->size()) ||
                          (a->is_array() && b->is_array() && a->size() == b->size());
        if (!same_shape) {
            break;
        }
        std::string diff;
        int n = 0;
        bool keys_same = true;
        auto ia = a->begin();
        auto ib = b->begin();
        for (size_t k = 0; k < a->size(); ++k, ++ia, ++ib) {
            std::string key = a->is_object() ? ia.key() : std::to_string(k);
            if (a->is_object() && ia.key() != ib.key()) {
                keys_same = false;
                break;
            }
            if (*ia != *ib) {
                diff = key;
                n += 1;
            }
        }
        if (!keys_same || n != 1) {
            break;
        }
        path.push_back(diff);
        a = a->is_object() ? &(*a)[diff] : &(*a)[std::stoull(diff)];
        b = b->is_object() ? &(*b)[diff] : &(*b)[std::stoull(diff)];
    }
    Scan sc{f.body};
    sc.ws();
    const Json* walk = &before;
    for (const std::string& t : path) {
        bool is_obj = walk->is_object();
        if (!sc.enter(t, is_obj)) {
            return std::nullopt;
        }
        walk = is_obj ? &(*walk)[t] : &(*walk)[std::stoull(t)];
    }
    size_t start = sc.i;
    std::optional<std::string> one = add_or_remove(f, sc, *a, *b);
    if (one) {
        return one;
    }
    if (path.empty()) {
        return std::nullopt;   // 變的是整份：整份重排
    }
    sc.i = start;
    sc.ok = true;
    sc.value();
    if (!sc.ok) {
        return std::nullopt;
    }
    size_t end = sc.i;
    bool flat = f.body.substr(start, end - start).find('\n') == std::string::npos;
    return f.body.substr(0, start) + render(f, *b, flat, pad_of(f.body, start)) + f.body.substr(end);
}

}  // namespace aos::json
