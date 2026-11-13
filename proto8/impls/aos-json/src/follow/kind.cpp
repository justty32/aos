// kind.cpp：【follow】認指示詞（N-45 寬容規則，同 aos-directive 的 ref.cpp／env.cpp）。
//
// 有 $ref 就只看 $ref（寫法不合也不改看 $env）：字串（# 左邊檔案系統、右邊 json 內部，11-13 ref-path-rules）或這種字串的非空陣列
// （有一個不是字串＝整個不合）。路徑寫壞（#aaa、y.json#./…）不算 FormBad：照 aos-directive 是 DirectiveBad，fetch 時丟（怎麼算交給 aos::ref_spot）。
// $env：非空字串。寫法不合＝FormBad（aos 會原封不動留著）。
#include "follow/follow.hpp"

namespace aos::json {

std::vector<std::string> ref_parts(const Json& v) {
    std::vector<std::string> out;
    auto ok = [&](const Json& x) {   // 寫法照 aos-directive 那一支（不是字串＝不合）
        return x.is_string();
    };
    const Json& r = v["$ref"];
    if (r.is_array()) {
        for (const Json& x : r) {
            if (!ok(x)) {
                return {};
            }
            out.push_back(x.get<std::string>());
        }
    } else if (ok(r)) {
        out.push_back(r.get<std::string>());
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
