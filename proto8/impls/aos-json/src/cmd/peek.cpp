// peek.cpp：【cmd】peek [--follow] [--depth N] 檔#/指標——漸進展開：一次只看一層，大的值摺成一句摘要（省 token）。
//
// 使用者 10-24：「agent說想要看某些json，那就是給他json頂層，他說想看特定key，再逐一給他看細節。」
// 印法（純文字，一行一個 key）：
//   第一行：位置＋形狀（`fsm.json#/states {3}`）；穿過 $ref 展開的加「（$ref 展開）」
//   之後每個孩子一行 `key: 摘要`，深一層多兩格空白（--depth N＝往下展開 N 層，預設 1）
// 摘要：字串超過 80 位元組截到 60 加「…（共 N 位元組）」；數字、true／false／null 照寫；
//   物件 `{N} 前六個 key…`；陣列 `[N]`（全是短的純值就整個印出來）；指示詞 `$ref "…"`／`$env 名字 $path …`。
// 指到的是純值＝整個印出來（不截）。--follow＝路上與指到的 $ref 都穿過去（$ref 陣列照 aos-directive 合成一份給你看）。
#include "cmd/cmd.hpp"

#include "follow/follow.hpp"

#include "aos/cli.hpp"

#include <iostream>

namespace aos::json {

namespace {

const size_t LONG = 80;
const size_t CUT = 60;

std::string cut_utf8(const std::string& s, size_t n) {
    if (s.size() <= n) {
        return s;
    }
    while (n > 0 && ((unsigned char)s[n] & 0xC0) == 0x80) {
        n -= 1;
    }
    return s.substr(0, n);
}

std::string summary(const Json& v) {
    Kind k = kind_of(v);
    if (k == Kind::Ref) {
        return "$ref " + aos::dumps(v["$ref"]);
    }
    if (k == Kind::Env) {
        std::string s = "$env " + v["$env"].get<std::string>();
        for (const char* m : {"$path", "$prefix"}) {
            if (v.contains(m)) {
                s += std::string(" ") + m + " " + aos::dumps(v[m]);
            }
        }
        return s;
    }
    if (v.is_string()) {
        std::string s = v.get<std::string>();
        if (s.size() > LONG) {
            return aos::dumps(cut_utf8(s, CUT)) + "…（共 " + std::to_string(s.size()) + " 位元組）";
        }
        return aos::dumps(v);
    }
    if (v.is_object()) {
        std::string s = "{" + std::to_string(v.size()) + "}";
        size_t n = 0;
        for (auto it = v.begin(); it != v.end(); ++it) {
            if (n == 6) {
                s += "…";
                break;
            }
            s += (n == 0 ? " " : ", ") + it.key();
            n += 1;
        }
        return s;
    }
    if (v.is_array()) {
        bool flat = true;
        for (const Json& x : v) {
            flat = flat && !x.is_object() && !x.is_array();
        }
        std::string d = aos::dumps(v);
        if (flat && d.size() <= LONG) {
            return d;
        }
        return "[" + std::to_string(v.size()) + "]";
    }
    std::string d = aos::dumps(v);
    return d.size() > LONG ? cut_utf8(d, CUT) + "…" : d;
}

void lines(const Json& v, int depth, const std::string& pad, std::string& out) {
    if (depth <= 0 || kind_of(v) != Kind::Plain || !(v.is_object() || v.is_array())) {
        return;
    }
    size_t i = 0;
    for (auto it = v.begin(); it != v.end(); ++it, ++i) {
        std::string key = v.is_object() ? it.key() : std::to_string(i);
        std::string sum = summary(*it);
        out += pad + key + ": " + sum + "\n";
        if (sum != aos::dumps(*it)) {   // 整個已經印出來的（短陣列）不再拆
            lines(*it, depth - 1, pad + "  ", out);
        }
    }
}

}  // namespace

int cmd_peek(const Args& args) {
    Cli cli = parse_cli(args, {{"--depth", "depth"}}, {{"--follow", "follow"}});
    if (cli.rest.size() != 1) {
        throw Error{code::ArgumentsBad, "用法：aos-json peek [--follow] [--depth N] 檔#/指標"};
    }
    int depth = 1;
    if (cli.opts.count("depth")) {
        const std::string& d = cli.opts["depth"];
        if (d.empty() || d.size() > 3 || d.find_first_not_of("0123456789") != std::string::npos) {
            throw Error{code::ArgumentsBad, "--depth 要是 0～999 的整數"};
        }
        depth = std::stoi(d);
    }
    const std::string& s = cli.rest[0];
    Docs docs;
    Mode mode;
    mode.follow = cli.opts.count("follow") > 0;
    Located at = locate(docs, parse_spec(s), mode);
    if (!at.rest.empty()) {
        throw Error{code::PointerMissing, "指不到 " + s + "（" + shown(at.at.file, at.at.toks) + " 底下沒有 " +
                                              at.rest[0] + "）"};
    }
    Json v = *at.at.node;
    std::string note;
    if (mode.follow && kind_of(v) == Kind::Ref) {
        v = aos::resolve_shallow(v, at.at.base).value;
        note = "（$ref 展開）";
    }
    std::string out;
    if (kind_of(v) == Kind::Plain && !v.is_object() && !v.is_array()) {
        out = s + ": " + aos::dumps(v) + "\n";
    } else {
        out = s + " " + summary(v) + note + "\n";
        lines(v, depth, "  ", out);
    }
    std::cout << out << std::flush;
    return 0;
}

}  // namespace aos::json
