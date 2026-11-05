// main.cpp：aos-llm-kernel 命令列——LLM kernel 跑一次：從信箱挑最該跑的信、跑、回信（多半是 daemon.json 的身體，給 daemon 一次次拍；要在 daemon 底下）。
//
//     aos-llm-kernel [旗標] kernel.json
//
//   block_signals → 命令列（目前沒有旗標；唯一的位置參數＝設定檔，可寫 `檔#/指標`）→ 要 AOS_STACK → read_cfg → serve
// 自己出錯：stderr 一行「aos-llm-kernel: error: 代號 原因」、退 1（11-05 stdio-unify R1）。`--help`＝英文說明印 stdout、退 0（R3）。一封信的錯不是 kernel 的錯：寫進那封信的回信。
#include "serve/serve.hpp"

#include "aos/cli.hpp"

#include <cstdio>
#include <cstdlib>
#include <exception>

static const char* USAGE = "aos-llm-kernel [FLAGS] kernel.json";

static const char* HELP = R"(usage: aos-llm-kernel [FLAGS] kernel.json

One round of the LLM kernel (usually the body of an aos-daemon; needs $AOS_STACK):
collect finished brain calls and reply to their letters, then pick the best waiting
request letters from the mailbox and ask the daemon to run them on an endpoint pack.
A bad letter is answered with an error reply; it is not the kernel's error.

flags:
  --help   show this help

exit codes: 0 ok; 1 own error ("aos-llm-kernel: error: CODE ..." on stderr).
)";

int main(int argc, char** argv) {
    namespace k = aos::llm_kernel;
    try {
        aos::loop::block_signals();
        aos::Cli cli;
        try {
            cli = aos::parse_cli(std::vector<std::string>(argv + 1, argv + argc), {}, {}, HELP);   // 目前沒有旗標
        } catch (const aos::Error& e) {
            throw aos::usage_error(e.code, e.msg, USAGE);
        }
        if (cli.rest.size() != 1) {
            std::string why = "missing config file";
            if (!cli.rest.empty()) {
                why = "only one config file allowed, got extra " + cli.rest[1];
            }
            throw aos::usage_error(k::code::ArgumentsBad, why, USAGE);
        }
        const char* s = std::getenv("AOS_STACK");
        if (s == nullptr || s[0] == '\0') {
            throw aos::Error{k::code::StackMissing, "AOS_STACK is not set"};
        }
        k::Cfg cfg = k::read_cfg(cli.rest[0], s);
        return k::serve(cfg, s);
    } catch (const aos::Error& e) {
        return aos::fail("aos-llm-kernel", e);
    } catch (const std::exception& e) {
        return aos::fail("aos-llm-kernel", k::code::Internal, e.what());
    }
}
