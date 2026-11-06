// main.cpp：aos-json 命令列——第一個參數挑子命令，其餘交給它（src/cmd/）。
//
//     aos-json [旗標] 子命令 [旗標...] 檔#/指標 [...]
//
// 子命令前先 parse_cli（旗標表是空的；只認 --help）：不認得的旗標＝FlagUnknown，子命令不認得才 CommandUnknown（11-05 stdio-unify R4）。
// 出錯 stderr 一行「aos-json: error: 代號 原因」、退 1（R1）。check 有問題退 10（R7）。
#include "cmd/cmd.hpp"
#include "common/common.hpp"
#include "help/help.hpp"

#include "aos/util/cli.hpp"

#include <cstdio>
#include <exception>
#include <iostream>
#include <map>

namespace {

const char* USAGE = "aos-json [FLAGS] SUBCOMMAND [ARGS...]";

const char* HELP = R"(aos-json - Read and edit aos JSON files.

usage: aos-json [FLAGS] SUBCOMMAND [ARGS...]
       aos-json SUBCOMMAND --help

subcommands:
  get      print a value
  peek     inspect one level of a value
  where    locate the source of a value
  set      set a value
  batch    set several values from stdin
  del      delete a key or array element
  append   append to an array
  merge    merge keys into an object
  env      write an environment directive
  ref      write a reference directive
  check    check files

flags:
  -h, --help   show this help

Address values with FILE#/POINTER; follow $ref when requested.

exit codes: 0 success; 10 check found problems; 1 error.
more: aos-json/README.md
)";

int fail(const aos::Error& e) {
    return aos::fail("aos-json", e);
}

}  // namespace

int main(int argc, char** argv) {
    using namespace aos::json;
    const std::map<std::string, int (*)(const Args&)> table = {
        {"get", cmd_get},       {"peek", cmd_peek},   {"where", cmd_where}, {"set", cmd_set}, {"batch", cmd_batch}, {"del", cmd_del}, {"append", cmd_append},
        {"merge", cmd_merge},   {"env", cmd_env},     {"ref", cmd_ref}, {"check", cmd_check},
    };
    std::string sub_cmd;
    try {
        aos::Cli cli = aos::parse_cli(Args(argv + 1, argv + argc), {}, {}, HELP);
        if (cli.rest.empty()) {
            throw aos::usage_error(code::ArgumentsBad, "missing subcommand", USAGE);
        }
        auto it = table.find(cli.rest[0]);
        if (it == table.end()) {
            throw aos::usage_error(code::CommandUnknown, "unknown subcommand " + cli.rest[0], USAGE);
        }
        sub_cmd = cli.rest[0];
        return it->second(Args(cli.rest.begin() + 1, cli.rest.end()));
    } catch (const aos::Error& e) {
        if (!sub_cmd.empty() && e.code == code::FlagUnknown) {
            return fail(aos::Error{e.code, e.msg + " (see aos-json " + sub_cmd + " --help)"});
        }
        if (!sub_cmd.empty() && e.code == code::ArgumentsBad && e.msg.find(" (usage: ") == std::string::npos) {
            return fail(aos::usage_error(e.code, e.msg, cli_usage(sub_cmd)));
        }
        return fail(e);
    } catch (const std::exception& e) {
        return fail(aos::Error{code::Internal, e.what()});
    }
}
