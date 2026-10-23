// resolve.cpp：走遍整份 JSON，認出指示詞、分派給 $ref（ref.cpp）／$env（env.cpp），換出來是字串再接 $path、加 $prefix。
// 10-20 ideas D9～D15；$path 10-21 傍晚改成字串拼接（join_path）。
//
// 物件：有 $ref 就是 $ref（同時有 $env 也只看 $ref）；否則有 $env 就是 $env；都沒有＝普通物件，逐個 key 往下走
//       （不認得的 $xxx 不管）。寫法不合（回 nullopt）＝整個物件原封不動留著（不往裡面走）。
// 陣列：逐個往下走。其他值原樣。
// $ref 可以是陣列（10-23 使用者）：每一份各自解完再合成一份（ref.cpp 的 merge）。
#include "internal.hpp"

#include "aos/files.hpp"

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

Json walk(const Json& v, const std::string& base, Chain& chain) {
    if (v.is_array()) {
        Json out = Json::array();
        for (const Json& x : v) {
            out.push_back(walk(x, base, chain));
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
            out[k] = walk(x, base, chain);
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

// 只換這一格（10-23 晚，aos 讀的 JSON 都解指示詞）：v 是指示詞就換成它指到的原文；原文本身又是指示詞就再換，
// 一直到不是指示詞（或寫法不合、原封不動）為止；不往物件、陣列裡面走。回換好的值與它裡面相對 $ref 的起點。
// $ref 陣列：每一份各自這樣換（鏈各自往下接），再合成一份；合出來的每個 key／元素記著它來自哪份檔（merge）。
static Resolved shallow(const Json& v, const std::string& base, const Chain& chain) {
    if (!v.is_object()) {
        return {v, base, {}, {}};
    }
    if (v.contains("$ref")) {
        std::optional<std::vector<Fetched>> fs = fetch_ref(v, base, chain);
        if (!fs) {
            return {v, base, {}, {}};
        }
        std::vector<Resolved> parts;
        for (const Fetched& f : *fs) {
            Chain c = chain;
            c.push_back(f.here);
            parts.push_back(shallow(f.value, aos::dirname(f.here.first), c));
        }
        Resolved in = merge(parts, aos::dumps(v["$ref"]));
        in.value = decorate(v, in.value);
        return in;
    }
    if (v.contains("$env")) {
        std::optional<Json> got = resolve_env(v);
        if (!got) {
            return {v, base, {}, {}};
        }
        return {decorate(v, *got), base, {}, {}};
    }
    return {v, base, {}, {}};
}

}  // namespace aos::directive

namespace aos {

Json resolve(const Json& doc, const std::filesystem::path& base_dir, const std::string& where) {
    (void)where;
    directive::Chain chain;
    return directive::walk(doc, aos::abspath(base_dir.string()), chain);
}

Resolved resolve_shallow(const Json& v, const std::filesystem::path& base_dir) {
    directive::Chain chain;
    return directive::shallow(v, aos::abspath(base_dir.string()), chain);
}

const std::string& Resolved::dir_of(const std::string& key) const {
    auto it = key_dirs.find(key);
    return it == key_dirs.end() ? base_dir : it->second;
}

const std::string& Resolved::dir_of(size_t i) const {
    return i < item_dirs.size() ? item_dirs[i] : base_dir;
}

}  // namespace aos
