← [入口](../proto8.md)｜涵蓋：`proto8/impls/`（使用者的 C／C++ 實作）、舊 lib（10-16 那套，已刪）

> 2026-10-21 下午從 [proto8.md](../proto8.md) 逐字下放（那份超過 8 KB，照 [STRUCTURE](../../../../STRUCTURE.md)）。

### `proto8/impls/`（使用者的 C／C++ 實作；10-23 起進 git；舊快照 `backup/` 10-23 已刪）

總入口與逐專案說明在 `proto8/impls/README.md`（10-23 起進 git；各專案的 `build/`、`bin/`、`lib/` 由各自的 `.gitignore` 擋）。10-21 晚對齊 bin 版 10-21 傍晚、10-23 再對齊 bin 10-22：提供 `aos-exec`、`aos-loop`、`aos-fsm`、`aos-daemon` 四支命令列（`inst` C lib、`aos-util`、`aos-directive`、`aos-schema` 是庫）。**10-23 起是唯一實作**（使用者「python版本可以刪掉了。aos-exec/loop/daemon都用C++」，fsm 也改 C++、tick 先留 Python；bin 版這四支刪了，只剩 `proto8/bin/aos-tick`）；`proto8/tests` 與 `proto8/demo/run.sh` 都跑這四支的 `bin/`（要先建，見 [testing](../../../testing.md)）。下表「對應 bin 的 …」指 10-23 前的 Python 版。

| 哪裡 | 負責什麼 |
|---|---|
| `aos-util/include/aos/cli.hpp`、`src/cli.cpp` | 10-21 起的命令列：`parse_cli`（旗標在位置參數前、`--x V`／`--x=V`、`--` 結束、錯＝ArgumentsBad、不認得的旗標 FlagUnknown（10-23 統合前一律 Usage）；10-22 起另收不帶值的開關表 `switches`；四支命令列共用，對應 bin 的 `aos_flags.parse`）、`load_cfg`（設定檔 `檔` 或 `檔#/指標`）。舊的 `aos/flags.hpp`（10-16～17 那代）是另一套 |
| `aos-util/include/aos/text.hpp`、`src/text.cpp` | 10-22 起：`is_utf8`、`space_at`、`lstrip`／`rstrip`／`strip`（照 Python `str.isspace` 認 Unicode 空白）；aos-exec 的 `.env`、aos-fsm 的 state 與 `next` 檢查用 |
| `aos-util/include/aos/error.hpp`、`proc.hpp`（`src/proc.cpp`） | 全家共用的錯誤代號 `aos::code`（10-30 加投遞的 `CommandUnknown`、`MailboxMissing`、`LetterMissing`、`LetterBad`，原本 aos-post、aos-lock、aos-json、aos-llm-kernel 各定一份）；子程序與 /proc、`utc_now_ms`；10-30 加 `utc_now_ns`、`utc_ms_at` 與**信號** `unique_id`（`<UTC 奈秒 20 位>.<pid>.<started_at_ticks>`，原本 kernel、aos-post、aos-lock 三份；medium-plan 實作時代定 12） |
| `aos-exec/include/aos/exec.hpp` | 公開 API 只剩 `run_cli`（等同命令列；會 chdir／setenv）、`run_inst`、`argv0`、`Result`、代號（含 `DotenvBad`、`WsMissing`；10-23 統合前叫 `EnvBad`／`EnvReadFailed`、`WorkspaceMissing`） |
| `aos-exec/src/cli/` | `run_cli`：解旗標（`--ws`、10-22 起不帶值的 `--dotenv-override`，只管這一跳、轉向時清掉）→ 一跳跳走（字串轉向＝全新的一跳）→ `launch` |
| `aos-exec/src/find/find.cpp`、`classify.cpp` | `hop`（定工作區 → `locate` → 建 stack → `enter`：cd、讀 `.env`、旗標蓋回 → 照當下 `$AOS_ENTRY` 一路往下挑入口 → 重設 `AOS_CF`／`AOS_CD`／`AOS_CO`）；`classify`（種類、沒 argv 的 JSON 物件當資料夾、`AOS_CO`、轉向繞圈） |
| `aos-exec/src/env/env.cpp`、`dotenv.cpp` | `check_ws`、`setup_stack`；`.env` 檔（`load_env`；10-22 起 dotenv 基礎子集：`export_prefix`、`env_value` 管引號／註解／去空白，預設不蓋＝`set_env` 的 `keep`）與 JSON `.env` key（`json_env`，只套蓋不蓋）、`set_env`（只展開 `${名字}`、錯不印值） |
| `aos-exec/src/launch/launch.cpp`、`src/inst/` | exec 可執行檔／argv 陣列（指示詞、argv[0] 交給 aos-exec）；inst 單子行程內交給 libaos（`run_inst`） |
| `aos-loop/src/run/folder.cpp` | 每次 fork 子行程呼叫 aos-exec 的 `run_cli({"--", 目標, 參數...})`、轉訊號 |
| `aos-loop/src/run/inline.cpp`、`run.cpp` | 10-24：`run_once(Target)` 分流——目標交給 `run_folder`；單子物件交給 `run_inline`：`AOS_CF`／`AOS_CD`／`AOS_CO` 設成單子的位置、相對 `AOS_WS`／`AOS_STACK` 轉絕對（跑完還原）、行程內 aos-exec 的 `run_inst`（[thinking 10-24](../../../../../proto8/thinking/2026-10-24-exec-relative.md#10-24-exec-直接放單子)）；捷徑設定檔＝`config_file` |
| `aos-loop/src/engine/loop.cpp`、`window.cpp` | 每次怎麼走（10-23：沒有 `exec` 時一輪只 tend 一次、只寫一份 state）、窗（`read_ctl` 先解指示詞、解不開＝不採用，子類別 `check_ctl` 可填 `ctl_note_` 進 `ctl_warning`；`write_state`＝state 窗＋子類別的 `write_more`〔10-29，同一份心跳、沒開 state 也呼叫〕、`beat`＝離上一份滿 1 秒就再寫） |
| `aos-loop/src/engine/config.cpp` | `resolve_keys`（10-23 晚：設定檔與 ctl 的指示詞，整份換一層、自己讀的格整個解；daemon、fsm 共用）、`Loop` 建構子（`load_cfg`、解指示詞、旗標 ＞ 設定檔 ＞ 預設）、`parse_target`（loop 的 `exec`、fsm 格的 `exec`＝字串或 `[目標, 參數...]`，10-24 起物件＝單子；`resolve_exec`（exec 換一層、單子裡面不解）、`place_inline`（單子的 `AOS_CF`／`AOS_CO`）；10-23 深夜兩邊統一叫 `exec`，原 loop 的 `run`、fsm 格的 `val`）、`loop_cli`（aos-loop、aos-daemon 共用） |
| `aos-fsm/src/table/table.cpp` | `read_table`（`load_cfg`；10-23 晚 `resolve_table` 解整份、`states`、每格、`start`／`exec`／`next` 的指示詞；10-24 起 exec 是單子＝裡面不解、記 `exec_bases`，`check` 用 `place_inline` 填 `AOS_CF`／`AOS_CO`）、`check`（10-22：開跑時查整張表，表壞 CfgBad，10-23 統合前叫 FieldType）、`pick`（state 不在表上 StateUnknown）、`next_for`；`exec` 走 `parse_target`；trace 沒有 `timed_out`。10-30 `next` 兩種（N-36 分岔）：字串、或 `{結束碼: 狀態名}`（key 0～255 或 `*`，至少有 `0` 或 `*`） |
| `aos-fsm/src/main.cpp` | 跑一格：`run_once` → `next_for` 查表 → trace → 查到寫 state、退 0；查不到 state 不動、以格的碼退；自己收到訊號照表寫完再 128＋N |
| `aos-fsm/src/state/state.cpp` | `read_state`（10-22：在但讀不了 StateBad〔10-23 統合前叫 ReadFailed〕、去頭尾 Unicode 空白）、`write_state`（`.state.txt` 再改名；10-23 起狀態檔是 `state.txt`）、`append_trace`（時間用 aos-util 的 `utc_now_ms`，ISO 到毫秒；10-30 一行末尾加 `next`） |
| `aos-daemon/src/` | 逐檔（`daemon.cpp`、`windows.cpp`、`child.cpp`）在 [14-aos-daemon](14-aos-daemon.md)（2026-10-29 本檔超過 8 KB，逐字下放） |
| `aos-directive/src/resolve.cpp` | 指示詞走訪；`$path` 是字串拼接（`join_path`、`decorate`）；10-23 晚加 `resolve_shallow`（只換這一格、不往裡面走，回值與裡面的起點；`$ref` 陣列合出來的每個 key／元素的起點在 `Resolved::dir_of`） |
| `aos-directive/src/ref.cpp` | `$ref`：`fetch_ref`（寫法〔字串或字串陣列；位置只認 `#/`，10-23 刪 `$at`〕、繞圈、讀檔、照指標取原文，陣列＝每份一個）、`resolve_ref`（取完往下解、再合）、`merge`（10-23：`$ref` 陣列幾份合成一份——物件合 key 後蓋前、陣列接起來、混著＝DirectiveBad） |

aos-loop 的骨架是公開的 `aos::loop::Loop`（`src/engine/`），aos-daemon 繼承它（`src/daemon/`）。動工前的樣子原本備份在 `proto8/impls/backup/`（只在家中那台、不進 git），10-23 使用者授權刪掉。

### 舊 lib（10-16 那套，已刪）

`proto8/lib/`（inst、loop、daemon、fsm、agent 格庫、兩種 kernel、tasks、tick，27 支模組＋說明＋12 個測試檔 169 個）與舊 `bin/aos`、六組舊 demo（daemon、fsm、paint、kernels、tasks、tick），10-19 刪進 git 歷史；要找回：`git show 5546be29:proto8/lib/README.md`（逐檔表）。daemon 10-20 已照新做法重寫（10-23 起只剩上面 impls 的 `aos-daemon`）；kernel、tasks、tick、腦的工具呼叫現無實作，待照新做法重寫（[NORMS 待定](../../../../../proto8/docs/NORMS/08-待定.md)）。
