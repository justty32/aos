// directive/resolve.cpp: walk a whole JSON value and replace every directive, then apply $path/$prefix (copy of proto8 aos-directive src/resolve.cpp without resolve_shallow/resolve_keys).
// 10-20 ideas D9～D15；$path 10-21 傍晚改成字串拼接（join_path）。
//
// 物件：有 $ref 就是 $ref（同時有 $env 也只看 $ref）；否則有 $env 就是 $env；都沒有＝普通物件，逐個 key 往下走
//       （不認得的 $xxx 不管）。寫法不合（回 nullopt）＝整個物件原封不動留著（不往裡面走）。
// 陣列：逐個往下走。其他值原樣。
// $ref 可以是陣列（10-23 使用者）：每一份各自解完再合成一份（ref.cpp 的 merge）。
#include "internal.hpp"

#include "util/files.hpp"

namespace aos::directive {

// $path 的字串拼接（10-21 傍晚 ideas § 9，原 os.path.join／aos::join）：sub 以 # 開頭＝直接接在後面（`x.json` + `#/a`）；
// 空字串＝不接；其他＝去掉 v 結尾的 /、去掉 sub 開頭的 /，中間剛好一個 /（寫絕對路徑不再整個取代）。
static std::string join_path(const std::string& v, const std::string& sub) {
    if (sub.empty()) {
        return v;
    }
    if (sub[0] == '#') {
        return v + sub;
    }
    size_t end = v.find_last_not_of('/');
    std::string head = "";
    if (end != std::string::npos) {
        head = v.substr(0, end + 1);
    }
    size_t start = sub.find_first_not_of('/');
    std::string tail = "";
    if (start != std::string::npos) {
        tail = sub.substr(start);
    }
    return head + "/" + tail;
}

Json walk(const Json& v, const RefBase& base, Chain& chain) {
    if (v.is_array()) {
        Json out = Json::array();
        for (size_t i = 0; i < v.size(); ++i) {
            out.push_back(walk(v[i], base.in(i), chain));
        }
        return out;
    }
    if (!v.is_object()) {
        return v;
    }
    std::optional<Json> got;
    if (v.contains("$ref")) {
        got = resolve_ref(v, base, chain);
    } else if (v.contains("$env")) {
        got = resolve_env(v);
    } else {
        Json out = Json::object();
        for (auto& [k, x] : v.items()) {
            out[k] = walk(x, base.in(k), chain);
        }
        return out;
    }
    if (!got) {
        return v;
    }
    return decorate(v, *got);
}

Json decorate(const Json& d, const Json& got) {
    if (!got.is_string()) {   // 換出來不是字串＝$path／$prefix 靜默不作用（D11）
        return got;
    }
    std::string s = got.get<std::string>();
    if (d.contains("$path") && d["$path"].is_string()) {
        s = join_path(s, d["$path"].get<std::string>());
    }
    if (d.contains("$prefix") && d["$prefix"].is_string()) {
        s = d["$prefix"].get<std::string>() + s;
    }
    return s;
}

}  // namespace aos::directive

namespace aos {

// 起點整理成絕對路徑（file 空照舊空；位置照帶）。
static RefBase absolute(const RefBase& b) {
    RefBase a = b;
    a.dir = aos::abspath(b.dir);
    a.file = b.file.empty() ? "" : aos::abspath(b.file);
    return a;
}

Json resolve(const Json& doc, const RefBase& base) {
    directive::Chain chain;
    return directive::walk(doc, absolute(base), chain);
}

RefBase Resolved::dir_of(const std::string& key) const {
    auto it = key_dirs.find(key);
    return it == key_dirs.end() ? base_dir.in(key) : it->second;
}

RefBase Resolved::dir_of(size_t i) const {
    return i < item_dirs.size() ? item_dirs[i] : base_dir.in(i);
}

}  // namespace aos
