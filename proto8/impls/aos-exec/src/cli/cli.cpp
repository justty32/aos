// cli.cpp：【cli】run_cli（說明見 cli.hpp；10-21 ideas § 3、§ 4）。
#include "cli/cli.hpp"

#include "find/find.hpp"
#include "launch/launch.hpp"
#include "aos/cli.hpp"
#include "aos/files.hpp"

#include <cstdio>
#include <exception>
#include <filesystem>

namespace aos::exec {

static const char* USAGE = "aos-exec [--ws WS] [--dotenv-override] XXX [args...]";

static int fail(const std::string& code, const std::string& msg) {
    std::fprintf(stderr, "aos-exec: %s %s\n", code.c_str(), msg.c_str());
    std::fflush(stderr);
    return 1;
}

int run_cli(const std::vector<std::string>& argv) {
    try {
        Cli cli;
        try {
            // 以後加旗標就在這裡加一列；--dotenv-override（10-22）不帶值：.env 蓋掉已有的，只管這一次 aos-exec
            cli = parse_cli(argv, {{"--ws", "ws"}}, {{"--dotenv-override", "dotenv_override"}});
        } catch (const Error& e) {
            throw Error{code::Usage, std::string("usage: ") + USAGE + "（" + e.msg + "）"};
        }
        if (cli.rest.empty()) {
            throw Error{code::Usage, std::string("usage: ") + USAGE + "（沒有 XXX）"};
        }
        std::string spec = cli.rest[0];
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
        return fail(e.code, e.msg);
    } catch (const std::exception& e) {
        return fail(code::Internal, e.what());
    }
}

}  // namespace aos::exec
