// ref.cpp：{"$ref": "檔[#/指標]"[, "$at": 指標]}——換成那份 JSON 檔裡那個位置的值，取回來的值接著解。
// $ref 也可以是這種字串的陣列（10-23 使用者）：每個元素各取一份、各自接著解，再照順序合成一份（merge）。
//
// 1. 寫法：$ref 不是字串、空字串、只有 #/…（沒檔名）、# 後面不是 /＝回 nullopt（原封不動，D15）；陣列＝空的、或有一個元素這樣＝回 nullopt；
//    $at 不是字串、或不是空字串也不是 / 開頭＝當沒寫（D14）；兩個都寫＝$at 接在 #/ 後面（D7）。
//    修飾詞都帶 $（10-23 命名統合；沒帶 $ 的 at 是普通 key、不作用）
// 2. 相對檔名從這一層的 base 算（最外層＝呼叫者給的 base_dir；被 $ref 進來的檔＝它解開捷徑後所在的資料夾）
// 3. 同一個（檔＋指標）已經在鏈上＝繞圈
// 4. 讀檔（第一行 #! 跳過）、解 JSON（讀不到、不是 JSON＝錯）、照指標取值（指不到＝錯），推上鏈、接著往下解
// 錯一律 DirectiveBad。
#include "internal.hpp"

#include "aos/files.hpp"

#include <cstdlib>
#include <fstream>
#include <iterator>
#include <unordered_map>

#include <sys/stat.h>

namespace aos::directive {

namespace fs = std::filesystem;

// 路徑 → realpath（絕對、捷徑解開）。檔不在就整理一下字面（反正接著讀檔會失敗）。
static std::string real_path(const std::string& p) {
    char* r = ::realpath(p.c_str(), nullptr);
    if (r == nullptr) {
        return fs::path(aos::abspath(p)).lexically_normal().string();
    }
    std::string s = r;
    std::free(r);
    return s;
}

// 讀一份 JSON 檔（第一行 #! 跳過）；讀不到（含資料夾）或不是 JSON＝DirectiveBad。
static Json load(const std::string& path) {
    struct stat st;
    bool is_dir = ::stat(path.c_str(), &st) == 0 && S_ISDIR(st.st_mode);
    std::ifstream f(path, std::ios::binary);
    if (!f || is_dir) {
        throw Error{code::DirectiveBad, "$ref 讀不到 " + path};
    }
    std::string text(std::istreambuf_iterator<char>(f), {});
    if (text.starts_with("#!")) {
        size_t nl = text.find('\n');
        text = nl == std::string::npos ? "" : text.substr(nl + 1);
    }
    Json doc = Json::parse(text, nullptr, false);
    if (doc.is_discarded()) {
        throw Error{code::DirectiveBad, "$ref " + path + " 不是 JSON"};
    }
    return doc;
}

static bool all_digits(const std::string& s) {
    if (s.empty()) {
        return false;
    }
    for (char c : s) {
        if (c < '0' || c > '9') {
            return false;
        }
    }
    return true;
}

// RFC 6901：ptr 是空字串（整份）或 /a/b（~1＝/、~0＝~）。陣列索引不收前導 0、不收 "-"。指不到＝DirectiveBad。
static Json pointer(const Json& doc, const std::string& ptr, const std::string& file) {
    const Json* cur = &doc;
    size_t i = 1;
    while (i <= ptr.size() && !ptr.empty()) {
        size_t next = ptr.find('/', i);
        if (next == std::string::npos) {
            next = ptr.size();
        }
        std::string tok;
        std::string raw = ptr.substr(i, next - i);
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
        if (cur->is_object() && cur->contains(tok)) {
            cur = &(*cur)[tok];
        } else if (cur->is_array() && all_digits(tok) && (tok == "0" || tok[0] != '0') && tok.size() < 18 &&
                   std::stoull(tok) < cur->size()) {
            cur = &(*cur)[std::stoull(tok)];
        } else {
            throw Error{code::DirectiveBad, "$ref 指不到：" + file + "#" + ptr};
        }
        i = next + 1;
    }
    return *cur;
}

// 一個元素（"檔[#/指標]"）的寫法：不是字串、空字串、只有 #/…（沒檔名）、# 後面不是 /＝nullopt；回（檔, 指標＋at）。
static std::optional<std::pair<std::string, std::string>> parse_spec(const Json& ref, const std::string& at) {
    if (!ref.is_string()) {
        return std::nullopt;
    }
    std::string spec = ref.get<std::string>();
    std::string path = spec;
    std::string ptr;
    size_t hash = spec.find('#');
    if (hash != std::string::npos) {
        path = spec.substr(0, hash);
        ptr = spec.substr(hash + 1);
        if (!ptr.starts_with("/")) {
            return std::nullopt;
        }
    }
    if (path.empty()) {
        return std::nullopt;
    }
    return std::make_pair(path, ptr + at);
}

std::optional<std::vector<Fetched>> fetch_ref(const Json& d, const std::string& base, const Chain& chain) {
    // 1. 寫法：字串＝一份；陣列（10-23 使用者）＝每個元素一份，空陣列或有一個不合＝整個不合
    std::string at;
    if (d.contains("$at") && d["$at"].is_string()) {
        std::string a = d["$at"].get<std::string>();
        if (a.empty() || a[0] == '/') {
            at = a;
        }
    }
    const Json& ref = d["$ref"];
    std::vector<std::pair<std::string, std::string>> specs;
    if (ref.is_array()) {
        if (ref.empty()) {
            return std::nullopt;
        }
        for (const Json& r : ref) {
            auto one = parse_spec(r, at);
            if (!one) {
                return std::nullopt;
            }
            specs.push_back(*one);
        }
    } else {
        auto one = parse_spec(ref, at);
        if (!one) {
            return std::nullopt;
        }
        specs.push_back(*one);
    }

    std::vector<Fetched> out;
    for (const auto& [path, ptr] : specs) {
        // 2～3. 從這一層算、看繞圈（鏈＝往上那幾層；同一個陣列裡寫兩次同一份不算繞圈）
        std::string file = real_path(aos::join(base, path));
        std::pair<std::string, std::string> here{file, ptr};
        for (const auto& seen : chain) {
            if (seen == here) {
                std::string walked;
                for (const auto& s : chain) {
                    walked += s.first + (s.second.empty() ? "" : "#" + s.second) + " → ";
                }
                throw Error{code::DirectiveBad, "$ref 繞圈：" + walked + file + (ptr.empty() ? "" : "#" + ptr)};
            }
        }
        // 4. 讀、取值（原文，還沒往下解）
        Fetched f;
        f.value = pointer(load(file), ptr, file);
        f.here = here;
        out.push_back(std::move(f));
    }
    return out;
}

std::optional<Json> resolve_ref(const Json& d, const std::string& base, Chain& chain) {
    std::optional<std::vector<Fetched>> fs = fetch_ref(d, base, chain);
    if (!fs) {
        return std::nullopt;
    }
    // 每一份推上鏈、往下解（那份檔裡的 $ref 從它實際所在的資料夾算），再合成一份
    std::vector<Resolved> parts;
    for (Fetched& f : *fs) {
        chain.push_back(f.here);
        parts.push_back({walk(f.value, aos::dirname(f.here.first), chain), aos::dirname(f.here.first), {}, {}});
        chain.pop_back();
    }
    return merge(parts, aos::dumps(d["$ref"])).value;
}

// 合成一份（說明見 internal.hpp）。
Resolved merge(std::vector<Resolved>& parts, const std::string& where) {
    if (parts.size() == 1) {
        return std::move(parts[0]);
    }
    bool objects = true;
    bool arrays = true;
    for (const Resolved& p : parts) {
        objects = objects && p.value.is_object();
        arrays = arrays && p.value.is_array();
    }
    Resolved out;
    out.base_dir = parts[0].base_dir;
    if (arrays) {
        out.value = Json::array();
        for (Resolved& p : parts) {
            for (size_t i = 0; i < p.value.size(); ++i) {
                out.item_dirs.push_back(p.dir_of(i));
                out.value.push_back(std::move(p.value[i]));
            }
        }
        return out;
    }
    if (!objects) {
        throw Error{code::DirectiveBad, "$ref " + where + " 的幾份合不起來（要都是物件或都是陣列）"};
    }
    out.value = Json::object();
    // ordered_json 的 [] 逐個比對 key（N 個就 N×N）：自己記位置、直接接在尾巴；同名的就地蓋掉（位置留在第一次出現的地方）
    auto& vec = static_cast<std::vector<std::pair<const std::string, Json>>&>(out.value.get_ref<Json::object_t&>());
    std::unordered_map<std::string, size_t> pos;
    for (Resolved& p : parts) {
        for (auto& [k, x] : p.value.items()) {
            auto it = pos.find(k);
            if (it == pos.end()) {
                pos.emplace(k, vec.size());
                vec.emplace_back(k, std::move(x));
            } else {
                vec[it->second].second = std::move(x);
            }
            out.key_dirs[k] = p.dir_of(k);
        }
    }
    return out;
}

}  // namespace aos::directive
