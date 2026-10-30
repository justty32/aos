// main.cpp：aos-llm-kernel 命令列——LLM kernel 跑一次：從信箱挑最該跑的信、跑、回信（給 aos-loop／aos-daemon 一次次拍）。
//
//     aos-llm-kernel [旗標] kernel.json
//
//   block_signals → 命令列（目前沒有旗標；唯一的位置參數＝設定檔，可寫 `檔#/指標`）→ 要 AOS_STACK → read_cfg → serve
// 自己出錯：stderr 一行「aos-llm-kernel: 代號 原因」、退 1（N-60）。一封信的錯不是 kernel 的錯：寫進那封信的回信。
#include "serve/serve.hpp"

#include "aos/cli.hpp"

#include <cstdio>
#include <cstdlib>
#include <exception>

static const char* USAGE = "usage: aos-llm-kernel [旗標] kernel.json";

static int fail(const std::string& code, const std::string& msg) {
    std::fprintf(stderr, "aos-llm-kernel: %s %s\n", code.c_str(), msg.c_str());
    std::fflush(stderr);
    return 1;
}

int main(int argc, char** argv) {
    namespace k = aos::llm_kernel;
    try {
        aos::loop::block_signals();
        aos::Cli cli;
        try {
            cli = aos::parse_cli(std::vector<std::string>(argv + 1, argv + argc), {});   // 目前沒有旗標
        } catch (const aos::Error& e) {
            throw aos::Error{e.code, std::string(USAGE) + "（" + e.msg + "）"};
        }
        if (cli.rest.size() != 1) {
            std::string why = "沒有設定檔";
            if (!cli.rest.empty()) {
                why = "設定檔只能一個，多給了 " + cli.rest[1];
            }
            throw aos::Error{k::code::ArgumentsBad, std::string(USAGE) + "（" + why + "）"};
        }
        const char* s = std::getenv("AOS_STACK");
        if (s == nullptr || s[0] == '\0') {
            throw aos::Error{k::code::StackMissing, "沒設定 AOS_STACK"};
        }
        k::Cfg cfg = k::read_cfg(cli.rest[0], s);
        return k::serve(cfg, s);
    } catch (const aos::Error& e) {
        return fail(e.code, e.msg);
    } catch (const std::exception& e) {
        return fail(k::code::Internal, e.what());
    }
}
