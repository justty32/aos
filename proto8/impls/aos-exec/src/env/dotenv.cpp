// dotenv.cpp：【env】`.env`（10-21 ideas § 4、§ 6、§ 7；10-22 ideas § 3；N-59 第 4 件）。說明見 env.hpp。
// 對應 proto8/bin/aos-exec 的 set_env、env_value、load_env、json_env。
//
// 一行 `[export ]名字=值`（10-22 起 dotenv 基礎子集）：去前導空白（只認 ASCII 空白）、去行尾 \r 後，空的或 # 開頭跳過；
// 行首 `export ` 忽略；= 只切第一個、兩邊空白忽略；值見 env_value（引號只剝一對、空白＋# 起是註解、去頭尾空白；
// 值的空白照 python-dotenv 認 Unicode 空白，同 Python str.isspace）；只展開 ${名字}（逐行，後面看得到前面設的；沒設＝錯），
// 孤零零的 $ 原樣留；單引號照字面。預設不蓋：開始讀一份 .env 那一刻環境裡已有的名字＝驗過、不設（override＝蓋）。
// 錯只印檔名和行號（JSON 的 .env key：只印位置），絕不印值。
#include "env/env.hpp"

#include "aos/directive.hpp"
#include "aos/files.hpp"
#include "aos/text.hpp"

#include <cerrno>
#include <cstdlib>
#include <cstring>
#include <vector>

#include <unistd.h>

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

// 一個 `名字=值` 套進環境。expand＝展開 ${名字}。錯丟 EnvBad（bad_prefix＋（原因））。
// 名字在 keep 裡（不蓋時＝開始讀這份 .env 那一刻環境裡已有的名字，10-22）＝驗過、不設，回 false；設了回 true。
bool set_env(const std::string& name, const std::string& val, const std::string& bad_prefix,
             const std::set<std::string>& keep, bool expand) {
    if (!good_name(name)) {
        throw Error{code::EnvBad, bad_prefix + "（名字要是英數字和底線、不以數字開頭）"};
    }
    std::string out;
    size_t i = 0;
    while (true) {
        size_t j = std::string::npos;
        if (expand) {
            j = val.find("${", i);
        }
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
    if (keep.count(name) > 0) {
        return false;
    }
    setenv(name.c_str(), out.c_str(), 1);
    return true;
}

// 環境裡現在有的名字（不蓋時要留的）。
std::set<std::string> env_names() {
    std::set<std::string> out;
    for (char** e = environ; *e != nullptr; ++e) {
        std::string kv = *e;
        out.insert(kv.substr(0, kv.find('=')));
    }
    return out;
}

// 行首的 `export ` 前綴（10-22 B1）：export 後接一個以上的空格／tab，再接不是 = 也不是空白的字（同 bin 的
// `export[ \t]+(?=[^=\s])`）。是＝回前綴長度、不是＝0（`export=1`、`export =1` 是名字 export）。
size_t export_prefix(const std::string& line) {
    if (!line.starts_with("export")) {
        return 0;
    }
    size_t i = 6;
    while (i < line.size() && (line[i] == ' ' || line[i] == '\t')) {
        i += 1;
    }
    if (i == 6 || i >= line.size() || line[i] == '=' || aos::space_at(line, i) > 0) {
        return 0;
    }
    return i;
}

// `=` 後面那段 → 值；expand 回要不要展開 ${}。基礎子集（10-22 ideas § 3.2 第 5 點）：收下的寫法給的值同 python-dotenv，
// 各家給的值不一樣的寫法＝錯。引號只剝一對：不跳脫、不跨行；單引號照字面，雙引號展開 ${}；引號後只能接空白或 # 註解。
// 沒引號：第一個「空白＋#」起是註解，a#b、#fff 照字面（同 python-dotenv）；去頭尾空白。
std::string env_value(const std::string& rest, const std::string& bad, bool& expand) {
    std::string v = aos::lstrip(rest);
    expand = true;
    if (!v.empty() && (v[0] == '\'' || v[0] == '"')) {
        char q = v[0];
        size_t j = v.find(q, 1);
        if (j == std::string::npos) {
            throw Error{code::EnvBad, bad + "（引號沒收尾（不支援多行））"};
        }
        std::string inner = v.substr(1, j - 1);
        std::string tail = aos::lstrip(v.substr(j + 1));
        if (inner.find('\\') != std::string::npos) {
            throw Error{code::EnvBad, bad + "（引號裡不能有 \\（不支援跳脫））"};
        }
        if (q == '\'' && inner.find("${") != std::string::npos) {
            throw Error{code::EnvBad, bad + "（單引號裡不能有 ${）"};
        }
        if (!tail.empty() && tail[0] != '#') {
            throw Error{code::EnvBad, bad + "（引號後面只能接空白或 # 註解）"};
        }
        expand = q == '"';
        return inner;
    }
    if (!v.empty() && v[0] == '#' && v != rest) {
        throw Error{code::EnvBad, bad + "（= 後面空白再接 #（要空值寫 X=，要 # 開頭的值加引號））"};
    }
    size_t i = 0;
    while (i < v.size()) {
        size_t n = aos::space_at(v, i);
        if (n > 0 && i + n < v.size() && v[i + n] == '#') {
            v = v.substr(0, i);
            break;
        }
        if (n > 0) {
            i += n;
        } else {
            i += 1;
        }
    }
    return aos::rstrip(v);
}

}  // namespace

std::set<std::string> load_env(const std::string& dir, bool override) {
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
    if (!aos::is_utf8(*text)) {
        throw Error{code::EnvBad, ".env 壞：" + p + " 不是 UTF-8"};
    }
    std::set<std::string> keep;
    if (!override) {
        keep = env_names();
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
        line = line.substr(export_prefix(line));
        size_t eq = line.find('=');
        if (eq == std::string::npos) {
            throw Error{code::EnvBad, bad + "（沒有 =）"};
        }
        std::string name = line.substr(0, eq);
        size_t name_end = name.find_last_not_of(" \t");   // 名字後面的空白只認空格／tab（同 bin 的 rstrip(" \t")）
        if (name_end == std::string::npos) {
            name.clear();
        } else {
            name.resize(name_end + 1);
        }
        bool expand = true;
        std::string val = env_value(line.substr(eq + 1), bad, expand);
        if (set_env(name, val, bad, keep, expand)) {
            names.insert(name);
        }
    }
    return names;
}

std::set<std::string> json_env(const Json& env, const std::string& where, const std::string& ref_base,
                               bool override) {
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
    std::set<std::string> keep;
    if (!override) {
        keep = env_names();
    }
    for (auto& [name, val] : v.items()) {
        if (!val.is_string()) {
            continue;
        }
        if (set_env(name, val.get<std::string>(), bad, keep, true)) {
            names.insert(name);
        }
    }
    return names;
}

}  // namespace aos::exec
