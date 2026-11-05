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

#include <cstdio>
#include <exception>
#include <map>
#include <optional>

static const char* USAGE =
    "aos-llm [FLAGS] send [--priority P] --reply-to BOX | recv BOX LETTER | ask [--priority P] | regret LETTER | ls [--json]";

static const char* HELP = R"(usage: aos-llm [FLAGS] SUBCOMMAND [FLAGS...] [ARGS...]

Send request letters to the LLM kernel's mailbox ($AOS_LLM_KERNEL) and get replies.
body.json = {"endpoint"?: PACK, "request": {"messages": [...], ...}, "priority"?}

subcommands:
  send [--priority P] --reply-to BOX < body.json   send; prints the letter name
  recv BOX LETTER                                  print the reply's message (exit 10 = not yet)
  ask [--priority P] < body.json                   send, wait, print the reply's message
  regret LETTER                                    take back a letter still in new/
  ls [--json]                                      list the kernel's endpoint packs

flags:
  --help   show this help (aos-llm SUBCOMMAND --help shows that subcommand's)

exit codes: 0 ok; 10 no reply yet (recv); 1 error, or the reply is an error
("aos-llm: error: CODE ..." on stderr).
)";

static int fail(const std::string& code, const std::string& msg) {
    return aos::fail("aos-llm", code, msg);
}

static aos::Cli parse(const std::vector<std::string>& argv, const std::map<std::string, std::string>& flags,
                      size_t want, const std::string& what, const std::string& usage,
                      const std::map<std::string, std::string>& switches = {}) {
    namespace g = aos::llm;
    aos::Cli cli;
    try {
        cli = aos::parse_cli(argv, flags, switches, "usage: " + usage + "\n\nsee aos-llm --help\n");
    } catch (const aos::Error& e) {
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
    try {
        aos::loop::block_signals();
        aos::Cli top = aos::parse_cli(std::vector<std::string>(argv + 1, argv + argc), {}, {}, HELP);
        std::vector<std::string> args = top.rest;
        if (args.empty()) {
            throw aos::usage_error(g::code::ArgumentsBad, "no subcommand given", USAGE);
        }
        std::string cmd = args[0];
        args.erase(args.begin());
        if (cmd == "send") {
            const char* u = "aos-llm send [--priority P] --reply-to BOX < body.json";
            aos::Cli cli = parse(args, {{"--priority", "priority"}, {"--reply-to", "reply_to"}}, 0, "send takes no positional arguments", u);
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
            aos::Cli cli = parse(args, {}, 2, "recv needs BOX and a letter name", "aos-llm recv BOX LETTER");
            return g::recv(cli.rest[0], cli.rest[1]);
        }
        if (cmd == "ask") {
            aos::Cli cli = parse(args, {{"--priority", "priority"}}, 0, "ask takes no positional arguments", "aos-llm ask [--priority P] < body.json");
            g::Mailbox mb = g::kernel();
            g::warn_idle(mb);
            aos::Json body = g::read_body(opt(cli, "priority"));
            std::string id = g::send_held(mb, body);
            return g::ask_wait(mb, id);
        }
        if (cmd == "ls") {
            aos::Cli cli = parse(args, {}, 0, "ls takes no positional arguments", "aos-llm ls [--json]", {{"--json", "json"}});
            g::ls_print(g::ls_window(g::kernel()), cli.opts.count("json") > 0);
            return 0;
        }
        if (cmd == "regret") {
            aos::Cli cli = parse(args, {}, 1, "regret needs a letter name", "aos-llm regret LETTER");
            g::regret(g::kernel(), cli.rest[0]);
            return 0;
        }
        throw aos::usage_error(g::code::CommandUnknown, "unknown subcommand " + cmd, USAGE);
    } catch (const aos::Error& e) {
        return fail(e.code, e.msg);
    } catch (const std::exception& e) {
        return fail(aos::llm::code::Internal, e.what());
    }
}
