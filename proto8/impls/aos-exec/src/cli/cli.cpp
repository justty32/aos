// cli.cpp：【cli】run_cli（說明見 cli.hpp；10-21 ideas § 3、§ 4）。
#include "cli/cli.hpp"

#include "env/env.hpp"
#include "find/find.hpp"
#include "launch/launch.hpp"
#include "aos/cli.hpp"
#include "aos/files.hpp"

#include <cstdio>
#include <exception>
#include <filesystem>

namespace aos::exec {

static const char* USAGE = "aos-exec [--ws WS] [--stack S] [--dotenv-override] XXX [args...]";

static int fail(const std::string& code, const std::string& msg) {
    std::fprintf(stderr, "aos-exec: %s %s\n", code.c_str(), msg.c_str());
    std::fflush(stderr);
    return 1;
}

static int run(const std::vector<std::string>& argv) {
    try {
        Cli cli;
        try {
            // 以後加旗標就在這裡加一列；--dotenv-override（10-22）不帶值：.env 蓋掉已有的，只管這一次 aos-exec
            // --stack S（11-03）：stack 放哪，同 --ws（"-"／空＝沿用外面的）
            cli = parse_cli(argv, {{"--ws", "ws"}, {"--stack", "stack"}}, {{"--dotenv-override", "dotenv_override"}});
        } catch (const Error& e) {
            throw Error{e.code, std::string("usage: ") + USAGE + " (" + e.msg + ")"};   // FlagUnknown／ArgumentsBad
        }
        if (cli.rest.empty()) {
            throw Error{code::ArgumentsBad, std::string("usage: ") + USAGE + " (missing XXX)"};
        }
        std::string spec = cli.rest[0];
        if (spec.empty()) {   // "" 不當成 .：`aos-exec "$X"` 的 X 沒設時不該默默跑 cwd 的入口
            throw Error{code::ArgumentsBad, std::string("usage: ") + USAGE + " (XXX is an empty string)"};
        }
        std::vector<std::string> args(cli.rest.begin() + 1, cli.rest.end());
        std::string ws = "-";
        if (cli.opts.count("ws") > 0) {
            ws = cli.opts["ws"];
        }
        std::string stack = "-";
        if (cli.opts.count("stack") > 0) {
            stack = cli.opts["stack"];
        }
        bool dotenv_override = cli.opts.count("dotenv_override") > 0;
        std::string base = std::filesystem::current_path().string();
        Chain chain;
        while (true) {
            Found found = hop(spec, base, ws, stack, dotenv_override, chain);
            if (found.kind != Kind::Redirect) {
                return launch(found, args);
            }
            // 字串轉向＝交給下一層、全新的一次 aos-exec（C-52）：旗標不帶過去、args 原樣接過去，
            // 下一層自己定工作區、cd、讀它那裡的 .env（疊在這層設好的環境上）。繞圈偵測沿用同一條鏈。
            // --dotenv-override 也不帶過去（10-22 ideas § 3.2 第 4 點：字串轉向＝全新一跳、不吃旗標）。
            spec = found.doc.get<std::string>();
            base = dirname(found.file);
            ws = "-";
            stack = "-";   // --stack 也不帶過去（同 --ws）；這一層 export 的 AOS_STACK（已是絕對路徑）留在環境裡
            dotenv_override = false;
        }
    } catch (const Error& e) {
        return fail(e.code, e.msg);
    } catch (const std::exception& e) {
        return fail(code::Internal, e.what());
    }
}

// 11-05：沒用上的 stack 不留（在不是工作區的地方跑「把自己掛上 daemon」的 _entry 會留一個空 .stack）。
int run_cli(const std::vector<std::string>& argv) {
    int rc = run(argv);
    drop_stack_if_empty();
    return rc;
}

}  // namespace aos::exec
