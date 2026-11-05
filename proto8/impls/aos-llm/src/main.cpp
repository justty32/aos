// main.cpp：aos-llm 命令列——寄請求信進 LLM kernel 的信箱、收回信的基礎工具（定位同 aos-post；thinking 11-04 think-as-function 02/01 § 5）。
//
//     aos-llm send [--priority P] --reply-to BOX < body.json   寄（非同步、不建 sender.flock）；stdout 印信件名稱、退 0
//     aos-llm recv BOX 信件名稱                               收：到了印 body.message 一行、0；沒到 10
//     aos-llm ask [--priority P] < body.json                  同步：寄、等、印 body.message、0
//     aos-llm regret 信件名稱                                 撤回還在 new/ 的信；已被認領＝RegretFailed
//
//   block_signals → 子命令 → 命令列（旗標在位置參數前，P-44；aos-util 的 parse_cli）→ $AOS_LLM_KERNEL（send、ask、regret）→ 做事
//   body＝{"endpoint"?: 代號, "request": {"messages": [...], ...}, "priority"?}（呼叫端自己組；--priority 有給就蓋 body.priority）。
// 自己出錯、或回信是 error：stderr 一行「aos-llm: 代號 原因」、退 1（N-60）。
#include "send/send.hpp"
#include "wait/wait.hpp"

#include "aos/cli.hpp"

#include <cstdio>
#include <exception>
#include <map>
#include <optional>

static const char* USAGE =
    "usage: aos-llm send [--priority P] --reply-to BOX | recv BOX 信件名稱 | ask [--priority P] | regret 信件名稱";

static int fail(const std::string& code, const std::string& msg) {
    std::fflush(stdout);
    std::fprintf(stderr, "aos-llm: %s %s\n", code.c_str(), msg.c_str());
    std::fflush(stderr);
    return 1;
}

static aos::Cli parse(const std::vector<std::string>& argv, const std::map<std::string, std::string>& flags,
                      size_t want, const std::string& what) {
    namespace g = aos::llm;
    aos::Cli cli;
    try {
        cli = aos::parse_cli(argv, flags);
    } catch (const aos::Error& e) {
        throw aos::Error{e.code, std::string(USAGE) + "（" + e.msg + "）"};
    }
    if (cli.rest.size() != want) {
        throw aos::Error{g::code::ArgumentsBad, std::string(USAGE) + "（" + what + "）"};
    }
    return cli;
}

static std::optional<std::string> opt(const aos::Cli& cli, const std::string& k) {
    auto it = cli.opts.find(k);
    if (it == cli.opts.end()) {
        return std::nullopt;
    }
    return it->second;
}

int main(int argc, char** argv) {
    namespace g = aos::llm;
    try {
        aos::loop::block_signals();
        std::vector<std::string> args(argv + 1, argv + argc);
        if (args.empty()) {
            throw aos::Error{g::code::ArgumentsBad, std::string(USAGE) + "（沒給子命令）"};
        }
        std::string cmd = args[0];
        args.erase(args.begin());
        if (cmd == "send") {
            aos::Cli cli = parse(args, {{"--priority", "priority"}, {"--reply-to", "reply_to"}}, 0, "send 不收位置參數");
            std::optional<std::string> rt = opt(cli, "reply_to");
            if (!rt || rt->empty()) {
                throw aos::Error{g::code::ArgumentsBad, std::string(USAGE) + "（send 要給 --reply-to BOX）"};
            }
            g::Mailbox mb = g::kernel();
            g::warn_idle(mb);
            aos::Json body = g::read_body(opt(cli, "priority"));
            std::string id = g::send(mb, body, *rt);
            std::printf("%s\n", id.c_str());
            std::fflush(stdout);
            return 0;
        }
        if (cmd == "recv") {
            aos::Cli cli = parse(args, {}, 2, "recv 要給 BOX 與信件名稱");
            return g::recv(cli.rest[0], cli.rest[1]);
        }
        if (cmd == "ask") {
            aos::Cli cli = parse(args, {{"--priority", "priority"}}, 0, "ask 不收位置參數");
            g::Mailbox mb = g::kernel();
            g::warn_idle(mb);
            aos::Json body = g::read_body(opt(cli, "priority"));
            std::string id = g::send_held(mb, body);
            return g::ask_wait(mb, id);
        }
        if (cmd == "regret") {
            aos::Cli cli = parse(args, {}, 1, "regret 要給信件名稱");
            g::regret(g::kernel(), cli.rest[0]);
            return 0;
        }
        throw aos::Error{g::code::CommandUnknown, std::string(USAGE) + "（不認得的子命令 " + cmd + "）"};
    } catch (const aos::Error& e) {
        return fail(e.code, e.msg);
    } catch (const std::exception& e) {
        return fail(aos::llm::code::Internal, e.what());
    }
}
