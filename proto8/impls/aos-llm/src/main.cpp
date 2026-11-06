// main.cpp：aos-llm 命令列——寄請求信進 LLM kernel 的信箱、收回信的基礎工具（定位同 aos-post；thinking 11-04 think-as-function 02/01 § 5）。
//
//     aos-llm send [--priority P] --reply-to BOX < body.json   寄（非同步、不建 sender.flock）；stdout 印信件名稱、退 0
//     aos-llm recv BOX 信件名稱                               收：到了印 body.message 一行、0；沒到 10
//     aos-llm ask [--priority P] < body.json                  同步：寄、等、印 body.message、0
//     aos-llm regret 信件名稱                                 撤回還在 new/ 的信；已被認領＝RegretFailed
//     aos-llm ls [--json]                                     列 kernel 的包（讀 $AOS_LLM_KERNEL 的 stack 底下 endpoints.json）：一行一包；沒窗＝EndpointsMissing
//
//   block_signals → 子命令 → 命令列（旗標在位置參數前，P-44；aos-util 的 parse_cli）→ $AOS_LLM_KERNEL（send、ask、regret）→ 做事
//   body＝{"endpoint"?: 代號, "request": {"messages": [...], ...}, "priority"?}（呼叫端自己組；--priority 有給就蓋 body.priority）。
// 自己出錯、或回信是 error：stderr 一行「aos-llm: error: 代號 原因」、退 1（11-05 stdio-unify R1）。
// 子命令前先 parse_cli（旗標表是空的；只認 --help）：不認得的旗標＝FlagUnknown，子命令不認得才 CommandUnknown（R4）；子命令後的 --help＝那個子命令的說明。
#include "ls/ls.hpp"
#include "send/send.hpp"
#include "wait/wait.hpp"

#include "aos/cli.hpp"
#include "aos/signals.hpp"

#include <cstdio>
#include <exception>
#include <map>
#include <optional>

static const char* USAGE = "aos-llm [FLAGS] SUBCOMMAND [ARGS...]";

static const char* HELP = R"(aos-llm - Send requests to the LLM kernel and receive replies.

usage: aos-llm [FLAGS] SUBCOMMAND [ARGS...]
       aos-llm SUBCOMMAND --help

subcommands:
  send     send a request from stdin
  recv     receive a reply
  ask      send a request and wait
  regret   withdraw a waiting request
  ls       list endpoint packs

flags:
  -h, --help   show this help

Requests use $AOS_LLM_KERNEL. Body JSON has request; endpoint and priority are optional.

exit codes: 0 success; 10 no reply yet; 1 error.
more: aos-llm/README.md
)";

static const std::map<std::string, std::string> SUB_USAGE = {
    {"send", "aos-llm send [--priority P] --reply-to BOX < body.json"},
    {"recv", "aos-llm recv BOX LETTER"},
    {"ask", "aos-llm ask [--priority P] < body.json"},
    {"regret", "aos-llm regret LETTER"},
    {"ls", "aos-llm ls [--json]"},
};

static const std::map<std::string, std::string> SUB_HELP = {
    {"send", R"(aos-llm send - Send a request to the LLM kernel.

usage: aos-llm send [--priority P] --reply-to BOX < body.json
       aos-llm send --help

flags:
  --priority P     override body.priority
  --reply-to BOX   set the mailbox for replies (required)
  -h, --help       show this help

Read body JSON from stdin, send via $AOS_LLM_KERNEL, and print the letter name.

exit codes: 0 sent; 1 error.
more: aos-llm/README.md
)"},
    {"recv", R"(aos-llm recv - Receive a reply.

usage: aos-llm recv BOX LETTER
       aos-llm recv --help

flags:
  -h, --help   show this help

Print the reply's body.message as one JSON line and finish the reply letter.

exit codes: 0 received; 10 no reply yet; 1 error.
more: aos-llm/README.md
)"},
    {"ask", R"(aos-llm ask - Send a request and wait for its reply.

usage: aos-llm ask [--priority P] < body.json
       aos-llm ask --help

flags:
  --priority P   override body.priority
  -h, --help     show this help

Read body JSON from stdin, send via $AOS_LLM_KERNEL, and print body.message.

exit codes: 0 received; 1 error.
more: aos-llm/README.md
)"},
    {"regret", R"(aos-llm regret - Withdraw a waiting LLM request.

usage: aos-llm regret LETTER
       aos-llm regret --help

flags:
  -h, --help   show this help

Remove LETTER from $AOS_LLM_KERNEL/mailbox/new/; print nothing.

exit codes: 0 withdrawn; 1 error.
more: aos-llm/README.md
)"},
    {"ls", R"(aos-llm ls - List the LLM kernel endpoint packs.

usage: aos-llm ls [--json]
       aos-llm ls --help

flags:
  -j, --json   print the endpoint window as one JSON line
  -h, --help   show this help

Read $AOS_LLM_KERNEL/endpoints.json and print one pack per line.
Columns (TAB): name, speed, cost, context, slots, summary.

exit codes: 0 listed; 1 error.
more: aos-llm/README.md
)"},
};

static int fail(const std::string& code, const std::string& msg) {
    return aos::fail("aos-llm", code, msg);
}

static aos::Cli parse(const std::vector<std::string>& argv, const std::map<std::string, std::string>& flags,
                      size_t want, const std::string& what, const std::string& command,
                      const std::map<std::string, std::string>& switches = {},
                      const std::vector<std::string>& short_flags = {}) {
    namespace g = aos::llm;
    const std::string& usage = SUB_USAGE.at(command);
    aos::Cli cli;
    try {
        cli = aos::parse_cli(argv, flags, switches, SUB_HELP.at(command), short_flags);
    } catch (const aos::Error& e) {
        if (e.code == g::code::FlagUnknown) {
            throw aos::Error{e.code, e.msg + " (see aos-llm " + command + " --help)"};
        }
        throw aos::usage_error(e.code, e.msg, usage);
    }
    if (cli.rest.size() != want) {
        throw aos::usage_error(g::code::ArgumentsBad, what, usage);
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
    std::string sub_cmd;
    try {
        aos::block_signals();
        aos::Cli top = aos::parse_cli(std::vector<std::string>(argv + 1, argv + argc), {}, {}, HELP);
        std::vector<std::string> args = top.rest;
        if (args.empty()) {
            throw aos::usage_error(g::code::ArgumentsBad, "no subcommand given", USAGE);
        }
        std::string cmd = args[0];
        sub_cmd = cmd;
        args.erase(args.begin());
        if (cmd == "send") {
            const std::string& u = SUB_USAGE.at("send");
            aos::Cli cli = parse(args, {{"--priority", "priority"}, {"--reply-to", "reply_to"}}, 0, "send takes no positional arguments", "send");
            std::optional<std::string> rt = opt(cli, "reply_to");
            if (!rt || rt->empty()) {
                throw aos::usage_error(g::code::ArgumentsBad, "send needs --reply-to BOX", u);
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
            aos::Cli cli = parse(args, {}, 2, "recv needs BOX and a letter name", "recv");
            return g::recv(cli.rest[0], cli.rest[1]);
        }
        if (cmd == "ask") {
            aos::Cli cli = parse(args, {{"--priority", "priority"}}, 0, "ask takes no positional arguments", "ask");
            g::Mailbox mb = g::kernel();
            g::warn_idle(mb);
            aos::Json body = g::read_body(opt(cli, "priority"));
            std::string id = g::send_held(mb, body);
            return g::ask_wait(mb, id);
        }
        if (cmd == "ls") {
            aos::Cli cli = parse(args, {}, 0, "ls takes no positional arguments", "ls", {{"--json", "json"}}, {"-j"});
            g::ls_print(g::ls_window(g::kernel()), cli.opts.count("json") > 0);
            return 0;
        }
        if (cmd == "regret") {
            aos::Cli cli = parse(args, {}, 1, "regret needs a letter name", "regret");
            g::regret(g::kernel(), cli.rest[0]);
            return 0;
        }
        throw aos::usage_error(g::code::CommandUnknown, "unknown subcommand " + cmd, USAGE);
    } catch (const aos::Error& e) {
        if (SUB_USAGE.count(sub_cmd) && e.code == g::code::ArgumentsBad &&
            e.msg.find(" (usage: ") == std::string::npos) {
            return aos::fail("aos-llm", aos::usage_error(e.code, e.msg, SUB_USAGE.at(sub_cmd)));
        }
        return fail(e.code, e.msg);
    } catch (const std::exception& e) {
        return fail(aos::llm::code::Internal, e.what());
    }
}
