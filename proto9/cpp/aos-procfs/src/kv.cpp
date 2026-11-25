// kv.cpp：「名稱: 值」一行一個的純文字產生器（status、settings、attrs 共用）。
#include "aos/procfs.hpp"

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

Kv& Kv::add(std::string_view name, std::string_view value) {
    out_ += kv_line(name, value);
    return *this;
}

Kv& Kv::add(std::string_view name, long long value) {
    out_ += kv_line(name, std::to_string(value));
    return *this;
}

Kv& Kv::raw(std::string_view lines) {
    out_.append(lines);
    return *this;
}

}  // namespace aos::procfs
