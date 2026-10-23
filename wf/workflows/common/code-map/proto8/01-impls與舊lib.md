← [入口](../proto8.md)｜涵蓋：`proto8/impls/`（使用者的 C／C++ 實作）、舊 lib（10-16 那套，已刪）

> 2026-10-21 下午從 [proto8.md](../proto8.md) 逐字下放（那份超過 8 KB，照 [STRUCTURE](../../../../STRUCTURE.md)）。

### `proto8/impls/`（使用者的 C／C++ 實作；10-23 起進 git，`backup/` 不進）

總入口與逐專案說明在 `proto8/impls/README.md`（10-23 起進 git；各專案的 `build/`、`bin/`、`lib/` 由各自的 `.gitignore` 擋，`proto8/impls/.gitignore` 擋 `backup/`）。10-21 晚對齊 bin 版 10-21 傍晚：提供 `aos-exec`、`aos-loop`、`aos-fsm`、`aos-daemon` 四支命令列（`inst` C lib、`aos-util`、`aos-directive`、`aos-schema` 是庫）。

| 哪裡 | 負責什麼 |
|---|---|
| `aos-util/include/aos/cli.hpp`、`src/cli.cpp` | 10-21 起的命令列：`parse_cli`（旗標在位置參數前、`--x V`／`--x=V`、`--` 結束、錯＝Usage；四支命令列共用，對應 bin 的 `aos_flags.parse`）、`load_cfg`（設定檔 `檔` 或 `檔#/指標`）。舊的 `aos/flags.hpp`（10-16～17 那代）是另一套 |
| `aos-exec/include/aos/exec.hpp` | 公開 API 只剩 `run_cli`（等同命令列；會 chdir／setenv）、`run_inst`、`argv0`、`Result`、代號（含 `EnvBad`、`EnvReadFailed`） |
| `aos-exec/src/cli/` | `run_cli`：解旗標（只有 `--ws`）→ 一跳跳走（字串轉向＝全新的一跳）→ `launch` |
| `aos-exec/src/find/find.cpp`、`classify.cpp` | `hop`（定工作區 → `locate` → 建 stack → `enter`：cd、讀 `.env`、旗標蓋回 → 照當下 `$AOS_ENTRY` 一路往下挑入口 → 重設 `AOS_CF`／`AOS_CD`／`AOS_CO`）；`classify`（種類、沒 argv 的 JSON 物件當資料夾、`AOS_CO`、轉向繞圈） |
| `aos-exec/src/env/env.cpp`、`dotenv.cpp` | `check_ws`、`setup_stack`；`.env` 檔（`load_env`）與 JSON `.env` key（`json_env`）、`set_env`（只展開 `${名字}`、錯不印值） |
| `aos-exec/src/launch/launch.cpp`、`src/inst/` | exec 可執行檔／argv 陣列（指示詞、argv[0] 交給 aos-exec）；inst 單子行程內交給 libaos（`run_inst`） |
| `aos-loop/src/beat/folder.cpp` | 每拍 fork 子行程呼叫 aos-exec 的 `run_cli({"--", 目標, 參數...})`、轉訊號 |
| `aos-loop/src/engine/config.cpp` | `Loop` 建構子（`load_cfg`、旗標 ＞ 設定檔 ＞ 預設）、`parse_target`（`run`／`val`＝字串或 `[目標, 參數...]`）、`loop_cli`（aos-loop、aos-daemon 共用） |
| `aos-fsm/src/table/table.cpp` | `read_table`（`load_cfg`）、`pick`（`val` 走 `parse_target`）；trace 沒有 `timed_out` |
| `aos-daemon/src/child/child.cpp` | 子 loop 經 aos-exec 起：寫小格 `loop.json`（補 ctl／state、蓋 `_exec`、相對 run 轉絕對）、fork 後呼叫 `run_cli({"--", 小格/loop.json#/_exec})`，exec 成 PATH 上的 aos-loop |
| `aos-directive/src/resolve.cpp` | 指示詞走訪；`$path` 是字串拼接（`join_path`） |

aos-loop 的骨架是公開的 `aos::loop::Loop`（`src/engine/`），aos-daemon 繼承它（`src/daemon/`）。動工前的樣子備份在 `proto8/impls/backup/2026-10-21-night/`（更早的在 `backup/aos-impls-2026-10-21-pre-align.tar.gz`；`backup/` 只在家中那台、不進 git）。

### 舊 lib（10-16 那套，已刪）

`proto8/lib/`（inst、loop、daemon、fsm、agent 格庫、兩種 kernel、tasks、tick，27 支模組＋說明＋12 個測試檔 169 個）與舊 `bin/aos`、六組舊 demo（daemon、fsm、paint、kernels、tasks、tick），10-19 刪進 git 歷史；要找回：`git show 5546be29:proto8/lib/README.md`（逐檔表）。daemon 10-20 已照新做法重寫（上面 `aos-daemon`）；kernel、tasks、tick、腦的工具呼叫現無實作，待照新做法重寫（[NORMS 待定](../../../../../proto8/NORMS/08-待定.md)）。
