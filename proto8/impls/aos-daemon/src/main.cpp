// main.cpp：aos-daemon 命令列——先阻擋收工、poke 與 SIGUSR1/2 訊號，再解設定並服務。
//
//     aos-daemon [--max N] [--interval-ms N] [--ctl 檔] [--state 檔] [--state-flux 檔] [--enable-logs] [--enable-counters] daemon.json [-- 參數...]
//
// 命令列同 aos-loop（loop_cli；唯一的位置參數＝設定檔，可寫 `檔#/指標`；10-21 傍晚 ideas § 9）。
// 管一群 proc（C-36、N-28；11-03 起 loops／execs 統稱 procs）；每個 proc 的小格是它寫的 stack，沒寫＝$AOS_STACK/procs/<名字>/（P-17）。規則見 README 與 daemon/daemon.hpp。
// log（11-02；11-02 晚改預設不印）：--enable-logs 才印到 stdout——子項起來一行、結束一行；daemon 自己有身體時同 aos-loop 每跑完一次一行。
// `-- 參數...`（11-02 晚）：只接在 daemon 自己的 exec 後面（沒有 exec＝ArgumentsBad），不影響子項。
// 不論為什麼結束都先收掉所有子 loop、寫好 state 再結束；收到 SIGINT／SIGTERM／SIGHUP 以 128＋N 結束（P-36）。
// 自己出錯：stderr 一行「aos-daemon: error: 代號 原因」、退 1（11-05 stdio-unify R1）；不退出的（身體失敗／好了、窗寫不了）是提醒行
// 「aos-daemon: warning: …」（D4）。`--help`＝英文說明印 stdout、退 0（R3）。PATH 不動（子 loop 要的 aos-exec、aos-loop 由呼叫者放進 PATH）。
#include "daemon/daemon.hpp"

#include "aos/util/signals.hpp"

#include <cstdio>
#include <exception>

static const char* HELP = R"(usage: aos-daemon [FLAGS] daemon.json [-- ARGS...]

Look after a group of procs (daemon.json "procs"): start them, restart or stop them
as the ctl window says, and report them in the state windows. Optional own body
("exec") runs like aos-loop; a failing body is retried next round (warning line).
ARGS after -- are appended to the daemon's own exec.
Poke: SIGRTMIN+1/+2/+3 wake it at once to read ctl / ctl + mailbox / run a full
round early (aos-daemon-ctl poke). SIGUSR1 and SIGUSR2 are blocked.
All procs share lifecycle rules regardless of launch syntax: stop writes their public
ctl and waits (no SIGTERM fallback); sleep sends SIGTERM and keeps a sleeping row.
Natural exit 0 removes the row; known nonzero exits keep stopped with a reason
(unless auto_restart requests a restart). Shutdown sleeps all live procs for next startup.
Each proc may set either stuck_after_cycles (positive integer, default 10) or
stuck_after_ms (positive signed 64-bit integer, wall-clock milliseconds). Unanswered
control windows project phase stuck; restart_on_stuck: true restarts the proc
(unless paused), stopping after 3 consecutive stuck runs without a response.

flags:
  --max N               stop after N rounds
  --interval-ms N       wait N ms between rounds (default 200)
  --ctl FILE            control window
  --state FILE          stable state window
  --state-flux FILE     response window
  --enable-logs         print JSON lines for proc start/end/stuck restart and body runs
  --enable-counters     write counter_runs.txt (runs so far) next to the state window
  -h, --help            show this help

exit codes: 0 done; 1 own error ("aos-daemon: error: CODE ..." on stderr); 128+N on signal N.
)";

int main(int argc, char** argv) {
    try {
        aos::block_signals();
        sigset_t blocked = aos::daemon::poke_signals();
        sigaddset(&blocked, SIGUSR1);
        sigaddset(&blocked, SIGUSR2);
        aos::block_more(blocked);
        aos::Cli cli = aos::loop::loop_cli(std::vector<std::string>(argv + 1, argv + argc), "aos-daemon", HELP, "daemon.json");
        aos::daemon::Daemon d(cli.opts, cli.rest[0], std::vector<std::string>(cli.rest.begin() + 1, cli.rest.end()));
        return d.serve();
    } catch (const aos::Error& e) {
        return aos::fail("aos-daemon", e);
    } catch (const std::exception& e) {
        return aos::fail("aos-daemon", aos::code::Internal, e.what());
    }
}
