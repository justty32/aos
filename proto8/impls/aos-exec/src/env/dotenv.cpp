// dotenv.cpp：【env】`.env`（10-21 ideas § 4、§ 6、§ 7；N-59 第 4 件）。說明見 env.hpp。
// 對應 proto8/bin/aos-exec 的 set_env、load_env、json_env。
//
// 一行 `名字=值`：去前導空白、去行尾 \r 後，空的或 # 開頭跳過；= 只切第一個；名字＝英數字和底線、不以數字開頭；
// 值照字面、只展開 ${名字}（逐行，後面看得到前面設的；沒設＝錯），孤零零的 $ 原樣留。不支援引號、export。
// 錯只印檔名和行號（JSON 的 .env key：只印位置），絕不印值。
#include "env/env.hpp"

#include "aos/directive.hpp"
#include "aos/files.hpp"

#include <cerrno>
#include <cstdlib>
#include <cstring>
#include <vector>

#include <sys/stat.h>

namespace aos::exec {

namespace {

bool name_start(char c) {
    return (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || c == '_';
}

bool name_char(char c) {
    return name_start(c) || (c >= '0' && c <= '9');
}

bool good_name(const std::string& s) {
    if (s.empty() || !name_start(s[0])) {
        return false;
    }
    for (char c : s) {
        if (!name_char(c)) {
            return false;
        }
    }
    return true;
}

// 嚴格的 UTF-8 檢查（同 Python 的 utf-8 解碼：不收過長編碼、代理區、超過 U+10FFFF）。
bool is_utf8(const std::string& s) {
    size_t i = 0;
    while (i < s.size()) {
        unsigned char c = (unsigned char)s[i];
        size_t n = 0;
        unsigned int cp = 0;
        if (c < 0x80) {
            i += 1;
            continue;
        } else if (c >= 0xC2 && c <= 0xDF) {
            n = 1;
            cp = c & 0x1F;
        } else if (c >= 0xE0 && c <= 0xEF) {
            n = 2;
            cp = c & 0x0F;
        } else if (c >= 0xF0 && c <= 0xF4) {
            n = 3;
            cp = c & 0x07;
        } else {
            return false;
        }
        for (size_t k = 1; k <= n; ++k) {
            if (i + k >= s.size()) {
                return false;
            }
            unsigned char d = (unsigned char)s[i + k];
            if ((d & 0xC0) != 0x80) {
                return false;
            }
            cp = (cp << 6) | (d & 0x3F);
        }
        if ((n == 2 && cp < 0x800) || (n == 3 && cp < 0x10000) || cp > 0x10FFFF || (cp >= 0xD800 && cp <= 0xDFFF)) {
            return false;
        }
        i += n + 1;
    }
    return true;
}

// 一個 `名字=值` 套進環境。錯丟 EnvBad（bad_prefix＋（原因））。
void set_env(const std::string& name, const std::string& val, const std::string& bad_prefix) {
    if (!good_name(name)) {
        throw Error{code::EnvBad, bad_prefix + "（名字要是英數字和底線、不以數字開頭）"};
    }
    std::string out;
    size_t i = 0;
    while (true) {
        size_t j = val.find("${", i);
        if (j == std::string::npos) {
            out += val.substr(i);
            break;
        }
        size_t k = j + 2;
        size_t end = k;
        while (end < val.size() && name_char(val[end])) {
            end += 1;
        }
        if (end == k || !name_start(val[k]) || end >= val.size() || val[end] != '}') {
            throw Error{code::EnvBad, bad_prefix + "（${ 後面要接 名字}）"};
        }
        std::string ref = val.substr(k, end - k);
        const char* v = std::getenv(ref.c_str());
        if (v == nullptr) {
            throw Error{code::EnvBad, bad_prefix + "（${…} 引用的環境變數沒設）"};
        }
        out += val.substr(i, j - i);
        out += v;
        i = end + 1;
    }
    if (out.find('\0') != std::string::npos) {
        throw Error{code::EnvBad, bad_prefix + "（值不能有 NUL）"};
    }
    setenv(name.c_str(), out.c_str(), 1);
}

}  // namespace

std::set<std::string> load_env(const std::string& dir) {
    std::set<std::string> names;
    std::string p = join(dir, ".env");
    struct stat st;
    if (lstat(p.c_str(), &st) != 0) {
        return names;
    }
    int err = 0;
    std::optional<std::string> text = read_file(p, err);
    if (!text) {
        throw Error{code::EnvReadFailed, ".env 讀不到：" + p + "（" + std::strerror(err) + "）"};
    }
    if (!is_utf8(*text)) {
        throw Error{code::EnvBad, ".env 壞：" + p + " 不是 UTF-8"};
    }
    size_t start = 0;
    int n = 0;
    while (start <= text->size()) {
        size_t nl = text->find('\n', start);
        if (nl == std::string::npos) {
            nl = text->size();
        }
        std::string line = text->substr(start, nl - start);
        start = nl + 1;
        n += 1;
        size_t lead = line.find_first_not_of(" \t\r\n\v\f");
        if (lead == std::string::npos) {
            line.clear();
        } else {
            line = line.substr(lead);
        }
        if (line.ends_with('\r')) {
            line.pop_back();
        }
        if (line.empty() || line[0] == '#') {
            continue;
        }
        std::string bad = ".env 壞：" + p + " 第 " + std::to_string(n) + " 行";
        size_t eq = line.find('=');
        if (eq == std::string::npos) {
            throw Error{code::EnvBad, bad + "（沒有 =）"};
        }
        std::string name = line.substr(0, eq);
        set_env(name, line.substr(eq + 1), bad);
        names.insert(name);
    }
    return names;
}

std::set<std::string> json_env(const Json& env, const std::string& where, const std::string& ref_base) {
    std::string bad = ".env 壞：" + where + " 的 .env";
    Json v;
    try {
        v = aos::resolve(env, ref_base);
    } catch (const Error&) {
        throw Error{code::EnvBad, bad + "（指示詞解不開）"};
    }
    std::set<std::string> names;
    if (!v.is_object()) {
        return names;
    }
    for (auto& [name, val] : v.items()) {
        if (!val.is_string()) {
            continue;
        }
        set_env(name, val.get<std::string>(), bad);
        names.insert(name);
    }
    return names;
}

}  // namespace aos::exec
