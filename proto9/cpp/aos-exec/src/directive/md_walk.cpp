// directive/md_walk.cpp: walk a markdown text by RFC 6901 tokens and give the value there (md_get; part of proto8 aos-directive src/md.cpp).
#include "directive/md.hpp"

namespace aos::md {

// ---- 往下走 ----

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

}  // namespace aos::md

namespace aos {

using namespace aos::md;

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

}  // namespace aos
