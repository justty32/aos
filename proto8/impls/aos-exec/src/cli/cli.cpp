// cli.cpp：【cli】run_cli（說明見 cli.hpp；10-21 ideas § 3、§ 4）。
#include "cli/cli.hpp"

#include "env/env.hpp"
#include "find/find.hpp"
#include "launch/launch.hpp"
#include "aos/util/cli.hpp"
#include "aos/util/files.hpp"

#include <cstdio>
#include <exception>
#include <filesystem>

namespace aos::exec {

static const char* USAGE = "aos-exec [--ws WS] [--stack S] [--stack-lazy] [--dotenv-override] XXX [ARGS...]";

static const char* HELP = R"(usage: aos-exec [FLAGS] XXX [ARGS...]

Find the entry XXX (a file, a folder with _entry, or FILE#/POINTER), set up the
workspace (AOS_WS), stack (AOS_STACK), .env and cwd, then run it with ARGS.
The exit code is the entry's own code once it runs.

flags:
  -w, --ws WS              workspace to use ("-" or empty = keep the outer one)
  -s, --stack S            stack to use ("-" or empty = keep the outer one)
  --stack-lazy             do not create the stack folder (whoever writes there creates it)
  --dotenv-override        let .env override variables already set
  -h, --help               show this help

exit codes: the entry's code; 1 with "aos-exec: error: CODE ..." on stderr = aos-exec's own error.
)";

static int run(const std::vector<std::string>& argv) {
    try {
        Cli cli;
        try {
            // 以後加旗標就在這裡加一列；--dotenv-override（10-22）不帶值：.env 蓋掉已有的，只管這一次 aos-exec
            // --stack S（11-03）：stack 放哪，同 --ws（"-"／空＝沿用外面的）
            cli = parse_cli(argv, {{"--ws", "ws"}, {"--stack", "stack"}}, {{"--dotenv-override", "dotenv_override"}, {"--stack-lazy", "stack_lazy"}}, HELP, {"-w", "-s"});
        } catch (const Error& e) {
            throw usage_error(e.code, e.msg, USAGE);   // FlagUnknown／ArgumentsBad
        }
        if (cli.rest.empty()) {
            throw usage_error(code::ArgumentsBad, "missing XXX", USAGE);
        }
        std::string spec = cli.rest[0];
        if (spec.empty()) {   // "" 不當成 .：`aos-exec "$X"` 的 X 沒設時不該默默跑 cwd 的入口
            throw usage_error(code::ArgumentsBad, "XXX is an empty string", USAGE);
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
        // --stack-lazy（11-11 thinking tool-cells-lazy）：stack 只轉絕對、export，不建；aos-tools call 給工具的小格用。只管這一跳
        bool stack_lazy = cli.opts.count("stack_lazy") > 0;
        std::string base = std::filesystem::current_path().string();
        Chain chain;
        while (true) {
            Found found = hop(spec, base, ws, stack, dotenv_override, chain, stack_lazy);
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
            stack_lazy = false;
        }
    } catch (const Error& e) {
        return aos::fail("aos-exec", e);
    } catch (const std::exception& e) {
        return aos::fail("aos-exec", code::Internal, e.what());
    }
}

// 11-05：沒用上的 stack 不留（在不是工作區的地方跑「把自己掛上 daemon」的 _entry 會留一個空 .stack）。
int run_cli(const std::vector<std::string>& argv) {
    int rc = run(argv);
    drop_stack_if_empty();
    return rc;
}

}  // namespace aos::exec
