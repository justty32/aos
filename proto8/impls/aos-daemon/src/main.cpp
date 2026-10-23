// main.cpp：aos-daemon 命令列——block_signals、解命令列、讀設定、Daemon::serve（照 proto8/bin/aos-daemon，10-21 傍晚）。
//
//     aos-daemon [--max N] [--interval-ms N] [--ctl 檔] [--state 檔] daemon.json
//
// 命令列同 aos-loop（loop_cli；唯一的位置參數＝設定檔，可寫 `檔#/指標`；10-21 傍晚 ideas § 9）。
// 管一群長壽的子 loop（C-36、N-28）；每個子項的小格是 $AOS_STACK/<名字>/（P-17）。規則見 README 與 daemon/daemon.hpp。
// 不論為什麼結束都先收掉所有子 loop、寫好 state 再結束；收到 SIGINT／SIGTERM／SIGHUP 以 128＋N 結束（P-36）。
// 自己出錯：stderr 一行「aos-daemon: 代號 原因」、退 1。PATH 不動（子 loop 要的 aos-exec、aos-loop 由呼叫者放進 PATH）。
#include "daemon/daemon.hpp"

#include <cstdio>
#include <exception>

static int fail(const std::string& code, const std::string& msg) {
    std::fprintf(stderr, "aos-daemon: %s %s\n", code.c_str(), msg.c_str());
    std::fflush(stderr);
    return 1;
}

int main(int argc, char** argv) {
    try {
        aos::loop::block_signals();
        aos::Cli cli = aos::loop::loop_cli(std::vector<std::string>(argv + 1, argv + argc), "aos-daemon");
        aos::daemon::Daemon d(cli.opts, cli.rest[0]);
        return d.serve();
    } catch (const aos::Error& e) {
        return fail(e.code, e.msg);
    } catch (const std::exception& e) {
        return fail(aos::code::Internal, e.what());
    }
}
