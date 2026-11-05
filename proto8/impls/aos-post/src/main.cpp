// main.cpp：aos-post 命令列——第一個參數挑子命令，其餘照 aos-util 的 parse_cli（旗標在位置參數前面）。
//
//     aos-post init 信箱
//     aos-post send [--ordered] [--reply-to 信箱] [--in-reply-to 信件名稱] 信箱 [信件名稱] < body.json
//                                                                印 new/ 裡的名字（--ordered＝帶序號的名字）
//     aos-post take 信箱                                         印一個信件名稱；沒有退 10
//     aos-post take-all 信箱                                     一行一個（照處理順序）；沒有退 10
//     aos-post see 信箱 [信件名稱]                               好信印 letter.json 一行；壞信退 1（LetterBad 原因）
//     aos-post done [--keep] [--reply] 信箱 [信件名稱] [< body.json]
//                                                                --reply＝照 reply_to 回一封、印回信的名字
//     aos-post regret 信箱 信件名稱                              撤不了退 1（RegretFailed）
//
// see、done 不給信件名稱＝cur/ 裡照處理順序第一封；cur/ 空退 10。
// 結束碼照 N-43：0 成功、10 沒東西、1 錯。出錯 stderr 一行「aos-post: error: 代號 原因」（11-05 stdio-unify R1）。
// 子命令前先 parse_cli（旗標表是空的；只認 --help）：不認得的旗標＝FlagUnknown，子命令不認得才 CommandUnknown（R4）；子命令後的 --help＝那個子命令的說明。
#include "aos/cli.hpp"
#include "aos/post.hpp"

#include <cstdio>
#include <exception>
#include <iostream>
#include <map>

namespace {

namespace p = aos::post;
using Args = std::vector<std::string>;

const char* USAGE = "aos-post [FLAGS] init|send|take|take-all|see|done|regret [FLAGS...] MAILBOX [LETTER]";

const char* HELP = R"(usage: aos-post [FLAGS] SUBCOMMAND [FLAGS...] MAILBOX [LETTER]

A maildir-style mailbox (tmp/ new/ cur/): letters are folders with letter.json.

subcommands:
  init MAILBOX                       create the mailbox
  send [--ordered] [--reply-to BOX] [--in-reply-to LETTER] MAILBOX [LETTER] < body.json
                                     send a letter; prints its name
  take MAILBOX                       move the next letter new/ -> cur/; prints its name
  take-all MAILBOX                   take every letter; one name per line
  see MAILBOX [LETTER]               print letter.json (default: first in cur/)
  done [--keep] [--reply] MAILBOX [LETTER] [< body.json]
                                     finish a letter (--reply answers to its reply_to)
  regret MAILBOX LETTER              take back a letter still in new/

flags:
  --help   show this help (aos-post SUBCOMMAND --help shows that subcommand's)

exit codes: 0 ok; 10 nothing there (take, take-all, see, done); 1 error ("aos-post: error: CODE ..." on stderr).
)";

// 子命令的用法（錯誤行的 usage 與 SUBCOMMAND --help）
const std::map<std::string, std::string> SUB_USAGE = {
    {"init", "aos-post init MAILBOX"},
    {"send", "aos-post send [--ordered] [--reply-to BOX] [--in-reply-to LETTER] MAILBOX [LETTER] < body.json"},
    {"take", "aos-post take MAILBOX"},
    {"take-all", "aos-post take-all MAILBOX"},
    {"see", "aos-post see MAILBOX [LETTER]"},
    {"done", "aos-post done [--keep] [--reply] MAILBOX [LETTER] [< body.json]"},
    {"regret", "aos-post regret MAILBOX LETTER"},
};

std::string sub_cmd;   // 正在跑的子命令（main 設）

int fail(const std::string& code, const std::string& msg) {
    return aos::fail("aos-post", code, msg);
}

// 解旗標、數位置參數（要 lo～hi 個：信箱，加上可有可無或必給的信件名稱）。信件名稱照 check_name 驗。
aos::Cli parse(const Args& args, size_t lo, size_t hi, const std::map<std::string, std::string>& flags,
               const std::map<std::string, std::string>& switches = {}) {
    const std::string& usage = SUB_USAGE.at(sub_cmd);
    aos::Cli cli = aos::parse_cli(args, flags, switches, "usage: " + usage + "\n\nsee aos-post --help\n");
    if (cli.rest.size() < lo || cli.rest.size() > hi) {
        std::string want = hi == 1 ? "expects one mailbox" : lo == 2 ? "expects a mailbox and a letter name" : "expects a mailbox (letter name optional)";
        throw aos::usage_error(p::code::ArgumentsBad, want, usage);
    }
    if (cli.rest.size() == 2) {
        p::check_name(cli.rest[1]);
    }
    return cli;
}

// see、done 的信件名稱：給了就用；沒給＝cur/ 裡照處理順序第一封（沒有＝nullopt，退 10）。
std::optional<std::string> name_or_first(const aos::Cli& cli, const p::Mailbox& mb) {
    if (cli.rest.size() == 2) {
        return cli.rest[1];
    }
    return p::first_in_cur(mb);
}

int cmd_init(const Args& args) {
    aos::Cli cli = parse(args, 1, 1, {});
    p::init(cli.rest[0]);
    return 0;
}

int cmd_send(const Args& args) {
    aos::Cli cli = parse(args, 1, 2, {{"--reply-to", "reply_to"}, {"--in-reply-to", "in_reply_to"}}, {{"--ordered", "ordered"}});
    p::Mailbox mb = p::open(cli.rest[0]);
    p::SendOpts opts;
    opts.ordered = cli.opts.count("ordered") > 0;
    if (cli.rest.size() == 2) {
        opts.name = cli.rest[1];
    }
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

int cmd_take(const Args& args) {
    aos::Cli cli = parse(args, 1, 1, {});
    std::optional<std::string> name = p::take(p::open(cli.rest[0]));
    if (!name) {
        return 10;
    }
    std::cout << *name << std::endl;
    return 0;
}

int cmd_take_all(const Args& args) {
    aos::Cli cli = parse(args, 1, 1, {});
    std::vector<std::string> names = p::take_all(p::open(cli.rest[0]));
    if (names.empty()) {
        return 10;
    }
    for (const std::string& name : names) {
        std::cout << name << "\n";
    }
    std::cout << std::flush;
    return 0;
}

int cmd_see(const Args& args) {
    aos::Cli cli = parse(args, 1, 2, {});
    p::Mailbox mb = p::open(cli.rest[0]);
    std::optional<std::string> name = name_or_first(cli, mb);
    if (!name) {
        return 10;
    }
    p::Seen c = p::see(mb, *name);
    if (!c.ok) {
        return fail(p::code::LetterBad, c.reason);
    }
    std::cout << aos::dumps(c.letter) << std::endl;
    return 0;
}

int cmd_done(const Args& args) {
    aos::Cli cli = parse(args, 1, 2, {}, {{"--keep", "keep"}, {"--reply", "reply"}});
    p::Mailbox mb = p::open(cli.rest[0]);
    std::optional<std::string> name = name_or_first(cli, mb);
    if (!name) {
        return 10;
    }
    if (cli.opts.count("reply")) {
        aos::Json body = aos::read_stdin();
        std::optional<std::string> r = p::reply(mb, *name, body);   // 寄不出去就丟例外，信留在 cur/（可以再 done 一次）
        if (r) {
            std::cout << *r << std::endl;
        }
    }
    p::done(mb, *name, cli.opts.count("keep") > 0);
    return 0;
}

int cmd_regret(const Args& args) {
    aos::Cli cli = parse(args, 2, 2, {});
    if (!p::regret(p::open(cli.rest[0]), cli.rest[1])) {
        return fail(p::code::RegretFailed, "letter not in new/ (already taken, or never there): " + cli.rest[1]);
    }
    return 0;
}

}  // namespace

int main(int argc, char** argv) {
    const std::map<std::string, int (*)(const Args&)> table = {
        {"init", cmd_init}, {"send", cmd_send}, {"take", cmd_take},     {"take-all", cmd_take_all},
        {"see", cmd_see},   {"done", cmd_done}, {"regret", cmd_regret},
    };
    try {
        aos::Cli cli = aos::parse_cli(Args(argv + 1, argv + argc), {}, {}, HELP);
        if (cli.rest.empty()) {
            throw aos::usage_error(p::code::ArgumentsBad, "missing subcommand", USAGE);
        }
        auto it = table.find(cli.rest[0]);
        if (it == table.end()) {
            throw aos::usage_error(p::code::CommandUnknown, "unknown subcommand " + cli.rest[0], USAGE);
        }
        sub_cmd = cli.rest[0];
        return it->second(Args(cli.rest.begin() + 1, cli.rest.end()));
    } catch (const aos::Error& e) {
        return fail(e.code, e.msg);
    } catch (const std::exception& e) {
        return fail(p::code::Internal, e.what());
    }
}
