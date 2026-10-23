← [入口](../proto8.md)｜涵蓋：`proto8/impls/`（使用者的 C／C++ 實作）、舊 lib（10-16 那套，已刪）

> 2026-10-21 下午從 [proto8.md](../proto8.md) 逐字下放（那份超過 8 KB，照 [STRUCTURE](../../../../STRUCTURE.md)）。

### `proto8/impls/`（使用者的 C／C++ 實作；10-23 起進 git；舊快照 `backup/` 10-23 已刪）

總入口與逐專案說明在 `proto8/impls/README.md`（10-23 起進 git；各專案的 `build/`、`bin/`、`lib/` 由各自的 `.gitignore` 擋）。10-21 晚對齊 bin 版 10-21 傍晚、10-23 再對齊 bin 10-22：提供 `aos-exec`、`aos-loop`、`aos-fsm`、`aos-daemon` 四支命令列（`inst` C lib、`aos-util`、`aos-directive`、`aos-schema` 是庫）。

| 哪裡 | 負責什麼 |
|---|---|
| `aos-util/include/aos/cli.hpp`、`src/cli.cpp` | 10-21 起的命令列：`parse_cli`（旗標在位置參數前、`--x V`／`--x=V`、`--` 結束、錯＝ArgumentsBad、不認得的旗標 FlagUnknown（10-23 統合前一律 Usage）；10-22 起另收不帶值的開關表 `switches`；四支命令列共用，對應 bin 的 `aos_flags.parse`）、`load_cfg`（設定檔 `檔` 或 `檔#/指標`）。舊的 `aos/flags.hpp`（10-16～17 那代）是另一套 |
| `aos-util/include/aos/text.hpp`、`src/text.cpp` | 10-22 起：`is_utf8`、`space_at`、`lstrip`／`rstrip`／`strip`（照 Python `str.isspace` 認 Unicode 空白）；aos-exec 的 `.env`、aos-fsm 的 state 與 `next` 檢查用 |
| `aos-exec/include/aos/exec.hpp` | 公開 API 只剩 `run_cli`（等同命令列；會 chdir／setenv）、`run_inst`、`argv0`、`Result`、代號（含 `DotenvBad`、`WsMissing`；10-23 統合前叫 `EnvBad`／`EnvReadFailed`、`WorkspaceMissing`） |
| `aos-exec/src/cli/` | `run_cli`：解旗標（`--ws`、10-22 起不帶值的 `--dotenv-override`，只管這一跳、轉向時清掉）→ 一跳跳走（字串轉向＝全新的一跳）→ `launch` |
| `aos-exec/src/find/find.cpp`、`classify.cpp` | `hop`（定工作區 → `locate` → 建 stack → `enter`：cd、讀 `.env`、旗標蓋回 → 照當下 `$AOS_ENTRY` 一路往下挑入口 → 重設 `AOS_CF`／`AOS_CD`／`AOS_CO`）；`classify`（種類、沒 argv 的 JSON 物件當資料夾、`AOS_CO`、轉向繞圈） |
| `aos-exec/src/env/env.cpp`、`dotenv.cpp` | `check_ws`、`setup_stack`；`.env` 檔（`load_env`；10-22 起 dotenv 基礎子集：`export_prefix`、`env_value` 管引號／註解／去空白，預設不蓋＝`set_env` 的 `keep`）與 JSON `.env` key（`json_env`，只套蓋不蓋）、`set_env`（只展開 `${名字}`、錯不印值） |
| `aos-exec/src/launch/launch.cpp`、`src/inst/` | exec 可執行檔／argv 陣列（指示詞、argv[0] 交給 aos-exec）；inst 單子行程內交給 libaos（`run_inst`） |
| `aos-loop/src/beat/folder.cpp` | 每拍 fork 子行程呼叫 aos-exec 的 `run_cli({"--", 目標, 參數...})`、轉訊號 |
| `aos-loop/src/engine/config.cpp` | `Loop` 建構子（`load_cfg`、旗標 ＞ 設定檔 ＞ 預設）、`parse_target`（`val`＝字串或 `[目標, 參數...]`）、`loop_cli`（aos-loop、aos-daemon 共用） |
| `aos-fsm/src/table/table.cpp` | `read_table`（`load_cfg`）、`check`（10-22：開跑時查整張表，表壞 CfgBad，10-23 統合前叫 FieldType）、`pick`（state 不在表上 StateUnknown）；`val` 走 `parse_target`；trace 沒有 `timed_out` |
| `aos-fsm/src/state/state.cpp` | `read_state`（10-22：在但讀不了 StateBad〔10-23 統合前叫 ReadFailed〕、去頭尾 Unicode 空白）、`write_state`（`.state.txt` 再改名；10-23 起狀態檔是 `state.txt`）、`append_trace`（時間用 aos-util 的 `utc_now_ms`，ISO 到毫秒） |
| `aos-daemon/src/daemon/daemon.cpp` | `Daemon`：`check_loops`（10-23 統合前叫 `check_children`）、10-22 起 `taken_names`／`check_names`（子項名字跟自己的 ctl／state 撞名：起來時 CfgBad〔10-23 統合前叫 Conflict〕、ctl 撞＝不採用）、`adopt`、`tend`、`stop`、`finish` |
| `aos-daemon/src/child/child.cpp` | 子 loop 經 aos-exec 起：寫小格 `loop.json`（補 ctl／state、蓋 `_entry`、相對 run 轉絕對）、fork 後呼叫 `run_cli({"--", 小格/loop.json#/_entry})`，exec 成 PATH 上的 aos-loop |
| `aos-directive/src/resolve.cpp` | 指示詞走訪；`$path` 是字串拼接（`join_path`） |

aos-loop 的骨架是公開的 `aos::loop::Loop`（`src/engine/`），aos-daemon 繼承它（`src/daemon/`）。動工前的樣子原本備份在 `proto8/impls/backup/`（只在家中那台、不進 git），10-23 使用者授權刪掉。

### 舊 lib（10-16 那套，已刪）

`proto8/lib/`（inst、loop、daemon、fsm、agent 格庫、兩種 kernel、tasks、tick，27 支模組＋說明＋12 個測試檔 169 個）與舊 `bin/aos`、六組舊 demo（daemon、fsm、paint、kernels、tasks、tick），10-19 刪進 git 歷史；要找回：`git show 5546be29:proto8/lib/README.md`（逐檔表）。daemon 10-20 已照新做法重寫（上面 `aos-daemon`）；kernel、tasks、tick、腦的工具呼叫現無實作，待照新做法重寫（[NORMS 待定](../../../../../proto8/NORMS/08-待定.md)）。
