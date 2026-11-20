// main.cpp：aos-loop 命令列——block_signals、解命令列、讀設定、Loop::serve（公開 API 見 aos/loop.hpp）。
//
//     aos-loop [--max N] [--interval-ms N] [--ctl 檔] [--state 檔] [--state-flux 檔] [--enable-logs] [--enable-counters] loop.json [-- 參數...]
//
// 唯一的位置參數就是設定檔（必給、只能一個；可寫 `檔#/指標`）；旗標放前面、規則同 aos-exec；起跑時 旗標 ＞ loop.json ＞ 預設
// （10-21 傍晚 ideas § 9）。exec＝字串或 [目標, 參數...]，每次 `aos-exec -- 目標 參數...`；max 沒寫＝不限。
// 那次的碼：0＝下一次；10＝正常停（以 0 結束）；其他非 0＝失敗，stderr 錯誤行「aos-loop: error: RunFailed run N: 誰 failed with exit code C」、以那個碼結束（11-05 D4）。
// 跑滿 max 以 0 結束、stderr 不寫（N-43）。收到 SIGINT／SIGTERM／SIGHUP：轉給正在跑的那次、等它結束，再以 128＋N 結束
// （兩次之間收到就不起下一次）。選填 interval_ms、ctl、state、state_flux。
// log（11-02；11-02 晚改預設不印）：--enable-logs 時每跑完一次在 stdout 印一行 JSON {"started_at", "counter_runs", "code", "signal", "elapsed_ms"}；
// 身體繼承同一個 stdout，混在一起由使用者自己處理。印不了（管子關了）就不印、照跑。
// `-- 參數...`（11-02 晚）：設定檔之後的附加參數，每次接在 exec 後面（字串、陣列接在最後；單子接在 argv 最後）。
// on_start／on_stop（11-11）：起來、要退時各跑一次（寫法同 exec）。on_before_run／on_after_run（11-20 hook 第 5 刀）：每跑一次身體的前後各一次，
// on_before_run 退 10＝跳過這一圈；兩個 _if＝旗標檔在才跑。四個點失敗都收工（錯誤行 PointFailed；使用者「四個點都跟著停」）。
// 11-14 B7：on_stop 多 AOS_LOOP_CAUSE（為什麼收工；daemon 送 SIGTERM 前寫的 $AOS_STACK/stop_cause.json 在這裡判讀，見 aos/loop.hpp）。
// $AOS_STACK 有設但不在＝設定讀完後先 mkdir -p（11-11，make_stack；建不了 MkdirFailed）。
// 自己出錯：stderr 一行「aos-loop: error: 代號 原因」、退 1（11-05 stdio-unify R1）。`--help`＝英文說明印 stdout、退 0（R3）。
#include "aos/loop.hpp"

#include <cstdio>
#include <exception>

static const char* HELP = R"(usage: aos-loop [FLAGS] CONFIG.json [-- ARGS...]

Run the body (CONFIG.json "exec", via aos-exec) again and again.
Each run's exit code: 0 = next run, 10 = stop (exit 0), other = stop with that code.
ARGS after -- are appended to every run's exec.
Optional CONFIG.json keys on_start / on_stop (written like exec): run once before the first run /
once when aos-loop is about to exit (stop, done, failure, signal; not SIGKILL). on_stop gets
AOS_LOOP_CODE (the exit code), AOS_LOOP_SIGNAL (signal number or empty) and AOS_LOOP_CAUSE
(stop, sleep, remove, shutdown, stuck, signal, max, body_exit or error; on SIGTERM it comes from
$AOS_STACK/stop_cause.json when the daemon wrote one for this process). Each gets on_timeout_ms
(integer >= 0; default 5000; 0 = no limit).
Optional keys on_before_run / on_after_run (written like exec, no time limit unless the inst sets
timeout_ms): run before / after each run of the body. on_before_run gets AOS_LOOP_RUNS (which run
this will be); exit 0 = run the body (ctl is read again first: a stop or pause given meanwhile
wins), 10 = skip this run (not counted, no on_after_run, try again after interval_ms), other = stop.
on_after_run gets AOS_LOOP_RUNS, AOS_LOOP_RUN_CODE, AOS_LOOP_RUN_SIGNAL (or empty) and
AOS_LOOP_RUN_MS; not run when the body could not start or aos-loop got a signal; non-zero = stop
with its code when the body exited 0 (else one warning, the body's result counts).
on_before_run_if / on_after_run_if: a file path; when given, that point runs only while the file
exists (one check per run).
A failing on_start, on_stop, on_before_run or on_after_run (non-zero, timed out, cannot run) stops
the loop: "aos-loop: error: PointFailed ..."; on_start failing = the body never runs; on_stop
failing changes the exit code only when it would have been 0.

flags:
  --max N               stop after N runs (exit 0)
  --interval-ms N       wait N ms between runs
  --ctl FILE            control window (JSON commands: pause, resume, stop, ...)
  --state FILE          state window (aos-loop writes its phase there)
  --state-flux FILE     response window (ctl sequence, warnings, response time)
  --enable-logs         print one JSON line per run to stdout
  --enable-counters     write counter_runs.txt (runs so far) next to the state window
  -h, --help            show this help

exit codes: 0 done; 1 own error ("aos-loop: error: CODE ..." on stderr);
the body's code when it fails ("aos-loop: error: RunFailed ..."); the point's code when one of
the four points fails ("aos-loop: error: PointFailed ..."); 128+N on signal N.
)";

int main(int argc, char** argv) {
    aos::loop::note_start();   // 11-14 B7：外層帶進來的 AOS_LOOP_CAUSE 清掉（只在 on_stop 期間才設）、記下自己的啟動 ticks 與 boot_id
    try {
        aos::loop::block_signals();
        aos::Cli cli = aos::loop::loop_cli(std::vector<std::string>(argv + 1, argv + argc), "aos-loop", HELP);
        aos::loop::Loop loop(cli.opts, cli.rest[0], aos::loop::Defaults{},
                             std::vector<std::string>(cli.rest.begin() + 1, cli.rest.end()));
        aos::loop::make_stack();   // 11-11：設定讀得過才建；$AOS_STACK 有設但不在＝mkdir -p
        return loop.serve();
    } catch (const aos::Error& e) {
        return aos::fail("aos-loop", e);
    } catch (const std::exception& e) {
        return aos::fail("aos-loop", aos::code::Internal, e.what());
    }
}
