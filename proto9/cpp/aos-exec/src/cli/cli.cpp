// cli.cpp：【cli】run_cli（說明見 cli.hpp；10-21 ideas § 3、§ 4）。proto9: no --stack / --stack-lazy, no stack cleanup.
#include "cli/cli.hpp"

#include "env/env.hpp"
#include "find/find.hpp"
#include "launch/launch.hpp"
#include "util/cli.hpp"
#include "util/files.hpp"

#include <cstdio>
#include <exception>
#include <filesystem>

namespace aos::exec {

static const char* USAGE = "aos-exec [--ws WS] [--dotenv-override] XXX [ARGS...]";

static const char* HELP = R"(usage: aos-exec [FLAGS] XXX [ARGS...]

Find the entry XXX (a file, a folder with _entry, or FILE#/POINTER), set up the
workspace (AOS_WS), .env and cwd, then run it with ARGS. Entries are
executables and JSON argv arrays (inst sheets are not supported in proto9).
AOS_STACK is neither set nor created; an inherited one is passed through.
The exit code is the entry's own code once it runs.

flags:
  -w, --ws WS              workspace to use ("-" or empty = keep the outer one)
  --dotenv-override        let .env override variables already set
  -h, --help               show this help

exit codes: the entry's code; 1 with "aos-exec: error: CODE ..." on stderr = aos-exec's own error.
)";

static int run(const std::vector<std::string>& argv) {
    try {
        Cli cli;
        try {
            // 以後加旗標就在這裡加一列；--dotenv-override（10-22）不帶值：.env 蓋掉已有的，只管這一次 aos-exec
            // proto9: --stack、--stack-lazy（與短名 -s）拿掉了，給了＝FlagUnknown（原因多一句 proto9 沒有 AOS_STACK）
            cli = parse_cli(argv, {{"--ws", "ws"}}, {{"--dotenv-override", "dotenv_override"}}, HELP, {"-w"}, {}, 1);   // XXX 起原樣交給它（P-44 續）
        } catch (const Error& e) {
            std::string msg = e.msg;
            if (msg == "unknown flag --stack" || msg == "unknown flag --stack-lazy" || msg == "unknown flag -s") {
                msg += " (proto9 has no AOS_STACK)";
            }
            throw usage_error(e.code, msg, USAGE);   // FlagUnknown／ArgumentsBad
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
        bool dotenv_override = cli.opts.count("dotenv_override") > 0;
        std::string base = std::filesystem::current_path().string();
        Chain chain;
        while (true) {
            Found found = hop(spec, base, ws, dotenv_override, chain);
            if (found.kind != Kind::Redirect) {
                return launch(found, args);
            }
            // 字串轉向＝交給下一層、全新的一次 aos-exec（C-52）：旗標不帶過去、args 原樣接過去，
            // 下一層自己定工作區、cd、讀它那裡的 .env（疊在這層設好的環境上）。繞圈偵測沿用同一條鏈。
            // --dotenv-override 也不帶過去（10-22 ideas § 3.2 第 4 點：字串轉向＝全新一跳、不吃旗標）。
            spec = found.doc.get<std::string>();
            base = dirname(found.file);
            ws = "-";
            dotenv_override = false;
        }
    } catch (const Error& e) {
        return aos::fail("aos-exec", e);
    } catch (const std::exception& e) {
        return aos::fail("aos-exec", code::Internal, e.what());
    }
}

int run_cli(const std::vector<std::string>& argv) {
    return run(argv);
}

}  // namespace aos::exec
