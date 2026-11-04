← [入口](../proto8.md)｜涵蓋：`proto8/tests/`（共用模組、固定資料 fixtures、impls 與 bin、lib、extras、eca）

跑法：`python3 -m unittest discover -s proto8/tests`（先建 impls，見 [testing](../../../testing.md)）。各 impls 專案自己的 `tests/` 列在 01-impls 各段。真模型的案例連不上就 skip；沒裝的外部程式（janet、bwrap、tmux…）整份或那幾案 skip。路徑相對於該段標題的資料夾。

## `tests/`（共用模組，不是測試）

| 檔 | 負責什麼 |
|---|---|
| `aos_bins.py` | 定程式在哪（各 `impls/<名>/bin/`、`proto8/bin/`、`extras/ai_tools/bin`）：`tool(名)`、`path_with()`；沒建就停 |
| `own_error.py` | import 時 `install()`：subprocess 拿回的 stderr 每行對一次錯誤代號再拿掉 |
| `dead_brain.py` | 「腦壞了」的網址（連上去馬上被拒） |
| `spy_bin/aos-fsm` | 旁觀者：放在 PATH 最前面，記下呼叫再轉給真的 aos-fsm |

## `tests/fixtures/`（測試的固定資料，不是測試；11-04 從 `demo/` 搬來）

**agent 骨架**：`_entry`（`exec aos-loop loop.json`）、`loop.json`（`exec` 指 `fsm.json`、`max`）、`fsm.json`（idle → think → act）、`idle/_entry`（`cur/` 或 `new/` 有題目退 0、沒有退 10）、`brain.py`（think：認領題目、問腦、接進 history；沒設 `AOS_BRAIN_URL`＝假腦）、`act.py`（跑工具，工具的問題回給腦不停）、`.env`（模型名）、`system.txt`（人格）、`tools.json`（工具註冊檔）、`tools/<名>`（捷徑到 `lib/`）。

| 檔 | 負責什麼 |
|---|---|
| `agent-bob/`：`_entry`、`loop.json`、`fsm.json`、`idle/_entry`、`brain.py` | 混合範本（子資料夾＋單子）骨架；think 是 `fsm.json` 裡的單子（test_exec） |
| `agent-bob/act/_entry` | 把 `plan.txt` 當題目交給 `tools/cathy`，答案寫 `out/` |
| `agent-bob/act/tools/cathy/*` | 另一隻 agent（自己的骨架＋`act/tools/stamp/_entry`：加時間戳、計次） |
| `agent-ann/`：`_entry`、`loop.json`、`fsm.json`、`brain.py`、`act.py`、`idle.py`、`.env` | 全內嵌對照：零子資料夾，`_entry`＝`exec aos-exec loop.json`，三格全是單子（test_exec、test_lua_aos 比對 `extras/langs/lua/examples/agent_ann.lua`，它的三支 .py 從這裡讀） |
| `agent-eve/`：骨架＋`tools/pyfix` | 叫 pyfix 的那一方（`tools/pyfix` 捷徑 → `lib/agent/pyfix`）；act 逾時 30 分鐘（test_pyfix、test_file_tools、test_grow、test_human、test_llm_kernel） |
| `tick/_entry`、`tick/loop.json` | loop 跑 5 次 `aos-tick`，時鐘檔是 5（test_tick） |

## `tests/`（impls 與 bin）

| 檔 | 涵蓋 |
|---|---|
| `test_inst.py` | inst 單子經 aos-exec 跑、單子欄位與錯誤代號 |
| `test_exec.py` | aos-exec、aos-loop、兩隻 agent 與巢狀 |
| `test_exec_rules.py` | aos-exec 的進階規則與四支的錯誤代號 |
| `test_exec_env.py` | `.env`：設值、`${}`、優先順序、轉向、沿路 `.env`、JSON `.env` key |
| `test_exec_dotenv.py` | `.env` 的 dotenv 基礎子集與 `--dotenv-override` |
| `test_directive_argv.py`、`test_directive_lenient.py` | 指示詞 `$ref`／`$env`／`$path` 的寫法與寬容規則 |
| `test_loop.py` | aos-loop：訊號、`interval_ms`、ctl 指令、state 窗 |
| `test_fsm.py` | aos-fsm：表、`next` 分岔、state 檔、訊號 |
| `test_daemon.py` | aos-daemon：procs、ctl 增減、不重起、收工、接回 |
| `test_aos_daemon_ctl.py` | `bin/aos-daemon-ctl`：add／rm／start／stop／pause／resume／ls／where、sleep／wake |
| `test_aos_tools.py` | `bin/aos-tools`：三種登記對象、撞名、路徑、`--tooldef` 快取與 `--no-cache` |
| `test_tick.py` | `bin/aos-tick` 與 fixtures 的 tick |
| `test_llm_kernel.py` | aos-llm-send＋aos-llm-kernel 經 aos-loop 端到端：撤信、排隊、slots、重起、額度 |

## `tests/`（lib）

| 檔 | 涵蓋 |
|---|---|
| `test_lib.py` | `lib/` 每個工具的形狀、base 的行為 |
| `test_pi_tools.py` | `lib/base` 的 read、write、edit、bash |
| `test_file_tools.py` | `lib/base` 的 ls、stat、view、json_edit、mkdir、move、copy、trash（看、改 fixtures 的 agent-eve 複本） |
| `test_cli_tools.py` | `lib/agent/claude`、`codex` 與 `cli_session.py`（假的 claude／codex） |
| `test_pyfix.py` | `lib/agent/pyfix`：fixtures 的 agent-eve 叫它，委派修好與 diff、子 agent 用自己的模型、工具留在 pyfix_dir（11-04 前叫 test_eve） |
| `test_memory.py` | `lib/aos/memory`：save／search／read／forget、`AOS_HEAP`、`HeapBad`、同時寫不互蓋（11-04 前叫 test_meg） |
| `test_send_message.py` | `lib/aos/send_message`：名冊、群組、上限、送不到、同時寄（11-04 前叫 test_talk） |

## `tests/`（extras）

| 檔 | 涵蓋 |
|---|---|
| `test_human.py` | `aos-say`、`aos-listen`（對臨時組的 eca 定義＋假 claude）；`aos_ws.letter_key`／「最新那封」照處理順序 |
| `test_aos_mcp.py` | `aos-mcp`：測試自己當 MCP client |
| `test_grow.py` | `aos-grow`：長上去再縮回、行為不變 |
| `test_janet.py` | Janet 編成 aos |
| `test_lua_aos.py` | Lua 編成 aos：lua／luajit／`nvim -l` 產物一樣、真跑 |
| `test_sandbox.py` | `aos-sandbox`：路徑、ro／rw、斷網、上限、`setup.sh` |

## `tests/`（外部 coding agent）

| 檔 | 涵蓋 |
|---|---|
| `test_eca_turn.py` | `bin/aos-eca-turn`：`--one`、`--on-empty`、`--on-busy`；批次順序（無序排最後、照樣答） |
| `test_agent_fsm.py` | 範本 `demo/agent-fsm`（11-04）：形狀、一問一答、整批、壞信、無序排後、`--prompt`、停著等 vs 收工、腦失敗接著答、工具錯回給腦、`--system`／`--tools`（本機假端點）、暫停改 history、掛 daemon（add／pause／resume／stop／start／rm） |
| `test_eca.py` | 範本 `demo/eca-claude`（codex 版由它複製換 `cli.json`）：say → 跑 → listen、停著等 |
| `test_eca_cmd.py` | `extras/eca` 的 `aos-eca`：open／close、start／stop、add／rm、ls／state |
