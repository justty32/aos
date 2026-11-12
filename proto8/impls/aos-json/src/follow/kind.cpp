// kind.cpp：【follow】認指示詞（N-45 寬容規則，同 aos-directive 的 ref.cpp／env.cpp）。
//
// 有 $ref 就只看 $ref（寫法不合也不改看 $env）：字串＝「檔[#/指標]」或「#/指標」（檔名空＝寫著它的那份檔，11-12 晚 ref-hash），# 後一定要 /；
// # 後面的 `..`＝往外一層、根再 `..`＝檔所在的資料夾、之後再寫 # 又進檔（`#/../other.json#/k`）；可帶 `$at`（字串、不含 #）＝從 $ref 指到的
// 地方接著往下走——怎麼算交給 aos::ref_spot／ref_step（fetch）；
// 或是這種字串的非空陣列（有一個不合＝整個不合）。$env：非空字串。寫法不合＝FormBad（aos 會原封不動留著）。
#include "follow/follow.hpp"

namespace aos::json {

std::vector<std::pair<std::string, std::string>> ref_parts(const Json& v) {
    std::vector<std::pair<std::string, std::string>> out;
    std::optional<std::string> at = aos::ref_at_of(v);
    if (!at) {
        return out;
    }
    auto ok = [&](const Json& x) {   // 寫法照 aos-directive 那一支（空字串、# 後面不是 /＝不合）
        return x.is_string() && aos::ref_spot(x.get<std::string>(), RefBase{"/", "/_"}).has_value();
    };
    const Json& r = v["$ref"];
    if (r.is_array()) {
        for (const Json& x : r) {
            if (!ok(x)) {
                return {};
            }
            out.emplace_back(x.get<std::string>(), *at);
        }
    } else if (ok(r)) {
        out.emplace_back(r.get<std::string>(), *at);
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
