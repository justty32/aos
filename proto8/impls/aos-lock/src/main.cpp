// main.cpp：aos-lock 命令列——第一個參數挑子命令，其餘照 aos-util 的 parse_cli（旗標在位置參數前面）。
//
//     aos-lock acquire [--lease-ms N] [--note 字] [--wait-ms N] [--pid N] 目標    拿到退 0；拿不到退 10
//     aos-lock release 目標                                                         鎖不在退 1（LockMissing）
//     aos-lock show 目標                                                            印名牌一行；沒有鎖退 10
//
// 目標換成鎖資料夾：結尾 / 或現有的資料夾＝<目標>/.lock/，否則＝<目標>.lock/（lock_dir_of）。
// 名牌上的持有者預設是**叫 aos-lock 的那個行程**（getppid）：aos-lock 拿完就退，名牌寫它自己的 pid 等於一拿到就死了。
// 要寫別的行程用 --pid。結束碼照 N-43：0 成功、10 沒東西（拿不到、沒有鎖）、1 錯。出錯 stderr 一行「aos-lock: error: 代號 原因」（11-05 stdio-unify R1）。
// 子命令前先 parse_cli（旗標表是空的；只認 --help）：不認得的旗標＝FlagUnknown，子命令不認得才 CommandUnknown（R4）。
#include "aos/cli.hpp"
#include "aos/lock.hpp"
#include "aos/proc.hpp"

#include <exception>
#include <iostream>
#include <map>

#include <unistd.h>

namespace {

namespace l = aos::lock;
using Args = std::vector<std::string>;

const char* USAGE = "aos-lock [FLAGS] acquire|release|show [FLAGS...] TARGET";

const char* HELP = R"(usage: aos-lock [FLAGS] SUBCOMMAND [FLAGS...] TARGET

A lock folder next to TARGET (TARGET/.lock/ for a folder, TARGET.lock/ otherwise)
with a holder.json name tag (pid, started_at_ticks, boot_id, lease, note).

subcommands:
  acquire [--lease-ms N] [--note TEXT] [--wait-ms N] [--pid N] TARGET
                     take the lock (holder = the calling process, or --pid)
  release TARGET     drop the lock
  show TARGET        print the holder (one JSON line)

flags:
  --help   show this help (aos-lock SUBCOMMAND --help shows that subcommand's)

exit codes: 0 ok; 10 not got / no lock (acquire, show); 1 error ("aos-lock: error: CODE ..." on stderr).
)";

const std::map<std::string, std::string> SUB_USAGE = {
    {"acquire", "aos-lock acquire [--lease-ms N] [--note TEXT] [--wait-ms N] [--pid N] TARGET"},
    {"release", "aos-lock release TARGET"},
    {"show", "aos-lock show TARGET"},
};

std::string sub_cmd;   // 正在跑的子命令（main 設）

int fail(const std::string& code, const std::string& msg) {
    return aos::fail("aos-lock", code, msg);
}

aos::Cli parse(const Args& args, const std::map<std::string, std::string>& flags) {
    const std::string& usage = SUB_USAGE.at(sub_cmd);
    aos::Cli cli = aos::parse_cli(args, flags, {}, "usage: " + usage + "\n\nsee aos-lock --help\n");
    if (cli.rest.size() != 1) {
        throw aos::usage_error(l::code::ArgumentsBad, "need exactly one TARGET", usage);
    }
    return cli;
}

// 旗標值：非負整數。
long long count_of(const aos::Cli& cli, const std::string& name, const std::string& flag) {
    const std::string& v = cli.opts.at(name);
    if (v.empty() || v.find_first_not_of("0123456789") != std::string::npos || v.size() > 15) {
        throw aos::Error{l::code::ArgumentsBad, flag + " must be a non-negative integer: " + v};
    }
    return std::stoll(v);
}

int cmd_acquire(const Args& args) {
    aos::Cli cli = parse(args, {{"--lease-ms", "lease_ms"}, {"--note", "note"}, {"--wait-ms", "wait_ms"}, {"--pid", "pid"}});
    pid_t pid = getppid();
    if (cli.opts.count("pid")) {
        pid = (pid_t)count_of(cli, "pid", "--pid");
        if (pid <= 0 || !aos::proc_started_at_ticks(pid)) {
            throw aos::Error{l::code::ArgumentsBad, "--pid: no such process: " + cli.opts["pid"]};
        }
    }
    l::Holder h = l::holder_of(pid);
    if (cli.opts.count("lease_ms")) {
        h.lease_ms = count_of(cli, "lease_ms", "--lease-ms");
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
