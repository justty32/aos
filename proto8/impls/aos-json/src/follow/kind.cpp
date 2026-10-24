// kind.cpp：【follow】認指示詞（N-45 寬容規則，同 aos-directive 的 ref.cpp／env.cpp）。
//
// 有 $ref 就只看 $ref（寫法不合也不改看 $env）：字串＝「檔[#/指標]」，檔名不能空、# 後一定要 /；
// 或是這種字串的非空陣列（有一個不合＝整個不合）。$env：非空字串。寫法不合＝FormBad（aos 會原封不動留著）。
#include "follow/follow.hpp"

namespace aos::json {

static std::optional<std::pair<std::string, std::string>> one_part(const Json& r) {
    if (!r.is_string()) {
        return std::nullopt;
    }
    std::string spec = r.get<std::string>();
    size_t hash = spec.find('#');
    std::string path = spec.substr(0, hash);
    std::string ptr;
    if (hash != std::string::npos) {
        ptr = spec.substr(hash + 1);
        if (!ptr.starts_with("/")) {
            return std::nullopt;
        }
    }
    if (path.empty()) {
        return std::nullopt;
    }
    return std::make_pair(path, ptr);
}

std::vector<std::pair<std::string, std::string>> ref_parts(const Json& v) {
    std::vector<std::pair<std::string, std::string>> out;
    const Json& r = v["$ref"];
    if (r.is_array()) {
        for (const Json& x : r) {
            auto p = one_part(x);
            if (!p) {
                return {};
            }
            out.push_back(*p);
        }
        return out;
    }
    auto p = one_part(r);
    if (p) {
        out.push_back(*p);
    }
    return out;
}

Kind kind_of(const Json& v) {
    if (!v.is_object()) {
        return Kind::Plain;
    }
    if (v.contains("$ref")) {
        return ref_parts(v).empty() ? Kind::FormBad : Kind::Ref;
    }
    if (v.contains("$env")) {
        const Json& e = v["$env"];
        return e.is_string() && !e.get<std::string>().empty() ? Kind::Env : Kind::FormBad;
    }
    return Kind::Plain;
}

}  // namespace aos::json
