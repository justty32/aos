// io.cpp：【aos-util】三扇門——stdin 讀一份 JSON、stdout 印一行、stderr 印錯誤（說明見 include/aos/io.hpp）。
#include "aos/io.hpp"

#include <cctype>
#include <cstdio>
#include <iostream>
#include <iterator>
#include <sstream>
#include <vector>

namespace aos {

// 一串 JSON 值（空白隔開，可跨行）→ 一個個值；壞掉的尾巴丟掉。
// nlohmann 的 `stream >> json` 一次讀一個值、停在那個值後面，剛好拿來一個個讀。
std::vector<Json> read_stream(const std::string& text) {
    std::vector<Json> out;
    std::istringstream in(text);
    while (true) {
        in >> std::ws;
        if (in.peek() == std::char_traits<char>::eof()) {
            return out;
        }
        Json v;
        try {
            in >> v;
        } catch (const Json::exception&) {
            return out;
        }
        out.push_back(std::move(v));
    }
}

// 整段都是空白（或空的）。
static bool is_blank(const std::string& text) {
    for (unsigned char c : text) {
        if (!std::isspace(c)) {
            return false;
        }
    }
    return true;
}

Json read_stdin() {
    std::string text(std::istreambuf_iterator<char>(std::cin), {});
    std::vector<Json> docs = read_stream(text);
    if (docs.empty() && is_blank(text)) {
        return Json::object();
    }
    if (docs.empty()) {
        throw Error{code::JsonSyntax, "stdin 沒有 JSON"};
    }
    if (docs.size() > 1) {
        throw Error{code::InputExtra, "stdin 有 " + std::to_string(docs.size()) + " 份 JSON，只要一份"};
    }
    return docs[0];
}

// 純量（字串、數字、布林、null）交給 nlohmann；壞掉的 UTF-8 換成 U+FFFD，不丟例外。
static std::string dump_scalar(const Json& v) {
    return v.dump(-1, ' ', false, Json::error_handler_t::replace);
}

// 物件、陣列自己拼，才能用 Python 的 ", "、": "（nlohmann 的 dump 不加空白）。
static void dump_to(std::string& out, const Json& v) {
    if (v.is_object()) {
        out += '{';
        bool first = true;
        for (auto& [k, x] : v.items()) {
            if (!first) {
                out += ", ";
            }
            first = false;
            out += dump_scalar(Json(k));
            out += ": ";
            dump_to(out, x);
        }
        out += '}';
        return;
    }
    if (v.is_array()) {
        out += '[';
        for (size_t i = 0; i < v.size(); ++i) {
            if (i > 0) {
                out += ", ";
            }
            dump_to(out, v[i]);
        }
        out += ']';
        return;
    }
    out += dump_scalar(v);
}

std::string dumps(const Json& v) {
    std::string out;
    dump_to(out, v);
    return out;
}

static void print_line(FILE* stream, const std::string& line) {
    std::fputs(line.c_str(), stream);
    std::fputc('\n', stream);
    std::fflush(stream);
}

int emit(const Json& v) {
    print_line(stdout, dumps(v));
    return 0;
}

int emit_error(const Error& e) {
    Json err = {{"error", {{"code", e.code}, {"msg", e.msg}}}};
    print_line(stderr, dumps(err));
    return 1;
}

// nlohmann 解 JSON 時，非負整數存成 unsigned、負的存成 signed；程式裡自己放進去的整數則是 signed。兩種都看。
bool is_count(const Json& v) {
    if (!v.is_number_integer()) {
        return false;
    }
    if (v.is_number_unsigned()) {
        return true;
    }
    return v.get<long long>() >= 0;
}

}  // namespace aos
