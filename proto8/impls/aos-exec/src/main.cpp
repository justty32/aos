// main.cpp：aos-exec 命令列——把參數交給公開 API 的 run_cli（aos/exec.hpp、src/cli/）。
//
//     aos-exec [--ws WS] XXX [args...]
//
// XXX 前面是 aos-exec 自己的旗標（目前只有 --ws），第一個不是旗標的參數就是 XXX，之後原樣交給入口；`--` 結束旗標
// （10-21 ideas § 3，N-58；原 `aos-exec XXX [WS [args...]]`）。不認得的旗標＝FlagUnknown；沒給 XXX、旗標缺值＝ArgumentsBad。
// 自己出錯：stderr 一行「aos-exec: 代號 原因」、退出 1（照 N-60／P-21「程式名: 原因」，代號放開頭給測試認；impls 計畫 v2）。
// 入口跑起來後的結束碼就是入口的。
#include "aos/exec.hpp"

int main(int argc, char** argv) {
    std::vector<std::string> args(argv + 1, argv + argc);
    return aos::exec::run_cli(args);
}
