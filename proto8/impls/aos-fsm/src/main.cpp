// main.cpp：aos-fsm 命令列——一次只跑一格（N-36）。
//
//     aos-fsm [旗標] 設定檔.json
//
//   aos-util block_signals → 命令列（目前沒有旗標；唯一的位置參數＝設定檔，可寫 `檔#/指標`；10-21 傍晚 ideas § 9）→ 要 AOS_STACK →
//   read_table → check（開跑時查整張表，10-22）→ make_stack（11-11：$AOS_STACK 有設但不在就 mkdir -p）→ read_state（在但讀不了＝StateBad，10-22）→ pick → run_once（aos-loop 的公開 API：目標＝子行程 `aos-exec -- 目標 參數...`；單子＝行程內 run_inst，10-24）
//   → next_for（照格的碼查表）→ 查到才 write_state → 查到退 0、沒查到以格的碼結束（11-03 起不寫 trace.jsonl，使用者「整個拿掉」）
//
// next 兩種寫法（10-30 N-36 改口）：字串＝格退 0 才換（其他碼 state 不動、以那個碼退）；物件 {結束碼: 狀態名}＝格退 c，表上有 "c"
// （或沒有但有 "*"）就寫進 state、fsm 退 0；查不到＝state 不動、以 c 退。
// exec＝字串或 [目標, 參數...]（相對路徑從 cwd 算，fsm 不轉）；物件＝內嵌單子（10-24 恢復；行程內 aos-exec 的 run_inst，
// 跑的期間 AOS_CF＝fsm.json、AOS_CO＝/states/<名>/exec，相對路徑從 fsm.json 的資料夾算；單子壞＝「aos-fsm: EntryBad 狀態 X：單子跑不起來：…」退 1、state 不動）。
// 單子被逾時收掉：格的碼 128＋N。
// 只看格的結束碼：不讀格的 stdout、不轉述格的 stderr（N-38）。表上沒接住的碼（字串 next 的非 0，含 10）＝state 不動、原碼往上。
// 收到 SIGINT／SIGTERM／SIGHUP：轉給那格、等它結束，state 照表寫完（含分岔），再以 128＋N 結束（P-36、N-38）。
// 自己出錯：stderr 一行「aos-fsm: error: 代號 原因」、退 1（11-05 stdio-unify R1）。`--help`＝英文說明印 stdout、退 0（R3）。
#include "aos/util/files.hpp"
#include "aos/util/proc.hpp"
#include "aos/util/signals.hpp"
#include "aos/loop.hpp"

#include "state/state.hpp"
#include "table/table.hpp"

#include <cstdio>
#include <cstdlib>
#include <exception>
#include <optional>

static const char* USAGE = "aos-fsm [FLAGS] CONFIG.json";   // 旗標表是空的也寫 [旗標]（10-22）

static const char* HELP = R"(usage: aos-fsm [FLAGS] CONFIG.json

Run one step of the state table in CONFIG.json ({"start", "states"}): read the
state from $AOS_STACK/stage.txt (none = "start"), run that state's exec once, then
look up the next state by its exit code ("next": a name = only on 0;
{"CODE": name, "*": name}).

flags:
  -h, --help   show this help

exit codes: 0 the table took the code (state written); 1 own error
("aos-fsm: error: CODE ..." on stderr); otherwise the step's own code (state unchanged);
128+N on signal N.
)";

int main(int argc, char** argv) {
    namespace fsm = aos::fsm;
    try {
        aos::block_signals();
        aos::Cli cli;
        try {
            cli = aos::parse_cli(std::vector<std::string>(argv + 1, argv + argc), {}, {}, HELP);   // 目前沒有旗標；以後加就在這裡加一列
        } catch (const aos::Error& e) {
            throw aos::usage_error(e.code, e.msg, USAGE);   // FlagUnknown／ArgumentsBad
        }
        if (cli.rest.size() != 1) {
            std::string why = "missing config file";
            if (!cli.rest.empty()) {
                why = "only one config file allowed, got extra " + cli.rest[1];
            }
            throw aos::usage_error(fsm::code::ArgumentsBad, why, USAGE);
        }
        const char* s = std::getenv("AOS_STACK");
        if (s == nullptr || s[0] == '\0') {
            throw aos::Error{fsm::code::StackMissing, "AOS_STACK is not set"};
        }
        std::string stack = s;
        fsm::Table table = fsm::read_table(cli.rest[0]);
        std::map<std::string, fsm::Cell> cells = fsm::check(table);   // 10-22：開跑時查整張表，哪一格壞都不跑
        aos::loop::make_stack();   // 11-11：表查過才建；$AOS_STACK 有設但不在＝mkdir -p（建不了 MkdirFailed）
        std::string state = fsm::read_state(stack, table.start);
        fsm::Cell cell = fsm::pick(cells, state, aos::join(stack, "stage.txt"));

        int sig = aos::take_signal();
        if (sig != 0) {
            return 128 + sig;
        }
        aos::loop::Run b;
        try {
            b = aos::loop::run_once(cell.exec);
        } catch (const aos::Error& e) {
            throw aos::Error{e.code, "state " + state + ": " + e.msg};
        }

        std::optional<std::string> next = fsm::next_for(cell, b.code);   // 10-30 N-36：照表查，查不到＝state 不動
        if (next) {
            fsm::write_state(stack, *next);
        }
        if (b.received != 0) {
            return 128 + b.received;   // fsm 自己收到訊號：照表寫完 state（含分岔），仍以 128＋N 結束（N-38、P-36）
        }
        if (next) {
            return 0;   // 表上接住了這個碼＝這一步照表走了（字串 next 只接 0；每層只說自己，N-43）
        }
        return b.code;   // 沒接住：透明轉交
    } catch (const aos::Error& e) {
        return aos::fail("aos-fsm", e);
    } catch (const std::exception& e) {
        return aos::fail("aos-fsm", fsm::code::Internal, e.what());
    }
}
