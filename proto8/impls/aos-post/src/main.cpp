// main.cpp：aos-post 命令列——第一個參數挑子命令，其餘照 aos-util 的 parse_cli（旗標在位置參數前面）。
//
//     aos-post init 信箱
//     aos-post send [--ordered] [--reply-to 信箱] [--in-reply-to 信號] 信箱 < body.json     印信號（--ordered＝帶序號的名字）
//     aos-post claim 信箱                                                       印一個信號；沒有退 10
//     aos-post claim-all 信箱                                                   一行一個（照名字排序）；沒有退 10
//     aos-post check 信箱 信號                                                  好信印 letter.json 一行；壞信退 1（LetterBad 原因）
//     aos-post finish [--keep] [--reply] 信箱 信號 [< body.json]                --reply＝照 reply_to 回一封、印回信的信號
//     aos-post withdraw 信箱 信號                                               撤不了退 1（WithdrawFailed）
//
// 結束碼照 N-43：0 成功、10 沒東西、1 錯。出錯 stderr 一行「aos-post: 代號 原因」（同 aos-exec、aos-json，N-60）。
#include "aos/cli.hpp"
#include "aos/post.hpp"

#include <cstdio>
#include <exception>
#include <iostream>
#include <map>

namespace {

namespace p = aos::post;
using Args = std::vector<std::string>;

const char* USAGE = "aos-post init|send|claim|claim-all|check|finish|withdraw [旗標...] 信箱 [信號]（說明見 README）";

int fail(const std::string& code, const std::string& msg) {
    std::cout << std::flush;
    std::cerr << "aos-post: " << code << " " << msg << std::endl;
    return 1;
}

// 解旗標、數位置參數（要剛好 n 個）。
aos::Cli parse(const Args& args, size_t n, const std::map<std::string, std::string>& flags,
               const std::map<std::string, std::string>& switches = {}) {
    aos::Cli cli = aos::parse_cli(args, flags, switches);
    if (cli.rest.size() != n) {
        throw aos::Error{p::code::ArgumentsBad, std::string(n == 1 ? "要一個信箱" : "要信箱與信號") + "；用法：" + USAGE};
    }
    if (n == 2) {
        p::check_id(cli.rest[1]);
    }
    return cli;
}

int cmd_init(const Args& args) {
    aos::Cli cli = parse(args, 1, {});
    p::init(cli.rest[0]);
    return 0;
}

int cmd_send(const Args& args) {
    aos::Cli cli = parse(args, 1, {{"--reply-to", "reply_to"}, {"--in-reply-to", "in_reply_to"}}, {{"--ordered", "ordered"}});
    p::Mailbox mb = p::open(cli.rest[0]);
    p::SendOpts opts;
    opts.ordered = cli.opts.count("ordered") > 0;
    if (cli.opts.count("reply_to")) {
        opts.reply_to = cli.opts["reply_to"];
    }
    if (cli.opts.count("in_reply_to")) {
        opts.in_reply_to = cli.opts["in_reply_to"];
    }
    aos::Json body = aos::read_stdin();
    std::cout << p::send(mb, body, opts) << std::endl;
    return 0;
}

int cmd_claim(const Args& args) {
    aos::Cli cli = parse(args, 1, {});
    std::optional<std::string> id = p::claim(p::open(cli.rest[0]));
    if (!id) {
        return 10;
    }
    std::cout << *id << std::endl;
    return 0;
}

int cmd_claim_all(const Args& args) {
    aos::Cli cli = parse(args, 1, {});
    std::vector<std::string> ids = p::claim_all(p::open(cli.rest[0]));
    if (ids.empty()) {
        return 10;
    }
    for (const std::string& id : ids) {
        std::cout << id << "\n";
    }
    std::cout << std::flush;
    return 0;
}

int cmd_check(const Args& args) {
    aos::Cli cli = parse(args, 2, {});
    p::Checked c = p::check(p::open(cli.rest[0]), cli.rest[1]);
    if (!c.ok) {
        return fail(p::code::LetterBad, c.reason);
    }
    std::cout << aos::dumps(c.letter) << std::endl;
    return 0;
}

int cmd_finish(const Args& args) {
    aos::Cli cli = parse(args, 2, {}, {{"--keep", "keep"}, {"--reply", "reply"}});
    p::Mailbox mb = p::open(cli.rest[0]);
    const std::string& id = cli.rest[1];
    if (cli.opts.count("reply")) {
        aos::Json body = aos::read_stdin();
        std::optional<std::string> r = p::reply(mb, id, body);   // 寄不出去就丟例外，信留在 cur/（可以再 finish 一次）
        if (r) {
            std::cout << *r << std::endl;
        }
    }
    p::finish(mb, id, cli.opts.count("keep") > 0);
    return 0;
}

int cmd_withdraw(const Args& args) {
    aos::Cli cli = parse(args, 2, {});
    if (!p::withdraw(p::open(cli.rest[0]), cli.rest[1])) {
        return fail(p::code::WithdrawFailed, "信不在 new/（已被認領，或本來就沒有）：" + cli.rest[1]);
    }
    return 0;
}

}  // namespace

int main(int argc, char** argv) {
    const std::map<std::string, int (*)(const Args&)> table = {
        {"init", cmd_init},   {"send", cmd_send},     {"claim", cmd_claim},       {"claim-all", cmd_claim_all},
        {"check", cmd_check}, {"finish", cmd_finish}, {"withdraw", cmd_withdraw},
    };
    try {
        if (argc < 2) {
            throw aos::Error{p::code::ArgumentsBad, std::string("用法：") + USAGE};
        }
        auto it = table.find(argv[1]);
        if (it == table.end()) {
            throw aos::Error{p::code::CommandUnknown, std::string("不認得的子命令 ") + argv[1] + "；用法：" + USAGE};
        }
        return it->second(Args(argv + 2, argv + argc));
    } catch (const aos::Error& e) {
        return fail(e.code, e.msg);
    } catch (const std::exception& e) {
        return fail(p::code::Internal, e.what());
    }
}
