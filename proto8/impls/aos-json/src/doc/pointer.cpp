// pointer.cpp：【doc】`檔#/指標` 的尋址（N-62：第一個 # 就切、# 後一定要 /、指標照 RFC 6901）。
#include "doc/doc.hpp"

#include "aos/files.hpp"

#include <filesystem>

namespace aos::json {

std::vector<std::string> split_pointer(const std::string& ptr) {
    std::vector<std::string> toks;
    if (ptr.empty()) {
        return toks;
    }
    size_t i = 1;
    while (true) {
        size_t next = ptr.find('/', i);
        std::string raw = ptr.substr(i, next == std::string::npos ? std::string::npos : next - i);
        std::string tok;
        for (size_t k = 0; k < raw.size(); ++k) {
            if (raw[k] == '~' && k + 1 < raw.size() && raw[k + 1] == '1') {
                tok += '/';
                ++k;
            } else if (raw[k] == '~' && k + 1 < raw.size() && raw[k + 1] == '0') {
                tok += '~';
                ++k;
            } else {
                tok += raw[k];
            }
        }
        toks.push_back(tok);
        if (next == std::string::npos) {
            break;
        }
        i = next + 1;
    }
    return toks;
}

std::string pointer_of(const std::vector<std::string>& toks) {
    std::string out;
    for (const std::string& t : toks) {
        out += "/";
        for (char c : t) {
            if (c == '~') {
                out += "~0";
            } else if (c == '/') {
                out += "~1";
            } else {
                out += c;
            }
        }
    }
    return out;
}

Spec parse_spec(const std::string& s) {
    Spec out;
    size_t hash = s.find('#');
    out.file = s.substr(0, hash);
    if (out.file.empty()) {
        throw Error{code::SpecBad, "沒寫檔名：" + s};
    }
    if (hash != std::string::npos) {
        std::string ptr = s.substr(hash + 1);
        if (!ptr.starts_with("/")) {
            throw Error{code::SpecBad, s + " 的 # 後面要接 /"};
        }
        out.toks = split_pointer(ptr);
    }
    return out;
}

bool is_index(const std::string& tok, size_t size) {
    if (tok.empty() || tok.size() > 18 || (tok.size() > 1 && tok[0] == '0')) {
        return false;
    }
    for (char c : tok) {
        if (c < '0' || c > '9') {
            return false;
        }
    }
    return std::stoull(tok) < size;
}

Json* child(Json& node, const std::string& tok) {
    if (node.is_object()) {
        auto it = node.find(tok);
        return it == node.end() ? nullptr : &*it;
    }
    if (node.is_array() && is_index(tok, node.size())) {
        return &node[std::stoull(tok)];
    }
    return nullptr;
}

std::string shown(const std::string& real, const std::vector<std::string>& toks) {
    std::string cwd = std::filesystem::current_path().string();
    std::string path = real;
    if (real.starts_with(cwd + "/")) {
        path = real.substr(cwd.size() + 1);
    }
    if (toks.empty()) {
        return path;
    }
    return path + "#" + pointer_of(toks);
}

}  // namespace aos::json
