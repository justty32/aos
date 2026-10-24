// read.cpp：【cmd】讀——get（取值）、where（這個值實際寫在哪份檔的哪個位置）。
#include "cmd/cmd.hpp"

#include "follow/follow.hpp"

#include "aos/cli.hpp"

#include <cstdio>
#include <cstdlib>
#include <iostream>

namespace aos::json {

static std::string one_spec(const Args& args, const Cli& cli, const std::string& usage) {
    (void)args;
    if (cli.rest.size() != 1) {
        throw Error{code::ArgumentsBad, "用法：" + usage};
    }
    return cli.rest[0];
}

// get [--follow] [--resolve] [--str] 檔#/指標
//   沒旗標＝原文（指示詞原樣印出來）；--follow＝路上遇到 $ref 穿過去（aos 自己的程式不會這樣讀，給人看拆檔後的值）；
//   --resolve＝把拿到的值裡的指示詞解開（交給 aos-directive，跟 aos-loop、aos-fsm 讀設定檔同一套）；--str＝值是字串就印字面（不帶引號）。
int cmd_get(const Args& args) {
    Cli cli = parse_cli(args, {}, {{"--follow", "follow"}, {"--resolve", "resolve"}, {"--str", "str"}});
    std::string s = one_spec(args, cli, "aos-json get [--follow] [--resolve] [--str] 檔#/指標");
    Docs docs;
    Mode mode;
    mode.follow = cli.opts.count("follow") > 0;
    Located at = locate(docs, parse_spec(s), mode);
    if (!at.rest.empty()) {
        throw Error{code::PointerMissing, "指不到 " + s + "（" + shown(at.at.file, at.at.toks) + " 底下沒有 " +
                                              at.rest[0] + "）"};
    }
    Json v = *at.at.node;
    if (cli.opts.count("resolve")) {
        v = aos::resolve(v, at.at.base);
    }
    if (cli.opts.count("str")) {
        if (!v.is_string()) {
            throw Error{code::TargetBad, s + " 不是字串（是 " + std::string(v.type_name()) + "）"};
        }
        std::cout << v.get<std::string>() << "\n" << std::flush;
        return 0;
    }
    return aos::emit(v);
}

// where 檔#/指標：一路穿過 $ref，每一站印一行（`檔#/指標`；檔在 cwd 底下印相對路徑）；最後一站就是值實際寫的地方。
// 最後是 $env＝多印一行 `$env 名字`（值是跑的時候的環境變數，沒有檔）。
int cmd_where(const Args& args) {
    Cli cli = parse_cli(args, {}, {});
    std::string s = one_spec(args, cli, "aos-json where 檔#/指標");
    Docs docs;
    Mode mode;
    mode.follow = true;
    mode.follow_final = true;
    Located at = locate(docs, parse_spec(s), mode);
    if (!at.rest.empty()) {
        throw Error{code::PointerMissing, "指不到 " + s + "（" + shown(at.at.file, at.at.toks) + " 底下沒有 " +
                                              at.rest[0] + "）"};
    }
    std::string out;
    for (const Cursor& c : at.hops) {
        out += shown(c.file, c.toks) + "\n";
    }
    if (kind_of(*at.at.node) == Kind::Env) {
        out += "$env " + (*at.at.node)["$env"].get<std::string>() + "\n";
    }
    std::cout << out << std::flush;
    return 0;
}

}  // namespace aos::json
