// ref.cpp：{"$ref": "檔[#/指標]"[, "at": 指標]}——換成那份 JSON 檔裡那個位置的值，取回來的值接著解。
// 對應 proto8/bin/aos_inst.py 的 _ref、_pointer、load。
//
// 1. 寫法：$ref 不是字串、空字串、只有 #/…（沒檔名）、# 後面不是 /＝回 nullopt（原封不動，D15）；
//    at 不是字串、或不是空字串也不是 / 開頭＝當沒寫（D14）；兩個都寫＝at 接在 #/ 後面（D7）
// 2. 相對檔名從這一層的 base 算（最外層＝呼叫者給的 base_dir；被 $ref 進來的檔＝它解開捷徑後所在的資料夾）
// 3. 同一個（檔＋指標）已經在鏈上＝繞圈
// 4. 讀檔（第一行 #! 跳過）、解 JSON（讀不到、不是 JSON＝錯）、照指標取值（指不到＝錯），推上鏈、接著往下解
// 錯一律 DirectiveBad。
#include "internal.hpp"

#include "aos/files.hpp"

#include <cstdlib>
#include <fstream>
#include <iterator>

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

std::optional<Json> resolve_ref(const Json& d, const std::string& base, Chain& chain) {
    // 1. 寫法
    const Json& ref = d["$ref"];
    if (!ref.is_string()) {
        return std::nullopt;
    }
    std::string at;
    if (d.contains("at") && d["at"].is_string()) {
        std::string a = d["at"].get<std::string>();
        if (a.empty() || a[0] == '/') {
            at = a;
        }
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
    ptr += at;

    // 2～3. 從這一層算、看繞圈
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

    // 4. 讀、取值、推上鏈、往下解（這份檔裡的 $ref 從它實際所在的資料夾算）
    Json v = pointer(load(file), ptr, file);
    chain.push_back(here);
    Json out = walk(v, aos::dirname(file), chain);
    chain.pop_back();
    return out;
}

}  // namespace aos::directive
