# core/exec — POSIX 執行器（純函式庫，無子命令）

← [core/README](../README.md)｜協定 [PROTOCOL](../../wf/workflows/dispatch/proto/PROTOCOL.md) §2–§3｜慣例 [conventions](../../wf/workflows/common/conventions.md)

## 這個小專案做什麼

把一批 `Spawn`（argv／env／cwd／stdin／timeout）**一次全部 fork/exec**（＝回合內並行），
再**統一等完**，回傳每條的 exit 或 signal、stdout／stderr 文字、起訖時間。
兩階段 API（`start_all` → `wait_all`）是為了讓上層在「已 fork、還沒等完」時拿到 pid 寫進 `state.json`。
stdout／stderr／stdin 一律走 `mkstemp` 暫存檔而非 pipe——多 child 並行時不需要 poll 迴圈、也不會塞爆緩衝互相卡死。
只認 argv 與環境，**不帶** `$ref`／`$env`、不帶 C ABI、不寫 exit 檔。

## 公開標頭草稿：`include/aos/exec.hpp`

```cpp
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

/* 現在時刻的 ISO8601 字串（UTC，毫秒）。上層寫 state.json 也用同一種格式。 */
AOS_API std::string now_iso8601();

}  // namespace aos::exec
```

## 檔案切分（`src/`，單檔 ≤ 300 行）

分層單向：`start` / `wait_all` ← `spawn_prep`、`wait`、`tempfile`、`clock`；四個底層互不相識。

| 檔案 | 職責 | 預估行數 |
|---|---|---|
| `src/clock.hpp` / `src/clock.cpp` | `now_iso8601()`（`clock_gettime(CLOCK_REALTIME)`＋`gmtime_r`）、`monotonic_ms()`、`sleep_ms()`；`sleep_ms` 抄舊 `wait.cpp` | 15 / 70 |
| `src/tempfile.hpp` / `src/tempfile.cpp` | `make_temp(prefix, path_out) -> fd`（`$TMPDIR` 或 `/tmp`，`mkstemp`）、`write_fully`（抄舊 `exec.cpp`）、`read_file_and_unlink(path) -> string` | 20 / 90 |
| `src/spawn_prep.hpp` / `src/spawn_prep.cpp` | 抄舊 `core/inst/src/spawn_prep.*`：環境合併（只加不減、拒絕含 `=` 的 key）、PATH 解析成 `executable`、`envp` 實體化、`failure_status`（126/127）。輸入型別由 `inst_t` 改成 `Spawn` | 25 / 170 |
| `src/wait.hpp` / `src/wait.cpp` | 抄舊 `core/inst/src/wait.*`：`wait_retry`（EINTR 重試）、`wait_until(pid, limit_ms)`（WNOHANG＋指數退避 ≤ 50 ms） | 12 / 90 |
| `src/start.cpp` | `start_all`：每條先建三個暫存檔並寫入 stdin_data、`prepare_spawn`、`fork`；**child 側** `setpgid(0,0)` → dup2 三個 fd → `chdir` → `execve`（只做 async-signal-safe）；**parent 側** `setpgid(pid,pid)` 忽略 `EACCES`（雙保險，抄舊 `exec.cpp`）；填 `started_at` 與 `deadline_mono_ms` | 200 |
| `src/wait_all.cpp` | `wait_all`：單一輪詢迴圈，對每條未完成者 `waitpid(WNOHANG)`；過了 `deadline_mono_ms` 就 `kill(-pid, SIGKILL)` 再阻塞等；全部收齊後 `WIFEXITED`/`WIFSIGNALED` 拆成 `exit`/`signal`、讀暫存檔進 `stdout_text`/`stderr_text`、`unlink`、填 `ended_at` | 180 |

CMake：`aos_add_subproject(exec SOURCES … HEADERS include/aos/exec.hpp)`，沒有 `PUBLIC_DEPS`／`PRIVATE_DEPS`、沒有 `aos_add_subcommand`。

## 已知不管

- 逾時直接 `SIGKILL` 整個 group，**不做** 舊碼的 SIGTERM → 2 秒寬限 → SIGKILL 兩段式；反正協定只認 `signal: 9`。
- 子行程自己再 `setpgid` 脫離群組的話，逾時殺不到孫行程；不追。
- 暫存檔在 `wait_all` 之前被外力刪掉、或 `$TMPDIR` 塞滿 → 那條的 `error` 非空、`stdout_text` 空；不重試。
- `stdout`/`stderr` 整檔讀進記憶體，沒有上限；child 印 GB 級輸出會吃光 RAM。
- `Running` 沒等就丟掉（呼叫端忘了 `wait_all`）會留殭屍與暫存檔；沒有解構子收拾。
- 不處理 `SIGCHLD` 被呼叫端設成 `SIG_IGN` 的情況（那會讓 `waitpid` 回 `ECHILD`）。
