// main.cpp：aos-lock 命令列——無存活標記的持久鎖、tick 租約、放鎖與查看。
#include "aos/util/cli.hpp"
#include "aos/lock.hpp"

#include <exception>
#include <iostream>
#include <map>


namespace {

namespace l = aos::lock;
using Args = std::vector<std::string>;

const char* USAGE = "aos-lock [FLAGS] SUBCOMMAND [ARGS...]";

const char* HELP = R"(aos-lock - Acquire, release and inspect locks.

usage: aos-lock [FLAGS] SUBCOMMAND [ARGS...]
       aos-lock SUBCOMMAND --help

subcommands:
  acquire   take a lock
  release   drop a lock
  show      print the holder as JSON

flags:
  -h, --help   show this help

A folder or trailing / uses TARGET/.lock/; other targets use TARGET.lock/.

exit codes: 0 success; 10 unavailable or no lock; 1 error.
more: aos-lock/README.md
)";

const std::map<std::string, std::string> SUB_USAGE = {
    {"acquire", "aos-lock acquire [--lease-ticks N] [--note TEXT] [--wait-ms N] TARGET"},
    {"release", "aos-lock release TARGET"},
    {"show", "aos-lock show TARGET"},
};

const std::map<std::string, std::string> SUB_HELP = {
    {"acquire", R"(aos-lock acquire - Acquire a lock next to TARGET.

usage: aos-lock acquire [--lease-ticks N] [--note TEXT] [--wait-ms N] TARGET
       aos-lock acquire --help

flags:
  --lease-ticks N   expire the lease after N ticks (default: no expiry)
  --note TEXT    store a note in the holder tag
  --wait-ms N    wait up to N milliseconds (default: 0)
  -h, --help     show this help

Create the lock folder and holder.json; print nothing.

exit codes: 0 acquired; 10 unavailable; 1 error.
more: aos-lock/README.md
)"},
    {"release", R"(aos-lock release - Release a lock.

usage: aos-lock release TARGET
       aos-lock release --help

flags:
  -h, --help   show this help

Remove the lock folder next to TARGET; print nothing.

exit codes: 0 released; 1 error (including a missing lock).
more: aos-lock/README.md
)"},
    {"show", R"(aos-lock show - Read the lock holder.

usage: aos-lock show TARGET
       aos-lock show --help

flags:
  -h, --help   show this help

Print holder.json as one JSON line for the lock next to TARGET.

exit codes: 0 found; 10 no lock; 1 error.
more: aos-lock/README.md
)"},
};

std::string sub_cmd;   // 正在跑的子命令（main 設）

int fail(const std::string& code, const std::string& msg) {
    return aos::fail("aos-lock", code, msg);
}

aos::Cli parse(const Args& args, const std::map<std::string, std::string>& flags) {
    const std::string& usage = SUB_USAGE.at(sub_cmd);
    aos::Cli cli;
    try {
        cli = aos::parse_cli(args, flags, {}, SUB_HELP.at(sub_cmd));
    } catch (const aos::Error& e) {
        if (e.code == l::code::FlagUnknown) {
            throw aos::Error{e.code, e.msg + " (see aos-lock " + sub_cmd + " --help)"};
        }
        throw aos::usage_error(e.code, e.msg, usage);
    }
    if (cli.rest.size() != 1) {
        throw aos::usage_error(l::code::ArgumentsBad, "need exactly one TARGET", usage);
    }
    return cli;
}

// 旗標值：非負整數。
long long count_of(const aos::Cli& cli, const std::string& name, const std::string& flag) {
    const std::string& v = cli.opts.at(name);
    if (v.empty() || v.find_first_not_of("0123456789") != std::string::npos || v.size() > 15) {
        throw aos::usage_error(l::code::ArgumentsBad, flag + " must be a non-negative integer: " + v, SUB_USAGE.at(sub_cmd));
    }
    return std::stoll(v);
}

int cmd_acquire(const Args& args) {
    aos::Cli cli = parse(args, {{"--lease-ticks", "lease_ticks"}, {"--note", "note"}, {"--wait-ms", "wait_ms"}});
    l::Holder h = l::holder_of(false);
    if (cli.opts.count("lease_ticks")) {
        h.lease_ticks = count_of(cli, "lease_ticks", "--lease-ticks");
    }
    if (cli.opts.count("note")) {
        h.note = cli.opts["note"];
    }
    long long wait_ms = 0;
    if (cli.opts.count("wait_ms")) {
        wait_ms = count_of(cli, "wait_ms", "--wait-ms");
    }
    return l::acquire(l::lock_dir_of(cli.rest[0]), h, wait_ms) ? 0 : 10;
}

int cmd_release(const Args& args) {
    aos::Cli cli = parse(args, {});
    std::string dir = l::lock_dir_of(cli.rest[0]);
    if (!l::release(dir)) {
        return fail(l::code::LockMissing, "lock not held: " + dir);
    }
    return 0;
}

int cmd_show(const Args& args) {
    aos::Cli cli = parse(args, {});
    std::string dir = l::lock_dir_of(cli.rest[0]);
    l::Seen s = l::look(dir);
    if (!s.held) {
        return 10;
    }
    if (!s.holder) {
        return fail(l::code::HolderBad, "holder file missing or unreadable: " + dir + "/holder.json");
    }
    std::cout << aos::dumps(*s.holder) << std::endl;
    return 0;
}

}  // namespace

int main(int argc, char** argv) {
    const std::map<std::string, int (*)(const Args&)> table = {
        {"acquire", cmd_acquire}, {"release", cmd_release}, {"show", cmd_show},
    };
    try {
        aos::Cli cli = aos::parse_cli(Args(argv + 1, argv + argc), {}, {}, HELP);
        if (cli.rest.empty()) {
            throw aos::usage_error(l::code::ArgumentsBad, "missing subcommand", USAGE);
        }
        auto it = table.find(cli.rest[0]);
        if (it == table.end()) {
            throw aos::usage_error(l::code::CommandUnknown, "unknown subcommand " + cli.rest[0], USAGE);
        }
        sub_cmd = cli.rest[0];
        return it->second(Args(cli.rest.begin() + 1, cli.rest.end()));
    } catch (const aos::Error& e) {
        return fail(e.code, e.msg);
    } catch (const std::exception& e) {
        return fail(l::code::Internal, e.what());
    }
}
