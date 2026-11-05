// main.cpp：aos-directive 命令列——讀一份 JSON、解開所有指示詞、印出來。
//
//     aos-directive < 設定.json
//
// stdin 一份 JSON（空的＝{}、多份＝InputExtra），以呼叫者的 cwd 為基準解開指示詞（見 aos/directive.hpp），
// stdout 印一行解好的 JSON、退出 0；出錯 stderr 印一行「aos-directive: 代號 原因」、退出 1（11-04 起照 CONVENTION P-44；
// 原本印 {"error": {"code", "msg"}}）。不收任何參數：命令列照 P-44 用 aos::parse_cli 解（旗標＝FlagUnknown、位置參數＝ArgumentsBad）。
#include "aos/cli.hpp"
#include "aos/directive.hpp"
#include "aos/io.hpp"

#include <cstdio>
#include <exception>
#include <filesystem>

static int fail(const aos::Error& e) {
    std::fprintf(stderr, "aos-directive: %s %s\n", e.code.c_str(), e.msg.c_str());
    std::fflush(stderr);
    return 1;
}

int main(int argc, char** argv) {
    try {
        aos::Cli cli;
        try {
            cli = aos::parse_cli(std::vector<std::string>(argv + 1, argv + argc), {});
        } catch (const aos::Error& e) {
            throw aos::Error{e.code, "usage: aos-directive < CONFIG.json (" + e.msg + ")"};
        }
        if (!cli.rest.empty()) {
            throw aos::Error{aos::code::ArgumentsBad,
                             "usage: aos-directive < CONFIG.json (takes no arguments, reads stdin; got extra " + cli.rest[0] + ")"};
        }
        aos::Json doc = aos::read_stdin();
        return aos::emit(aos::resolve(doc, std::filesystem::current_path()));
    } catch (const aos::Error& e) {
        return fail(e);
    } catch (const std::exception& e) {
        return fail(aos::Error{aos::code::Internal, e.what()});
    }
}
