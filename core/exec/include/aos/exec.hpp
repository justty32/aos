#pragma once

#include <aos/export.h>

#include <cstdint>
#include <map>
#include <string>
#include <vector>

#include <sys/types.h>

namespace aos::exec {

/* 一條要跑的指令。欄位語意照 PROTOCOL §2；id 不在這層，上層自己對號。 */
struct Spawn {
    std::vector<std::string> argv;              // 必填；argv[0] 走 PATH
    std::map<std::string, std::string> env;     // 只加不減，疊在本行程環境上
    std::string cwd;                            // 空＝不 chdir
    std::string stdin_data;                     // 先寫暫存檔再 dup2 到 fd 0
    std::uint64_t timeout_ms = 0;               // 0＝不限
};

/* 已 fork、尚未等完的一條。普通 struct，欄位攤開，上層可直接讀 pid 寫 state。 */
struct Running {
    pid_t pid = -1;                             // -1＝沒 fork 起來，看 error
    std::string started_at;                     // ISO8601（UTC，毫秒）
    std::string stdin_path;                     // 三個暫存檔；wait_all 讀完即 unlink
    std::string stdout_path;
    std::string stderr_path;
    std::uint64_t timeout_ms = 0;
    std::uint64_t deadline_mono_ms = 0;         // CLOCK_MONOTONIC 絕對截止；0＝不限
    std::string error;                          // 非空＝start 階段就失敗（fork/mkstemp）
};

/* 等完之後的結果。欄位語意照 PROTOCOL §3。 */
struct Result {
    int exit = 0;                               // signal == 0 時才有意義
    int signal = 0;                             // 0＝正常結束；逾時被殺＝9
    std::string stdout_text;
    std::string stderr_text;
    std::string started_at;
    std::string ended_at;
    pid_t pid = -1;
    std::string error;                          // 空＝成功；否則 exit/signal 不可信
};

/* 一次 fork 完全部，順序與輸入一一對應。任一條失敗只填該條的 error，不影響其他條。 */
AOS_API std::vector<Running> start_all(const std::vector<Spawn> &spawns);

/* 統一等完全部（含逾時：SIGKILL 整個 process group），讀回暫存檔、unlink。
 * 順序與輸入一一對應；呼叫後 running[i] 的暫存檔路徑即失效。 */
AOS_API std::vector<Result> wait_all(std::vector<Running> &running);

/* 對目前這個行程「已經 fork、還沒收線」的每一條子行程群組送出 signal_number。
 * 只呼叫 kill(2)，async-signal-safe，可以在 signal handler 裡呼叫。
 * 回傳實際送出的條數。 */
AOS_API int interrupt_running(int signal_number);

/* 現在時刻的 ISO8601 字串（UTC，毫秒）。上層寫 state.json 也用同一種格式。 */
AOS_API std::string now_iso8601();

}  // namespace aos::exec
