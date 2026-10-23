// main.cpp：aos-loop 命令列——block_signals、解命令列、讀設定、Loop::serve（公開 API 見 aos/loop.hpp）。
//
//     aos-loop [--max N] [--interval-ms N] [--ctl 檔] [--state 檔] loop.json
//
// 唯一的位置參數就是設定檔（必給、只能一個；可寫 `檔#/指標`）；旗標放前面、規則同 aos-exec；起跑時 旗標 ＞ loop.json ＞ 預設
// （10-21 傍晚 ideas § 9）。run＝字串或 [目標, 參數...]，每次 `aos-exec -- 目標 參數...`；max 沒寫＝不限。
// 那次的碼：0＝下一次；10＝正常停（以 0 結束）；其他非 0＝失敗，stderr 一行「aos-loop: 第 N 次 誰 失敗，結束碼 C」、以那個碼結束。
// 跑滿 max 以 0 結束、stderr 不寫（N-43）。收到 SIGINT／SIGTERM／SIGHUP：轉給正在跑的那次、等它結束，再以 128＋N 結束
// （兩次之間收到就不起下一次）。選填 interval_ms、ctl、state。
// 自己出錯：stderr 一行「aos-loop: 代號 原因」、退 1（同 aos-exec 的格式，N-60／P-21）。
#include "aos/loop.hpp"

#include <cstdio>
#include <exception>

static int fail(const std::string& code, const std::string& msg) {
    std::fprintf(stderr, "aos-loop: %s %s\n", code.c_str(), msg.c_str());
    std::fflush(stderr);
    return 1;
}

int main(int argc, char** argv) {
    try {
        aos::loop::block_signals();
        aos::Cli cli = aos::loop::loop_cli(std::vector<std::string>(argv + 1, argv + argc), "aos-loop");
        aos::loop::Loop loop(cli.opts, cli.rest[0], aos::loop::Defaults{});
        return loop.serve();
    } catch (const aos::Error& e) {
        return fail(e.code, e.msg);
    } catch (const std::exception& e) {
        return fail(aos::code::Internal, e.what());
    }
}
