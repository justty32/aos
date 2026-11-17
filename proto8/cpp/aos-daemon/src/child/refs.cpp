// refs.cpp：【child】把表與內嵌單子的路徑改寫成相對 daemon 或小格的參照。
#include "child/child.hpp"

#include <vector>

namespace aos::daemon {

std::string rel_to(const std::string& path, const std::string& base) {
    if (path.empty() || path[0] != '/' || base.empty() || base[0] != '/') {
        return path;
    }
    auto parts = [](const std::string& s) {
        std::vector<std::string> out;
        size_t i = 0;
        while (i < s.size()) {
            size_t j = s.find('/', i);
            if (j == std::string::npos) {
                j = s.size();
            }
            if (j > i) {
                out.push_back(s.substr(i, j - i));
            }
            i = j + 1;
        }
        return out;
    };
    std::vector<std::string> p = parts(path);
    std::vector<std::string> b = parts(base);
    size_t k = 0;
    while (k < p.size() && k < b.size() && p[k] == b[k]) {
        k += 1;
    }
    std::string out;
    for (size_t i = k; i < b.size(); i++) {
        out += out.empty() ? ".." : "/..";
    }
    for (size_t i = k; i < p.size(); i++) {
        out += (out.empty() ? "" : "/") + p[i];
    }
    return out.empty() ? "." : out;
}

std::string rel_spec(const std::string& spec, const std::string& base) {
    size_t hash = spec.find('#');
    std::string file = spec.substr(0, hash);
    if (file.empty() || file[0] != '/') {
        return spec;
    }
    return rel_to(file, base) + (hash == std::string::npos ? "" : spec.substr(hash));
}

Json daemon_ref(const std::string& abs, const std::string& dstack) {
    return Json::object({{"$env", "AOS_DAEMON"}, {"$path", rel_spec(abs, dstack)}});
}

// 內嵌單子寫進小格之前（11-05）：相對的 $ref 已在 read_procs 轉成絕對（abs_refs）；寫進小格時改成相對小格（$ref 本來就從它所在的檔算），
// 整份 image 搬走還解得開。只動 $ref 的檔名，跟 abs_refs 對稱。
Json rel_refs(const Json& v, const std::string& cell) {
    if (v.is_array()) {
        Json out = Json::array();
        for (const Json& x : v) {
            out.push_back(rel_refs(x, cell));
        }
        return out;
    }
    if (!v.is_object()) {
        return v;
    }
    Json out = v;
    if (v.contains("$ref")) {
        auto fix = [&](Json& s) {
            if (s.is_string()) {
                s = rel_spec(s.get<std::string>(), cell);
            }
        };
        Json& ref = out["$ref"];
        if (ref.is_array()) {
            for (Json& s : ref) {
                fix(s);
            }
        } else {
            fix(ref);
        }
        return out;
    }
    for (auto& [k, x] : out.items()) {
        x = rel_refs(x, cell);
    }
    return out;
}

}  // namespace aos::daemon
