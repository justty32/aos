// main.cpp：aos-json 命令列——第一個參數挑子命令，其餘交給它（src/cmd/）。
//
//     aos-json [旗標] 子命令 [旗標...] 檔#/指標 [...]
//
// 子命令前先 parse_cli（旗標表是空的；只認 --help）：不認得的旗標＝FlagUnknown，子命令不認得才 CommandUnknown（11-05 stdio-unify R4）。
// 出錯 stderr 一行「aos-json: error: 代號 原因」、退 1（R1）。check 有問題退 10（R7）。
#include "cmd/cmd.hpp"
#include "common/common.hpp"

#include "aos/cli.hpp"

#include <cstdio>
#include <exception>
#include <iostream>
#include <map>

namespace {

const char* USAGE = "aos-json [FLAGS] get|peek|where|set|batch|del|append|merge|env|ref|check [FLAGS...] FILE#/POINTER [...]";

const char* HELP = R"(usage: aos-json [FLAGS] SUBCOMMAND [FLAGS...] FILE#/POINTER [...]

Read and edit aos JSON files by JSON pointer, following $ref when asked.

subcommands:
  get      print a value               where    show where a value really lives
  peek     show one level, folded      set      set a value
  batch    set many values from stdin  del      delete a key or element
  append   append to an array          merge    shallow-merge into an object
  env      replace with {"$env": ...}  ref      replace with {"$ref": ...}
  check    check files (exit 10 when problems are found)

flags:
  --help   show this help (aos-json SUBCOMMAND --help shows that subcommand's)

exit codes: 0 ok; 10 check found problems; 1 error ("aos-json: error: CODE ..." on stderr).
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
    try {
        aos::Cli cli = aos::parse_cli(Args(argv + 1, argv + argc), {}, {}, HELP);
        if (cli.rest.empty()) {
            throw aos::usage_error(code::ArgumentsBad, "missing subcommand", USAGE);
        }
        auto it = table.find(cli.rest[0]);
        if (it == table.end()) {
            throw aos::usage_error(code::CommandUnknown, "unknown subcommand " + cli.rest[0], USAGE);
        }
        return it->second(Args(cli.rest.begin() + 1, cli.rest.end()));
    } catch (const aos::Error& e) {
        return fail(e);
    } catch (const std::exception& e) {
        return fail(aos::Error{code::Internal, e.what()});
    }
}
