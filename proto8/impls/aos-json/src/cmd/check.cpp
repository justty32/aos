// check.cpp：【cmd】check [--env] 檔[#/指標]...——驗一份（或幾份）aos 的 JSON，有問題每個一行印在 stdout、退 10（11-05 D1；原退 1）；沒問題不印、退 0。
//
// 驗三件：
//   1. 每個 $ref 指得到（檔在、是 JSON、指標指得到、不繞圈；陣列的幾份合得起來）——被參照的檔也一路往下驗
//   2. 指示詞的寫法：帶 $ref／$env 但寫法不合（aos 會原封不動留著，多半是寫錯）＝DirectiveFormBad
//   3. exec 的形狀（只看 aos 設定檔裡的那幾格：最上層的 exec、states/<名>/exec、procs/<名>/exec（11-03 原 loops，統稱 procs）——位置照 $ref 合好之後算）：
//      非空字串、非空陣列（元素是字串或指示詞）、或單子物件（argv 是非空陣列、元素是字串或指示詞；argv 本身是指示詞也算）
// $env 現在沒設不算問題（AOS_* 是跑的時候才有）；加 --env 才報。
// 每行：`位置: 代號 原因`（位置＝檔#/指標，檔在 cwd 底下印相對路徑）。代號：DirectiveBad（同 aos 跑的時候的錯）、DirectiveFormBad、ExecBad。
#include "cmd/cmd.hpp"

#include "follow/follow.hpp"

#include "aos/cli.hpp"

#include <cstdlib>
#include <iostream>
#include <set>

namespace aos::json {

namespace {

struct Checker {
    Docs& docs;
    bool env = false;
    std::vector<std::string> problems;
    std::set<std::pair<std::string, std::string>> seen;   // 已經驗過的 $ref 目標（檔, 指標）

    void report(const Cursor& c, const std::string& code, const std::string& why) {
        problems.push_back(shown(c.file, c.toks) + ": " + code + " " + why);
    }

    static bool is_exec_place(const std::vector<std::string>& at) {
        if (at.size() == 1) {
            return at[0] == "exec";
        }
        return at.size() == 3 && at[2] == "exec" && (at[0] == "states" || at[0] == "procs");
    }

    static bool item_ok(const Json& x) {
        Kind k = kind_of(x);
        return (x.is_string()) || k == Kind::Ref || k == Kind::Env;
    }

    void check_exec(Cursor c, Chain chain) {
        try {
            c = settle(docs, c, chain);
        } catch (const Error&) {
            return;   // $ref 本身的錯 visit 會報
        }
        const Json& v = *c.node;
        Kind k = kind_of(v);
        if (k == Kind::Env) {
            return;
        }
        bool ok = false;
        std::string want = "must be a non-empty string, a non-empty array ([target, args...]) or an inst object";
        if (v.is_string()) {
            ok = !v.get<std::string>().empty();
        } else if (v.is_array()) {
            ok = !v.empty();
            for (const Json& x : v) {
                ok = ok && item_ok(x);
            }
        } else if (v.is_object() && k == Kind::Plain) {
            want = "is an inst: argv must be a non-empty array (of strings or directives)";
            if (v.contains("argv")) {
                const Json& a = v["argv"];
                Kind ak = kind_of(a);
                ok = ak == Kind::Ref || ak == Kind::Env || (a.is_array() && !a.empty());
                if (a.is_array()) {
                    for (const Json& x : a) {
                        ok = ok && item_ok(x);
                    }
                }
            }
        }
        if (!ok) {
            report(c, code::ExecBad, "exec " + want + ", got " + aos::dumps(v));
        }
    }

    // c＝這個值在哪；at＝合好之後的邏輯位置（判斷是不是 exec 那幾格用）。
    void visit(const Cursor& c, const std::vector<std::string>& at, Chain chain) {
        const Json& v = *c.node;
        Kind k = kind_of(v);
        if (k == Kind::FormBad) {
            report(c, code::DirectiveFormBad, "has $ref/$env but is malformed, aos will leave it as is: " + aos::dumps(v));
            return;
        }
        if (k == Kind::Env) {
            std::string name = v["$env"].get<std::string>();
            if (env && std::getenv(name.c_str()) == nullptr) {
                report(c, code::DirectiveBad, "environment variable " + name + " is not set");
            }
            return;
        }
        if (k == Kind::Ref) {
            auto parts = ref_parts(v);
            std::vector<std::string> kinds;
            for (const auto& [path, ptr] : parts) {
                Chain mine = chain;
                try {
                    Cursor x = fetch(docs, c.base, path, ptr, mine);
                    std::pair<std::string, std::string> here{x.file, ptr};
                    if (!seen.count(here)) {
                        seen.insert(here);
                        visit(x, at, mine);
                    }
                    if (parts.size() > 1) {
                        Cursor y = settle(docs, x, mine);
                        kinds.push_back(y.node->is_object() ? "object" : y.node->is_array() ? "array" : "other");
                    }
                } catch (const Error& e) {
                    report(c, e.code, e.msg);
                    return;
                }
            }
            for (const std::string& kd : kinds) {
                if (kd != kinds[0] || kd == "other") {
                    report(c, code::DirectiveBad, "$ref parts cannot be merged (must be all objects or all arrays)");
                    break;
                }
            }
            return;
        }
        if (!v.is_object() && !v.is_array()) {
            return;
        }
        for (auto& [key, x] : c.node->items()) {
            Cursor sub{c.file, c.base, c.toks, &x};
            sub.toks.push_back(key);
            std::vector<std::string> sub_at = at;
            sub_at.push_back(key);
            if (is_exec_place(sub_at)) {
                check_exec(sub, chain);
            }
            visit(sub, sub_at, chain);
        }
    }
};

}  // namespace

std::vector<std::string> problems_of(Docs& docs, const std::string& spec, bool env) {
    Checker ck{docs};
    ck.env = env;
    Located at = locate(docs, parse_spec(spec), Mode{});
    if (!at.rest.empty()) {
        throw Error{code::PointerMissing, "no such pointer: " + spec};
    }
    ck.visit(at.at, {}, {});
    return ck.problems;
}

int cmd_check(const Args& args) {
    Cli cli = parse_cli(args, {}, {{"--env", "env"}}, "usage: aos-json check [--env] FILE[#/POINTER]...\n\nCheck aos JSON files: one problem per line on stdout; exit 0 = no problem, 10 = problems found.\n");
    if (cli.rest.empty()) {
        throw usage_error(code::ArgumentsBad, "wrong number of arguments", "aos-json check [--env] FILE[#/POINTER]...");
    }
    Docs docs;
    std::vector<std::string> all;
    for (const std::string& s : cli.rest) {
        for (const std::string& p : problems_of(docs, s, cli.opts.count("env") > 0)) {
            all.push_back(p);
        }
    }
    for (const std::string& p : all) {
        std::cout << p << "\n";
    }
    std::cout << std::flush;
    return all.empty() ? 0 : 10;   // 11-05 stdio-unify R7／D1：有問題＝查完了、結果否定，退 10（stderr 空）
}

}  // namespace aos::json
