// list.cpp：【cmd】ls（列一格底下的孩子，--long 附型別與大小）、search（找 key／value，往下或往上）——json 工具 json_ls／json_search 搬下來（11-12）。
//
// 輸出照 lib/aos_json.py 的 do_ls／do_search（給腦看的文字，一行一項、欄位 TAB）：
//   型別名同 JSON（object、array、string、number、boolean、null）；大小＝物件 N keys、陣列 N items、字串 N chars（code point 數），
//   單數不加 s，純值直接是緊湊 JSON；--long／search 的容器與字串再多一欄 `N bytes`（緊湊 JSON 的 UTF-8 bytes）。
//   沒列完最後一行 `[more] A to B of N shown; …`；search 沒中＝`[no match]`（都退 0：是結果不是錯）。
#include "cmd/cmd.hpp"

#include "help/help.hpp"

#include <iostream>
#include <limits>

namespace aos::json {

namespace {

std::string compact(const Json& v) {
    return v.dump(-1, ' ', false, Json::error_handler_t::replace);
}

size_t chars(const std::string& s) {
    size_t n = 0;
    for (char c : s) {
        n += ((unsigned char)c & 0xC0) != 0x80;
    }
    return n;
}

bool sized(const Json& v) {
    return v.is_object() || v.is_array() || v.is_string();
}

std::string size_of(const Json& v) {
    if (!sized(v)) {
        return compact(v);
    }
    size_t n = v.is_string() ? chars(v.get<std::string>()) : v.size();
    std::string unit = v.is_object() ? "key" : v.is_array() ? "item" : "char";
    return std::to_string(n) + " " + unit + (n == 1 ? "" : "s");
}

// --long／search 的欄：型別 TAB 大小（容器與字串再多 bytes）。
std::string columns(const Json& v) {
    std::string out = std::string(v.type_name()) + "\t" + size_of(v);
    if (sized(v)) {
        out += "\t" + std::to_string(compact(v).size()) + " bytes";
    }
    return out;
}

std::string esc(const std::string& key) {
    return pointer_of({key}).substr(1);
}

// 非負整數（不給＝dflt）；不是＝ArgumentsBad。
size_t count_opt(const Cli& cli, const std::string& name, size_t dflt, bool positive) {
    auto it = cli.opts.find(name);
    if (it == cli.opts.end()) {
        return dflt;
    }
    const std::string& t = it->second;
    bool digits = !t.empty() && t.size() <= 18 && t.find_first_not_of("0123456789") == std::string::npos;
    if (!digits || (positive && std::stoull(t) == 0)) {
        throw Error{code::ArgumentsBad, "--" + name + " must be a " + (positive ? "positive" : "non-negative") + " integer"};
    }
    return std::stoull(t);
}

// 印 rows[offset, offset+cap)；沒列完多一行 [more]。
void page(const std::vector<std::string>& rows, size_t offset, size_t cap, const std::string& hint) {
    std::string out;
    size_t end = offset + std::min(cap, rows.size());
    for (size_t i = offset; i < rows.size() && i < end; ++i) {
        out += rows[i] + "\n";
    }
    if (end < rows.size()) {
        out += "[more] " + std::to_string(offset) + " to " + std::to_string(end - 1) + " of " + std::to_string(rows.size()) +
               " shown; " + (hint.empty() ? "next: --offset " + std::to_string(end) : hint) + "\n";
    }
    std::cout << out << std::flush;
}

std::string one_spec(const Cli& cli, const std::string& command) {
    if (cli.rest.size() != 1) {
        throw usage_error(code::ArgumentsBad, "expects one FILE#/POINTER", cli_usage(command));
    }
    return cli.rest[0];
}

// 同 Python 的 same：JSON 相等、型別要一樣（1 不等於 "1"、true 不等於 1；1 等於 1.0）；物件不看 key 的順序。
bool same(const Json& a, const Json& b) {
    if (std::string(a.type_name()) != b.type_name()) {
        return false;
    }
    if (a.is_array()) {
        if (a.size() != b.size()) {
            return false;
        }
        for (size_t i = 0; i < a.size(); ++i) {
            if (!same(a[i], b[i])) {
                return false;
            }
        }
        return true;
    }
    if (a.is_object()) {
        if (a.size() != b.size()) {
            return false;
        }
        for (auto it = a.begin(); it != a.end(); ++it) {
            auto o = b.find(it.key());
            if (o == b.end() || !same(*it, *o)) {
                return false;
            }
        }
        return true;
    }
    return a == b;
}

struct Query {
    const std::string* key = nullptr;   // nullptr＝沒給
    const Json* want = nullptr;
    bool contains = false;

    bool hit(const std::string* k, const Json& x) const {
        if (key != nullptr && (k == nullptr || (contains ? k->find(*key) == std::string::npos : *k != *key))) {
            return false;
        }
        if (want != nullptr) {
            if (contains && want->is_string()) {
                return x.is_string() && x.get<std::string>().find(want->get<std::string>()) != std::string::npos;
            }
            return same(*want, x);
        }
        return true;
    }
};

// node 的每個成員：（key〔陣列元素＝nullptr〕、值、指標）。
template <typename F>
void members(const Json& node, const std::string& ptr, F f) {
    if (node.is_object()) {
        for (auto it = node.begin(); it != node.end(); ++it) {
            f(&it.key(), *it, ptr + "/" + esc(it.key()));
        }
    } else if (node.is_array()) {
        for (size_t i = 0; i < node.size(); ++i) {
            f(nullptr, node[i], ptr + "/" + std::to_string(i));
        }
    }
}

void down(const Query& q, const Json& node, const std::string& ptr, std::vector<std::pair<std::string, const Json*>>& found) {
    members(node, ptr, [&](const std::string* k, const Json& x, const std::string& p) {
        if (q.hit(k, x)) {
            found.push_back({p, &x});
        }
        down(q, x, p, found);
    });
}

}  // namespace

// ls [--follow] [--resolve] [--long] [--offset N] [--limit N] 檔#/指標：第一行這一格的型別與長度，之後一行一個孩子（可直接接在指標後面的寫法）。
int cmd_ls(const Args& args) {
    Cli cli = parse_args(args, {{"--offset", "offset"}, {"--limit", "limit"}},
                         {{"--follow", "follow"}, {"--resolve", "resolve"}, {"--long", "long"}}, "ls");
    std::string s = one_spec(cli, "ls");
    size_t offset = count_opt(cli, "offset", 0, false);
    size_t cap = count_opt(cli, "limit", std::numeric_limits<size_t>::max() / 2, true);
    Json v = get_value(s, cli.opts.count("follow") > 0, cli.opts.count("resolve") > 0);
    std::string head = std::string(v.type_name()) + (sized(v) ? ", " : " ") + size_of(v);
    if (v.is_array() && !v.empty()) {
        head += " (index 0.." + std::to_string(v.size() - 1) + ")";
    }
    std::cout << head << "\n";
    std::vector<std::string> rows;
    bool lng = cli.opts.count("long") > 0;
    members(v, "", [&](const std::string* k, const Json& x, const std::string& p) {
        rows.push_back(p.substr(1) + (lng ? "\t" + columns(x) : ""));
        (void)k;
    });
    page(rows, offset, cap, "");
    return 0;
}

// search [--follow] [--resolve] [--key K] [--value JSON] [--contains] [--up] [--limit N] 檔#/指標：
//   往下＝那一格以下每個物件成員與陣列元素（前序、照檔裡順序）；--up＝從父層一路到根、每層只看自己的成員、近的先。
//   一行一筆 `檔#/指標 TAB 型別 TAB 大小…`（檔照給的字面）。--follow／--resolve＝從穿過／解開後那格往下找，不配 --up。
int cmd_search(const Args& args) {
    Cli cli = parse_args(args, {{"--key", "key"}, {"--value", "value"}, {"--limit", "limit"}},
                         {{"--follow", "follow"}, {"--resolve", "resolve"}, {"--contains", "contains"}, {"--up", "up"}}, "search");
    std::string s = one_spec(cli, "search");
    Query q;
    q.contains = cli.opts.count("contains") > 0;
    if (!cli.opts.count("key") && !cli.opts.count("value")) {
        throw Error{code::ArgumentsBad, "give --key, --value, or both"};
    }
    bool follow = cli.opts.count("follow") > 0;
    bool resolve = cli.opts.count("resolve") > 0;
    bool up = cli.opts.count("up") > 0;
    if (up && (follow || resolve)) {
        throw Error{code::ArgumentsBad, "--up does not work with --follow or --resolve"};
    }
    size_t cap = count_opt(cli, "limit", std::numeric_limits<size_t>::max() / 2, true);
    if (cli.opts.count("key")) {
        q.key = &cli.opts.at("key");
    }
    Json want;
    if (cli.opts.count("value")) {
        want = Json::parse(cli.opts.at("value"), nullptr, false);
        if (want.is_discarded()) {
            throw Error{code::ValueBad, "--value is not JSON (write a string as \"...\" with quotes): " + cli.opts.at("value")};
        }
        q.want = &want;
    }
    Spec spec = parse_spec(s);
    size_t hash = s.find('#');
    std::string ptr = hash == std::string::npos ? "" : s.substr(hash + 1);
    Json node = get_value(s, follow, resolve);   // 指不到照 get 報錯
    std::vector<std::pair<std::string, const Json*>> found;
    Json doc;   // --up：整份原文（found 指進這裡，要活到印完）
    if (up) {
        doc = get_value(spec.file, false, false);   // 原文照走（同 get 不加 --follow）
        std::vector<std::pair<const Json*, std::string>> chain{{&doc, ""}};
        for (const std::string& t : spec.toks) {
            const Json& n = *chain.back().first;
            chain.push_back({n.is_array() ? &n.at(std::stoull(t)) : &n.at(t), chain.back().second + "/" + esc(t)});
        }
        for (size_t i = chain.size() - 1; i-- > 0;) {
            members(*chain[i].first, chain[i].second, [&](const std::string* k, const Json& x, const std::string& p) {
                if (q.hit(k, x)) {
                    found.push_back({p, &x});
                }
            });
        }
    } else {
        down(q, node, ptr, found);
    }
    if (found.empty()) {
        std::cout << "[no match]\n" << std::flush;
        return 0;
    }
    std::vector<std::string> rows;
    for (const auto& [p, x] : found) {
        rows.push_back(spec.file + "#" + p + "\t" + columns(*x));
    }
    page(rows, 0, cap, "narrow the path or give a bigger --limit");
    return 0;
}

}  // namespace aos::json
