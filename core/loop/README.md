# core/loop — 匯聚、並行執行、loop state（子命令 `run`、`deliver`）

← [core/README](../README.md)｜協定 [PROTOCOL](../../wf/workflows/dispatch/proto/PROTOCOL.md) §1、§4–§6｜慣例 [conventions](../../wf/workflows/common/conventions.md)

## 這個小專案做什麼

推進一個資料夾的世界：每回合把 `.aos/inbox/*.json` **搬**進 `batch/<turn>/insts/`，再把
`.aos/every/*.json` **複製**成 `<stem>-<turn>.json`，用 `aos::exec`
一次 fork 全部（並行），fork 完先寫一次 `state.json`（`running[]` 帶 pid），等完再寫 `out/<id>.json`
與第二次 `state.json`，然後 `turn` +1。`every/` 的原檔不搬走；檔案可用正整數 `every_ms`
限制投遞間隔，未設定或值 ≤ 0 時仍是每回合投遞。上次投遞的 epoch 毫秒記在
`.aos/every/.last/<stem>`；
`aos deliver` 寫 `<id>.json.tmp` 再 `rename` 發佈到 inbox。
相依 `aos::exec`（fork/wait）與 `aos::wire`（JSON），本層自己只管路徑、檔案系統與回合順序。

## 公開標頭草稿：`include/aos/loop.hpp`

```cpp
#pragma once

#include <aos/export.h>
#include <aos/exec.hpp>
#include <aos/wire.hpp>

#include <cstddef>
#include <cstdint>
#include <map>
#include <string>
#include <vector>

namespace aos::loop {

/* ---- layout：<folder>/.aos/ 的路徑推導，不碰檔案系統（ensure 除外） ---- */
struct Layout {
    std::string folder;       // 絕對路徑（realpath 後）
    std::string aos;          // <folder>/.aos
    std::string inbox;        // .aos/inbox
    std::string every;        // .aos/every
    std::string turn_file;    // .aos/turn
    std::string state_file;   // .aos/state.json
    std::string agents_dir;   // .aos/agents
};
AOS_API Layout layout_of(const std::string &folder);
AOS_API std::string find_folder(const std::string &start);
AOS_API std::string current_folder();
AOS_API std::string insts_dir(const Layout &layout, std::uint64_t turn);   // .aos/batch/<turn>/insts
AOS_API std::string out_dir(const Layout &layout, std::uint64_t turn);     // .aos/batch/<turn>/out
/* mkdir -p .aos/inbox、.aos/every、.aos/agents；turn 檔不存在就寫 "1"。deliver 與 run 都會呼叫。 */
AOS_API bool ensure_layout(const Layout &layout, std::string &error);
AOS_API std::uint64_t read_turn(const Layout &layout);                     // 讀不到＝1
AOS_API bool write_turn(const Layout &layout, std::uint64_t turn, std::string &error);

/* ---- deliver：原子投遞進 inbox/<id>.json（先 .json.tmp 再 rename） ---- */
AOS_API bool deliver(const Layout &layout, const wire::Inst &inst, std::string &error);
/* 從 argv 現做一份 Inst，id 由 make_delivery_id() 產生。 */
AOS_API wire::Inst inst_from_argv(const std::vector<std::string> &argv);
AOS_API std::string make_delivery_id();        // "d-<epoch_ms>-<pid>-<seq>"

/* ---- aggregate：inbox 搬入、到期的 every 複製入 batch/<turn>/insts/ ---- */
AOS_API std::vector<wire::Inst> aggregate(const Layout &layout, std::uint64_t turn,
                                          std::string &error,
                                          std::size_t *every_count = nullptr);
AOS_API bool every_due(const Layout &layout, const std::string &stem,
                       std::int64_t every_ms, std::int64_t now_ms);
AOS_API bool mark_every_delivered(const Layout &layout, const std::string &stem,
                                  std::int64_t now_ms, std::string &error);

/* ---- state：組 state.json 並原子寫出 ---- */
AOS_API std::map<std::string, std::string> mirror_agents(const Layout &layout);  // agents/*/status.json 原文
AOS_API bool write_state(const Layout &layout, const wire::State &state, std::string &error);

/* ---- turn：一回合 ---- */
struct InstFailure {
    std::string id;
    int exit = 0;
    int signal = 0;
    std::string argv0;
    std::string stderr_line;          // stderr 第一行非空白內容，可能為空
};

struct TurnSummary {
    std::uint64_t turn = 0;          // 這回合的編號
    std::size_t count = 0;           // 執行了幾條；0＝idle 回合
    std::size_t every_count = 0;     // 其中有幾條來自 every/
    std::uint64_t elapsed_ms = 0;
    std::vector<InstFailure> failures; // 非零 exit／signal；exit 75 不列入
};
/* 匯聚 → start_all → 寫 state(running) → wait_all → 寫 out/ → 寫 state(idle) → turn+1。
 * inbox 與 every 都空：不建 batch/<turn>/，但 state.json 照寫、turn 照加。 */
AOS_API bool run_turn(const Layout &layout, TurnSummary &summary, std::string &error);

}  // namespace aos::loop
```

## 檔案切分（`src/`）

分層單向：`layout` ← `deliver` ← `aggregate` ← `turn` ← `cli`。`fs` 是最底層的檔案系統小工具，誰都可以用、它不認得任何人。

| 檔案 | 職責 | 預估行數 |
|---|---|---|
| `src/fs.hpp` / `src/fs.cpp` | 內部：`read_file`、`write_atomic(path, text)`（寫 `path + ".tmp"` 再 `rename`）、`mkdir_p`（失敗時保留實際系統原因）、`list_json_files(dir)`（排序過）、`realpath_of`、`join`、`basename_sans_json` | 25 / 130 |
| `src/layout.cpp` | `layout_of`、`find_folder`、`current_folder`、`insts_dir`、`out_dir`、`ensure_layout`（建 inbox/every/agents）、`read_turn`、`write_turn`（turn 檔也走 `write_atomic`） | 110 |
| `src/deliver.cpp` | `deliver`（呼叫 `ensure_layout` → `wire::to_json_text` → `write_atomic(inbox/<id>.json)`）、`inst_from_argv`、`make_delivery_id` | 70 |
| `src/aggregate.cpp` | `aggregate`：先 `rename` inbox，再依 `every_ms` 與 `.last/<stem>` 判斷並複製到期的 every，強制 id＝`<stem>-<turn>`；`every_due`／`mark_every_delivered` 提供可注入時間的判斷與紀錄；解析失敗印 stderr 一行並保留 insts 現場 | 150 |
| `src/state.hpp` / `src/state.cpp` | `mirror_agents`（列 `agents_dir` 的每個子目錄，讀 `status.json` 原文）、`write_state`（`wire::to_json_text(State)` → `write_atomic`）；內部 helper `detail::running_entries(insts, runnings)` 與 `detail::mark_done(entries, results)` 宣告在 `state.hpp`，只給 `turn.cpp` 用 | 16 / 73 |
| `src/turn.cpp` | `run_turn`：`ensure_layout` → `read_turn` → `aggregate`（同步填 `TurnSummary.every_count`）→ 把每條 `Inst` 換成 `exec::Spawn`（`cwd` 相對 folder 轉絕對、空＝folder；注入 `AOS_FOLDER`、`AOS_TURN` 覆蓋同名 key）→ `start_all` → `write_state(phase=running)` → `wait_all` → 每條寫 `out/<id>.json`（`wire::Outcome`）→ 收集非零 exit／signal 的 `InstFailure`（exit 75 除外）→ `write_state(phase=idle, status=done)` → `write_turn(turn+1)`。idle 回合直接跳到最後兩步 | 220 |
| `src/run.cpp` | `extern "C" int aos_run_cli_main`：完整 help、明確 folder 驗證、重複旗標採第一個、`run.lock` 單 runner 鎖與 SIGINT／SIGTERM 收線；迴圈 `run_turn` 並逐條印失敗，任一 inst 失敗最後回 1，中斷寫 `phase=interrupted` 並回 130 | 340 |
| `src/deliver_cli.cpp` | `extern "C" int aos_deliver_cli_main`：完整 help（遇 `--` 停止掃描）；`[folder] -- <argv...>` 走 `inst_from_argv`，`[folder] <inst.json>` 讀檔 `parse_inst(default_id＝檔名去 .json)`，再 `deliver` | 140 |
| `tests/test_idle.cpp` | inbox 與 every 都空時驗 idle state、不建 batch 與 turn +1 | 30 |
| `tests/test_every.cpp` | every 三回合常駐執行、強制 id、與 inbox 同回合並存，以及 `every_ms` 到期邊界、跳過回合與各檔獨立節奏 | 150 |
| `tests/test_folder.cpp` | `find_folder` 往上找最近世界與找不到的情形 | 30 |
| `tests/test_run_cli.cpp` | 回歸明確 folder 驗證、inst 失敗摘要／退出碼、run 鎖、重複旗標與 run／deliver help。 | 165 |

## CLI

```text
aos run [folder] [--step N] [--interval MS]
aos deliver [folder] <inst.json>
aos deliver [folder] -- <argv...>
```

`folder` 省略時先用 `AOS_FOLDER`；沒有的話從 cwd 往上找最近含 `.aos/` 的目錄，
再找不到就用 cwd。`aos deliver` 不會寫 `every/`；常駐指令由生產者自行發佈到 `.aos/every/`。
常駐 JSON 的正整數 `every_ms` 只限制該檔的投遞頻率；不存在、不是整數或值 ≤ 0 都維持每回合投遞。

`aos run` 若明確收到 folder，會先確認其存在且為資料夾，不會替打錯的路徑建立空世界；
整段執行期間持有 `<folder>/.aos/run.lock` 的非阻塞獨佔鎖。同一世界已有 runner 時回 1。
`--step`／`--interval` 重複時會警告並沿用第一個值。每條非零 exit／signal 都印到 stderr，
exit 127 會指出找不到的 `argv[0]`，而 exit 75 視為 `waiting-llm` 回壓、不算失敗；任何其他
inst 失敗會讓整次 run 最後回 1。SIGINT／SIGTERM 會向尚未收線的行程群組送 SIGTERM，
把 state phase 寫成 `interrupted`、印出中斷訊息並回 130。兩支子命令的 `-h`／`--help`
都把完整用法印到 stdout 並回 0；deliver 的 `--` 之後不再把 `--help` 當自身選項。

CMake（`PUBLIC_DEPS` 不是 `PRIVATE_DEPS`，理由見 `wf/salvage/05-程式碼哪些值得抄.md` §六）：

```cmake
aos_add_subproject(loop
    SOURCES src/fs.cpp src/layout.cpp src/deliver.cpp src/aggregate.cpp src/state.cpp src/turn.cpp
    HEADERS include/aos/loop.hpp
    PUBLIC_DEPS aos::exec aos::wire
)
add_library(aos_loop_cli OBJECT src/run.cpp src/deliver_cli.cpp)
target_link_libraries(aos_loop_cli PUBLIC aos::loop)
aos_add_subcommand(NAME run     ENTRY aos_run_cli_main     LIBRARY aos_loop_cli SUMMARY "推進一個資料夾 N 回合")
aos_add_subcommand(NAME deliver ENTRY aos_deliver_cli_main LIBRARY aos_loop_cli SUMMARY "把一條指令原子投遞進 inbox")
```

## 已知不管

- 沒有 `.runi`／崩潰恢復：SIGINT／SIGTERM 會收線並記 `interrupted`，但行程遭 SIGKILL 或崩潰時，`insts/` 可能已搬走而 `out/` 沒寫、`turn` 沒加；下次啟動不會補跑。
- 不 `fsync`：`rename` 是原子，但斷電後檔案內容可能是空的。
- `agents/*/status.json` 只在寫 state 的那兩個時間點讀一次；agent 在回合中途更新不會即時反映。
- inbox 或 every 裡解析失敗的檔案：進 `insts/` 後跳過，`out/` 不會有對應結果，只在 stderr 留一行。
- `aos deliver` 給的 `id` 若撞到 inbox 既有檔案，直接覆蓋（`rename` 語意），不查重。
