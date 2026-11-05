// main.cpp：aos-exec 命令列——把參數交給公開 API 的 run_cli（aos/exec.hpp、src/cli/）。
//
//     aos-exec [--ws WS] [--stack S] [--dotenv-override] XXX [ARGS...]
//
// XXX 前面是 aos-exec 自己的旗標（--ws、--stack、--dotenv-override），第一個不是旗標的參數就是 XXX，之後原樣交給入口；`--` 結束旗標
// （10-21 ideas § 3，N-58；原 `aos-exec XXX [WS [args...]]`）。不認得的旗標＝FlagUnknown；沒給 XXX、旗標缺值＝ArgumentsBad。
// 自己出錯：stderr 一行「aos-exec: error: 代號 原因」、退出 1（11-05 stdio-unify R1）。`--help`＝英文說明印 stdout、退 0（R3）。
// 入口跑起來後的結束碼就是入口的。
#include "aos/exec.hpp"

int main(int argc, char** argv) {
    std::vector<std::string> args(argv + 1, argv + argc);
    return aos::exec::run_cli(args);
}
