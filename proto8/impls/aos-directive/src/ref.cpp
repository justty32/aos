// ref.cpp：{"$ref": "檔[#/指標]"}——換成那份 JSON 檔裡那個位置的值，取回來的值接著解。
// 可帶 "$at": "a/b"＝從 $ref 指到的地方接著往下走。$ref 也可以是這種字串的陣列（10-23 使用者）：每個元素各取一份、各自接著解，再照順序合成一份（merge）。
//
// 1. 寫法（ref_spot，「字串→位置」，只看字面）：$ref 不是字串、空字串、# 後面不是 /＝回 nullopt（原封不動，D15）；
//    陣列＝空的、或有一個元素這樣＝回 nullopt；$at（使用者 11-12「$at就變成$ref後面接着。$at仍不支援#」）＝從 $ref 指到的地方接著往下走（ref_step）；不是字串、裡面有 #＝回 nullopt。
//    #/…（沒檔名）＝寫著它的那份檔自己（使用者「ref應該支援#/開頭吧」）：那份檔＝base.file；不知道（空）＝回 nullopt。
//    # 後面的 `..`＝往外一層；根物件＝這份檔，再 `..`＝它所在的資料夾，之後照資料夾走、再遇到 # 又進那份檔
//    （使用者 11-12「可以用#/指代根obj，同時也算指代自身所在檔案，所以可以用#/key, #/../other.json。」）。
// 2. 相對檔名從這一層的 base 算（最外層＝呼叫者給的 base；被 $ref 進來的檔＝它解開捷徑後所在的資料夾）；./、../ 接上後整理
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
    if (spec.empty()) {
        return std::nullopt;
    }
    size_t hash = spec.find('#');
    if (hash == std::string::npos) {
        return RefSpot{aos::join(base.dir, spec), ""};
    }
    if (hash == 0 && base.file.empty()) {
        return std::nullopt;   // `#/…`＝寫著它的那份檔，但不知道是哪份
    }
    std::string file = hash == 0 ? base.file : aos::join(base.dir, spec.substr(0, hash));
    std::string rest = spec.substr(hash + 1);
    while (true) {
        // 在檔裡：rest 是 /tok/tok…；`..`＝往外一層，根物件（＝這份檔）再 `..`＝走出檔、到它所在的資料夾
        if (!rest.starts_with("/")) {
            return std::nullopt;
        }
        std::vector<std::string> toks;
        size_t pos = 1;
        bool left = false;
        while (true) {
            size_t next = rest.find('/', pos);
            std::string tok = rest.substr(pos, next == std::string::npos ? next : next - pos);
            if (tok != "..") {
                toks.push_back(tok);
            } else if (!toks.empty()) {
                toks.pop_back();
            } else {
                rest = next == std::string::npos ? "" : rest.substr(next + 1);
                left = true;
                break;
            }
            if (next == std::string::npos) {
                break;
            }
            pos = next + 1;
        }
        if (!left) {
            std::string ptr;
            for (const std::string& t : toks) {
                ptr += "/" + t;
            }
            return RefSpot{file, ptr};
        }
        // 在檔案系統：到下一個 # 之前是資料夾／檔名（./、../ 照資料夾走）；# 之後又進那份檔
        size_t h = rest.find('#');
        std::string walked = (std::filesystem::path(aos::dirname(file)) / ("./" + rest.substr(0, h))).lexically_normal().string();
        while (walked.size() > 1 && walked.ends_with("/")) {
            walked.pop_back();
        }
        file = walked;
        if (h == std::string::npos) {
            return RefSpot{file, ""};
        }
        rest = rest.substr(h + 1);
    }
}

// $at：從 $ref 指到的地方接著往下走（說明見 aos/directive.hpp）。
std::optional<RefSpot> ref_step(const RefSpot& from, const std::string& at) {
    if (at.find('#') != std::string::npos) {
        return std::nullopt;
    }
    std::vector<std::string> toks;   // from.pointer 的 token（跳脫後的樣子，照字面）
    for (size_t pos = 0; pos < from.pointer.size();) {
        size_t next = from.pointer.find('/', pos + 1);
        toks.push_back(from.pointer.substr(pos + 1, next == std::string::npos ? next : next - pos - 1));
        pos = next;
    }
    std::string file = from.file;
    bool inside = true;   // 還在檔裡；走出根物件之後是檔案系統
    for (size_t pos = 0; pos <= at.size();) {
        size_t next = at.find('/', pos);
        std::string seg = at.substr(pos, next == std::string::npos ? next : next - pos);
        pos = next == std::string::npos ? at.size() + 1 : next + 1;
        if (seg.empty() || seg == ".") {
            continue;
        }
        if (!inside) {
            file = (std::filesystem::path(file) / seg).lexically_normal().string();
        } else if (seg != "..") {
            toks.push_back(seg);
        } else if (!toks.empty()) {
            toks.pop_back();
        } else {
            file = std::filesystem::path(aos::dirname(file) + "/.").lexically_normal().string();
            inside = false;
        }
    }
    while (file.size() > 1 && file.ends_with("/")) {
        file.pop_back();
    }
    std::string ptr;
    for (const std::string& t : toks) {
        ptr += "/" + t;
    }
    return RefSpot{file, inside ? ptr : ""};
}

std::optional<std::string> ref_at_of(const Json& d) {
    if (!d.contains("$at") || d["$at"].is_null()) {
        return "";
    }
    if (!d["$at"].is_string() || d["$at"].get<std::string>().find('#') != std::string::npos) {
        return std::nullopt;
    }
    return d["$at"].get<std::string>();
}

}  // namespace aos

namespace aos::directive {

RefBase base_of(const std::string& file) {
    return RefBase{aos::dirname(file), file};
}

std::optional<std::vector<Fetched>> fetch_ref(const Json& d, const RefBase& base, const Chain& chain) {
    // 1. 寫法：字串＝一份；陣列（10-23 使用者）＝每個元素一份，空陣列或有一個不合＝整個不合
    const Json& ref = d["$ref"];
    std::vector<RefSpot> specs;
    std::optional<std::string> at = ref_at_of(d);   // $at 寫法不合（不是字串、有 #）＝整個物件不換
    if (!at) {
        return std::nullopt;
    }
    auto add = [&](const Json& r) {
        std::optional<RefSpot> one = r.is_string() ? ref_spot(r.get<std::string>(), base) : std::nullopt;
        if (one) {
            one = ref_step(*one, *at);   // 陣列＝每一份各自接著走
        }
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
    // 每一份推上鏈、往下解（那份檔裡的 $ref 從它實際所在的資料夾算），再合成一份
    std::vector<Resolved> parts;
    for (Fetched& f : *fs) {
        chain.push_back(f.here);
        parts.push_back({walk(f.value, base_of(f.here.first), chain), base_of(f.here.first), {}, {}});
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
