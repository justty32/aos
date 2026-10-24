// main.cpp：aos-json 命令列——第一個參數挑子命令，其餘交給它（src/cmd/）。
//
//     aos-json 子命令 [旗標...] 檔#/指標 [...]
//
// 出錯 stderr 一行「aos-json: 代號 原因」、退 1（同 aos-exec、aos-loop，N-60／P-21）。
#include "cmd/cmd.hpp"
#include "common/common.hpp"

#include <cstdio>
#include <exception>
#include <iostream>
#include <map>

namespace {

const char* USAGE = "aos-json get|peek|where|set|batch|del|append|merge|env|ref|check [旗標...] 檔#/指標 [...]（說明見 README）";

int fail(const aos::Error& e) {
    std::cout << std::flush;
    std::cerr << "aos-json: " << e.code << " " << e.msg << std::endl;
    return 1;
}

}  // namespace

int main(int argc, char** argv) {
    using namespace aos::json;
    const std::map<std::string, int (*)(const Args&)> table = {
        {"get", cmd_get},       {"peek", cmd_peek},   {"where", cmd_where}, {"set", cmd_set}, {"batch", cmd_batch}, {"del", cmd_del}, {"append", cmd_append},
        {"merge", cmd_merge},   {"env", cmd_env},     {"ref", cmd_ref}, {"check", cmd_check},
    };
    try {
        if (argc < 2) {
            throw aos::Error{code::ArgumentsBad, std::string("用法：") + USAGE};
        }
        auto it = table.find(argv[1]);
        if (it == table.end()) {
            throw aos::Error{code::CommandUnknown, std::string("不認得的子命令 ") + argv[1] + "；用法：" + USAGE};
        }
        return it->second(Args(argv + 2, argv + argc));
    } catch (const aos::Error& e) {
        return fail(e);
    } catch (const std::exception& e) {
        return fail(aos::Error{code::Internal, e.what()});
    }
}
