// directive/md.hpp: internal declarations shared by md_text.cpp, md_blocks.cpp and md_walk.cpp (proto9 split of proto8 aos-directive src/md.cpp, which was one 926-line file).
//
// 逐條照 proto8 py/aos/mdpath.py 搬過來（規則以它與 py/tests/md_path_cases.json 為準）；Python 用 regex 的地方這裡手寫掃描，結果要一樣。
// 字串都是 UTF-8 的位元組：Python 的 str.strip()（Unicode 空白）用 py_strip 對齊；same 只在兩邊都是 ASCII 時才不分大小寫；
// 全形冒號「：」是三個位元組 EF BC 9A。純讀、不寫 md、不讀檔。proto9: md_ls and md_tree are not brought in.
#pragma once

#include "directive/directive.hpp"

#include <cstdint>
#include <optional>
#include <string>
#include <utility>
#include <vector>

namespace aos::md {

using Lines = std::vector<std::string>;

struct Fence {
    std::string mark;
    std::string rest;
};

struct Head {
    int level;
    std::optional<std::string> rest;
};

struct Item {
    size_t indent;
    size_t marker;
    std::optional<std::string> gap;    // ( +)
    std::optional<std::string> rest;   // (.*)
};

struct H {
    size_t line;
    int level;
    std::string title;
};

// ---- md_text.cpp：Python str 的小動作、四個 regex（FENCE、HEAD、ITEM、SEP）、名字比對 ----
bool py_space(uint32_t c);
std::pair<uint32_t, size_t> decode(const std::string& s, size_t i);
size_t lead_space(const std::string& s);
size_t trail_space(const std::string& s, size_t from = 0);
std::string py_strip(const std::string& s);
std::string py_rstrip(const std::string& s);
bool blank(const std::string& s);
bool is_ascii(const std::string& s);
std::string ascii_lower(std::string s);
bool only(const std::string& s, char c);
size_t indent(const std::string& l);
bool is_int(const std::string& t);
bool below(const std::string& t, size_t n, size_t& out);
std::optional<Fence> fence(const std::string& l);
std::optional<Head> head(const std::string& l);
std::optional<Item> item(const std::string& l);
bool sep(const std::string& l);
bool same(const std::string& a, const std::string& b);
long pick(const std::vector<std::string>& names, const std::string& tok);
Lines sub(const Lines& v, size_t a, size_t b);

// ---- md_blocks.cpp：行、圍欄、標題、清單、鍵、表格、json 區塊 ----
Lines split_lines(const std::string& text);
std::vector<bool> fenced(const Lines& lines);
std::string title_of(const std::optional<std::string>& rest);
std::vector<H> heads_of(const Lines& lines);
std::string text_of(const Lines& lines, bool lead = true);
std::optional<std::vector<Lines>> list_of(const Lines& lines);
bool colon_end(std::string after);
std::optional<std::pair<std::string, std::string>> key_of(const std::string& first);
std::vector<std::string> cells_of(const std::string& line);
std::optional<std::vector<std::vector<std::string>>> table_of(const Lines& lines);
bool closes(const std::string& l, const std::string& mark);
std::optional<Json> json_block(const Lines& body);

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

// ---- md_walk.cpp：往下走 ----

enum class Kind { Scope, Body, Item, Value, Row, Json };

// 走到哪：scope／body（自己的內文）／item（清單的一項）／value（鍵的值）／row（表格的一列）／json（json 區塊裡的值）。
struct Node {
    Kind kind = Kind::Scope;
    Scope scope;
    Lines block;
    std::vector<std::string> row;
    Json value;
};

}  // namespace aos::md
