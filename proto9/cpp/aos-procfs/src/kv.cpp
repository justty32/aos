// kv.cpp：「名稱: 值」一行的寫法與 json 字串的跳脫（欄位表 aos/fields.hpp 的兩種寫法都靠這兩個）。
#include "aos/procfs.hpp"

#include <cstdio>

namespace aos::procfs {

std::string kv_line(std::string_view name, std::string_view value) {
    std::string out;
    out.reserve(name.size() + value.size() + 3);
    out.append(name);
    out += ": ";
    if (value.empty()) {
        out += '-';
    } else {
        // 值裡的換行會變成另一行、被讀的人當成別的名稱，所以換成空白
        for (char c : value) out += (c == '\n' || c == '\r') ? ' ' : c;
    }
    out += '\n';
    return out;
}

std::string json_quote(std::string_view s) {
    std::string out = "\"";
    for (char c : s) {
        unsigned char u = static_cast<unsigned char>(c);
        if (c == '"' || c == '\\') {
            out += '\\';
            out += c;
        } else if (c == '\n') {
            out += "\\n";
        } else if (c == '\t') {
            out += "\\t";
        } else if (c == '\r') {
            out += "\\r";
        } else if (u < 0x20) {
            char buf[8];
            std::snprintf(buf, sizeof buf, "\\u%04x", u);
            out += buf;
        } else {
            out += c;   // UTF-8 原樣
        }
    }
    return out + "\"";
}

}  // namespace aos::procfs
