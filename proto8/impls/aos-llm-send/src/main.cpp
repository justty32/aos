// main.cpp：aos-llm-send 命令列——把一張單子當成請求寄進 kernel 的信箱，等回信，結果原樣交回、以單子的碼結束。
//
//     aos-llm-send [旗標] 單子.json
//
//   block_signals → 命令列（目前沒有旗標；唯一的位置參數＝單子檔，可寫 `檔#/指標`）→ mailbox（$AOS_KERNEL）→ post → wait_reply
// 呼叫它的那一格不知道有 kernel（C-20）：跟直接跑那張單子一樣拿到 stdout、stderr、結束碼。
// 自己出錯、或 kernel 回「沒跑／跑不起來」：stderr 一行「aos-llm-send: 代號 原因」、退 1（N-60）。
#include "send/send.hpp"
#include "wait/wait.hpp"

#include "aos/cli.hpp"

#include <cstdio>
#include <exception>

static const char* USAGE = "usage: aos-llm-send [旗標] 單子.json";

static int fail(const std::string& code, const std::string& msg) {
    std::fflush(stdout);
    std::fprintf(stderr, "aos-llm-send: %s %s\n", code.c_str(), msg.c_str());
    std::fflush(stderr);
    return 1;
}

int main(int argc, char** argv) {
    namespace g = aos::llm_send;
    try {
        aos::loop::block_signals();
        aos::Cli cli;
        try {
            cli = aos::parse_cli(std::vector<std::string>(argv + 1, argv + argc), {});   // 目前沒有旗標
        } catch (const aos::Error& e) {
            throw aos::Error{e.code, std::string(USAGE) + "（" + e.msg + "）"};
        }
        if (cli.rest.size() != 1) {
            std::string why = "沒有單子檔";
            if (!cli.rest.empty()) {
                why = "單子檔只能一個，多給了 " + cli.rest[1];
            }
            throw aos::Error{g::code::ArgumentsBad, std::string(USAGE) + "（" + why + "）"};
        }
        g::Mailbox mb = g::mailbox();
        std::string id = g::post(mb, cli.rest[0]);
        return g::wait_reply(mb, id);
    } catch (const aos::Error& e) {
        return fail(e.code, e.msg);
    } catch (const std::exception& e) {
        return fail(g::code::Internal, e.what());
    }
}
