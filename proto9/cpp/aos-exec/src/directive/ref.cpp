// directive/ref.cpp: {"$ref": ...} reads the file (JSON or .md), checks loops and merges arrays of refs (copy of proto8 aos-directive src/ref.cpp; ref_spot moved to spot.cpp).
//
// （以下是 proto8 原註）{"$ref": "路徑"}——換成那份 JSON 檔裡那個位置的值，取回來的值接著解。$ref 也可以是這種字串的陣列（10-23 使用者）：每個元素各取一份、各自接著解，再照順序合成一份（merge）。
//
// 1. 寫法（ref_spot，「字串→位置」，只看字面；11-13 晚使用者「他應該是以#作爲json內部尋址的標示」，thinking 2026-11/13/ref-path-rules）：
//    # 左邊一律檔案系統（從 base.dir 算）、右邊一律 json 內部：#/＝本檔根、#./＝所在物件、#../＝上一層；#、#/＝整份。
//    寫法不合（#aaa、y.json#./、超出根…）＝DirectiveBad；$ref 不是字串、陣列空的或有一個元素不是字串、不知道檔或位置＝nullopt（原封不動，D15）。
//    Python 那份（py/aos/refpath.py，index 路徑也用）跑同一張表 py/tests/ref_path_cases.json。
// 2. 被 $ref 進來的檔＝它解開捷徑後所在的資料夾、位置＝取的那個指標
// 3. 同一個（檔＋指標）已經在鏈上＝繞圈
// 4. 讀檔（第一行 #! 跳過）、解 JSON（讀不到、不是 JSON＝錯）、照指標取值（指不到＝錯），推上鏈、接著往下解
// 5. 檔（解開捷徑後）以 .md 結尾＝不當 JSON 讀：照 md 的規則取值（md_get，src/md.cpp），整份＝原文（#! 不跳過）；取到的值不再往下解
// 錯一律 DirectiveBad。
#include "internal.hpp"

#include "util/files.hpp"

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
        throw Error{code::DirectiveBad, "$ref cannot read " + path};
    }
    std::string text(std::istreambuf_iterator<char>(f), {});
    if (text.starts_with("#!")) {
        size_t nl = text.find('\n');
        text = nl == std::string::npos ? "" : text.substr(nl + 1);
    }
    Json doc = Json::parse(text, nullptr, false);
    if (doc.is_discarded()) {
        throw Error{code::DirectiveBad, "$ref " + path + " is not JSON"};
    }
    return doc;
}

// 讀一份 md、照 md 的規則取 ptr 那一格（11-21 晚）：讀不到同 load、指不到同 pointer（後面括號接 md 那邊說的原因）。
static Json load_md(const std::string& path, const std::string& ptr) {
    struct stat st;
    bool is_dir = ::stat(path.c_str(), &st) == 0 && S_ISDIR(st.st_mode);
    std::ifstream f(path, std::ios::binary);
    if (!f || is_dir) {
        throw Error{code::DirectiveBad, "$ref cannot read " + path};
    }
    std::string text(std::istreambuf_iterator<char>(f), {});
    std::vector<std::string> toks;
    for (const std::string& raw : pointer_tokens(ptr)) {
        std::string tok;
        for (size_t k = 0; k < raw.size(); ++k) {
            if (raw[k] == '~' && k + 1 < raw.size() && (raw[k + 1] == '1' || raw[k + 1] == '0')) {
                tok += raw[k + 1] == '1' ? '/' : '~';
                ++k;
            } else {
                tok += raw[k];
            }
        }
        toks.push_back(tok);
    }
    try {
        return md_get(text, toks);
    } catch (const Error& e) {
        throw Error{code::DirectiveBad, "$ref pointer not found: " + path + "#" + ptr + " (" + e.msg + ")"};
    }
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
            throw Error{code::DirectiveBad, "$ref pointer not found: " + file + "#" + ptr};
        }
        i = next + 1;
    }
    return *cur;
}

}  // namespace aos::directive

namespace aos::directive {

RefBase base_of(const std::string& file, const std::string& ptr) {
    return RefBase{aos::dirname(file), file, pointer_tokens(ptr)};
}

std::optional<std::vector<Fetched>> fetch_ref(const Json& d, const RefBase& base, const Chain& chain) {
    // 1. 寫法：字串＝一份；陣列（10-23 使用者）＝每個元素一份，空陣列或有一個不合＝整個不合
    const Json& ref = d["$ref"];
    std::vector<RefSpot> specs;
    auto add = [&](const Json& r) {
        std::optional<RefSpot> one = r.is_string() ? ref_spot(r.get<std::string>(), base) : std::nullopt;
        if (one) {
            specs.push_back(*one);
        }
        return one.has_value();
    };
    if (ref.is_array()) {
        if (ref.empty()) {
            return std::nullopt;
        }
        for (const Json& r : ref) {
            if (!add(r)) {
                return std::nullopt;
            }
        }
    } else if (!add(ref)) {
        return std::nullopt;
    }

    std::vector<Fetched> out;
    for (const RefSpot& spot : specs) {
        // 2～3. 從這一層算、看繞圈（鏈＝往上那幾層；同一個陣列裡寫兩次同一份不算繞圈）
        std::string file = real_path(spot.file);
        const std::string& ptr = spot.pointer;
        std::pair<std::string, std::string> here{file, ptr};
        for (const auto& seen : chain) {
            if (seen == here) {
                std::string walked;
                for (const auto& s : chain) {
                    walked += s.first + (s.second.empty() ? "" : "#" + s.second) + " → ";
                }
                throw Error{code::DirectiveBad, "$ref loop: " + walked + file + (ptr.empty() ? "" : "#" + ptr)};
            }
        }
        // 4. 讀、取值（原文，還沒往下解）
        Fetched f;
        f.md = md_path(file);
        f.value = f.md ? load_md(file, ptr) : pointer(load(file), ptr, file);
        f.here = here;
        out.push_back(std::move(f));
    }
    return out;
}

std::optional<Json> resolve_ref(const Json& d, const RefBase& base, Chain& chain) {
    std::optional<std::vector<Fetched>> fs = fetch_ref(d, base, chain);
    if (!fs) {
        return std::nullopt;
    }
    // 每一份推上鏈、往下解（那份檔裡的 $ref 從它實際所在的資料夾、它在那份檔裡的位置算），再合成一份
    std::vector<Resolved> parts;
    for (Fetched& f : *fs) {
        chain.push_back(f.here);
        RefBase in = base_of(f.here.first, f.here.second);
        parts.push_back({f.md ? f.value : walk(f.value, in, chain), in, {}, {}});   // md 取到的值不再解指示詞
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
        throw Error{code::DirectiveBad, "$ref " + where + ": parts cannot be merged (must be all objects or all arrays)"};
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
