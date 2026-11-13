// ref.cpp：{"$ref": "路徑"}——換成那份 JSON 檔裡那個位置的值，取回來的值接著解。$ref 也可以是這種字串的陣列（10-23 使用者）：每個元素各取一份、各自接著解，再照順序合成一份（merge）。
//
// 1. 寫法（ref_spot，「字串→位置」，只看字面；11-13 晚使用者「他應該是以#作爲json內部尋址的標示」，thinking 2026-11/13/ref-path-rules）：
//    # 左邊一律檔案系統（從 base.dir 算）、右邊一律 json 內部：#/＝本檔根、#./＝所在物件、#../＝上一層；#、#/＝整份。
//    寫法不合（#aaa、y.json#./、超出根…）＝DirectiveBad；$ref 不是字串、陣列空的或有一個元素不是字串、不知道檔或位置＝nullopt（原封不動，D15）。
//    Python 那份（lib/aos_refpath.py，index 路徑也用）跑同一張表 lib/tests/ref_path_cases.json。
// 2. 被 $ref 進來的檔＝它解開捷徑後所在的資料夾、位置＝取的那個指標
// 3. 同一個（檔＋指標）已經在鏈上＝繞圈
// 4. 讀檔（第一行 #! 跳過）、解 JSON（讀不到、不是 JSON＝錯）、照指標取值（指不到＝錯），推上鏈、接著往下解
// 錯一律 DirectiveBad。
#include "internal.hpp"

#include "aos/util/files.hpp"

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

namespace aos {

// 「字串→位置」（說明見 aos/directive.hpp）。只看字面，不讀檔。
std::optional<RefSpot> ref_spot(const std::string& spec, const RefBase& base) {
    auto bad = [&](const std::string& why) -> std::optional<RefSpot> {
        throw Error{code::DirectiveBad, "$ref " + spec + ": " + why};
    };
    if (spec.empty()) {
        return bad("a path must be a non-empty string");
    }
    size_t hash = spec.find('#');
    std::string left = hash == std::string::npos ? spec : spec.substr(0, hash);
    std::string file;
    if (!left.empty()) {
        std::filesystem::path p = left.starts_with("/") ? std::filesystem::path(left) : std::filesystem::path(base.dir.empty() ? "." : base.dir) / left;
        file = p.lexically_normal().string();
        while (file.size() > 1 && file.ends_with("/")) {
            file.pop_back();
        }
    } else if (base.file.empty()) {
        return std::nullopt;   // `#…`＝寫著它的那份檔，但不知道是哪份
    } else {
        file = base.file;
    }
    if (hash == std::string::npos) {
        return RefSpot{file, ""};
    }
    std::string right = spec.substr(hash + 1);
    if (right.empty() || right == "/") {
        return RefSpot{file, ""};   // `#`、`#/`＝整份
    }
    if (right[0] == '/') {
        return RefSpot{file, right};   // RFC 6901，從根起算
    }
    if (right[0] != '.') {
        return bad("after # write /, ./ or ../ (e.g. #/key, #./key, #../key)");
    }
    if (!left.empty()) {
        return bad("#./ and #../ count from the object this $ref is written in, so they cannot follow a file name; write " + left + "#/POINTER");
    }
    std::vector<std::string> segs;
    for (size_t pos = 0;;) {
        size_t next = right.find('/', pos);
        segs.push_back(right.substr(pos, next == std::string::npos ? next : next - pos));
        if (next == std::string::npos) {
            break;
        }
        pos = next + 1;
    }
    size_t i = 0;
    size_t up = 0;
    while (i < segs.size() && (segs[i] == "." || segs[i] == "..")) {
        up += segs[i] == ".." ? 1 : 0;
        ++i;
    }
    if (i == 0) {
        return bad("after # write /, ./ or ../ (e.g. #/key, #./key, #../key)");
    }
    std::vector<std::string> rest(segs.begin() + static_cast<long>(i), segs.end());
    if (rest.size() == 1 && rest[0].empty()) {
        rest.clear();   // `#./`、`#../`＝那個物件整個
    }
    if (!base.placed) {
        return std::nullopt;   // 不知道這一格在檔裡哪裡
    }
    if (base.at.empty()) {
        return bad("the whole file is this $ref, so it sits in no object (#./ and #../ need one)");
    }
    std::vector<std::string> here(base.at.begin(), base.at.end() - 1);   // 所在物件＝這一格的上一層
    if (up > here.size()) {
        return bad("goes above the root of " + file);
    }
    here.resize(here.size() - up);
    std::string ptr;
    for (const std::string& t : here) {
        ptr += "/" + t;
    }
    for (const std::string& t : rest) {
        ptr += "/" + t;
    }
    return RefSpot{file, ptr};
}

std::vector<std::string> pointer_tokens(const std::string& ptr) {
    std::vector<std::string> toks;
    for (size_t pos = 0; pos < ptr.size();) {
        size_t next = ptr.find('/', pos + 1);
        toks.push_back(ptr.substr(pos + 1, next == std::string::npos ? next : next - pos - 1));
        pos = next;
    }
    return toks;
}

std::string token_of(const std::string& key) {
    std::string t;
    for (char c : key) {
        t += c == '~' ? "~0" : c == '/' ? "~1" : std::string(1, c);
    }
    return t;
}

RefBase RefBase::in(const std::string& key) const {
    RefBase b = *this;
    b.at.push_back(token_of(key));
    return b;
}

RefBase RefBase::in(size_t i) const {
    RefBase b = *this;
    b.at.push_back(std::to_string(i));
    return b;
}

}  // namespace aos

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
        f.value = pointer(load(file), ptr, file);
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
        parts.push_back({walk(f.value, in, chain), in, {}, {}});
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
