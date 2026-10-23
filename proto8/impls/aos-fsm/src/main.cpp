// main.cpp：aos-fsm 命令列——一拍只跑一格（N-36）。
//
//     aos-fsm [旗標] 設定檔.json
//
//   block_signals → 命令列（目前沒有旗標；唯一的位置參數＝設定檔，可寫 `檔#/指標`；10-21 傍晚 ideas § 9）→ 要 AOS_STACK →
//   read_table → check（開跑時查整張表，10-22）→ read_state（在但讀不了＝StateBad，10-22）→ pick → run_beat（aos-loop 的公開 API：子行程 `aos-exec -- 目標 參數...`）
//   → append_trace → 格的碼 0 才 write_state(next) → 以格的碼結束
//
// val＝字串或 [目標, 參數...]（相對路徑從 cwd 算，fsm 不轉）；物件＝表壞（要內嵌單子寫 fsm.json#/states/<名>/body）。
// 只看格的結束碼：不讀格的 stdout、不轉述格的 stderr（N-38）。格非 0（含 10）＝state 不動、原碼往上。
// trace 一行 {"at","state","code","signal","elapsed_ms"}（at＝ISO 8601 UTC 到毫秒），沒有 timed_out（fsm 看不到格裡有沒有逾時，C-52；10-21 plan F4）。
// 收到 SIGINT／SIGTERM／SIGHUP：轉給那格、等它結束，trace 與 state 照常寫完，再以 128＋N 結束（P-36）。
// 自己出錯：stderr 一行「aos-fsm: 代號 原因」、退 1（N-38、N-60）。
#include "aos/files.hpp"
#include "aos/proc.hpp"
#include "aos/loop.hpp"

#include "state/state.hpp"
#include "table/table.hpp"

#include <cstdio>
#include <cstdlib>
#include <exception>

static const char* USAGE = "usage: aos-fsm [旗標] 設定檔.json";   // 旗標表是空的也寫 [旗標]（同 bin，10-22）

static int fail(const std::string& code, const std::string& msg) {
    std::fprintf(stderr, "aos-fsm: %s %s\n", code.c_str(), msg.c_str());
    std::fflush(stderr);
    return 1;
}

int main(int argc, char** argv) {
    namespace fsm = aos::fsm;
    try {
        aos::loop::block_signals();
        aos::Cli cli;
        try {
            cli = aos::parse_cli(std::vector<std::string>(argv + 1, argv + argc), {});   // 目前沒有旗標；以後加就在這裡加一列
        } catch (const aos::Error& e) {
            throw aos::Error{e.code, std::string(USAGE) + "（" + e.msg + "）"};   // FlagUnknown／ArgumentsBad
        }
        if (cli.rest.size() != 1) {
            std::string why = "沒有設定檔";
            if (!cli.rest.empty()) {
                why = "設定檔只能一個，多給了 " + cli.rest[1];
            }
            throw aos::Error{fsm::code::ArgumentsBad, std::string(USAGE) + "（" + why + "）"};
        }
        const char* s = std::getenv("AOS_STACK");
        if (s == nullptr || s[0] == '\0') {
            throw aos::Error{fsm::code::StackMissing, "沒設定 AOS_STACK"};
        }
        std::string stack = s;
        fsm::Table table = fsm::read_table(cli.rest[0]);
        std::map<std::string, fsm::Cell> cells = fsm::check(table);   // 10-22：開跑時查整張表，哪一格壞都不跑
        std::string state = fsm::read_state(stack, table.start);
        fsm::Cell cell = fsm::pick(cells, state, aos::join(stack, "state"));

        int sig = aos::loop::take_signal();
        if (sig != 0) {
            return 128 + sig;
        }
        std::string at = aos::utc_now_ms();
        aos::loop::Beat b;
        try {
            b = aos::loop::run_beat(cell.val.target, cell.val.args);
        } catch (const aos::Error& e) {
            throw aos::Error{e.code, "狀態 " + state + "：" + e.msg};
        }

        aos::Json line = aos::Json::object();
        line["at"] = at;
        line["state"] = state;
        line["code"] = b.code;
        line["signal"] = nullptr;
        if (b.signal != 0) {
            line["signal"] = b.signal;
        }
        line["elapsed_ms"] = b.elapsed_ms;
        fsm::append_trace(stack, line);
        if (b.code == 0) {
            fsm::write_state(stack, cell.next);
        }
        if (b.received != 0) {
            return 128 + b.received;
        }
        return b.code;
    } catch (const aos::Error& e) {
        return fail(e.code, e.msg);
    } catch (const std::exception& e) {
        return fail(fsm::code::Internal, e.what());
    }
}
