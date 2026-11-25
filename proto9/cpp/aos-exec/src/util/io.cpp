// util/io.cpp: dumps and fail (trimmed copy of proto8 aos-util src/io.cpp; see util/io.hpp).
#include "util/io.hpp"

#include <cstdio>

namespace aos {

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

int fail(const std::string& prog, const std::string& code, const std::string& msg) {
    std::fflush(stdout);
    print_line(stderr, prog + ": error: " + code + " " + msg);
    return 1;
}

int fail(const std::string& prog, const Error& e) {
    return fail(prog, e.code, e.msg);
}

}  // namespace aos
