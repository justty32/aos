← [入口](../proto8.md)｜涵蓋：`proto8/tests/`（共用模組、impls 與 bin、agent 的格、demo agent、extras、eca）

跑法：`python3 -m unittest discover -s proto8/tests`（先建 impls，見 [testing](../../../testing.md)）。各 impls 專案自己的 `tests/` 列在 01-impls 各段。真模型的案例連不上就 skip；沒裝的外部程式（janet、bwrap、tmux…）整份或那幾案 skip。路徑相對於該段標題的資料夾。

## `tests/`（共用模組，不是測試）

| 檔 | 負責什麼 |
|---|---|
| `aos_bins.py` | 定程式在哪（各 `impls/<名>/bin/`、`proto8/bin/`、`extras/ai_tools/bin`）：`tool(名)`、`path_with()`；沒建就停 |
| `own_error.py` | import 時 `install()`：subprocess 拿回的 stderr 每行對一次錯誤代號再拿掉 |
| `fake_brain.py` | 假 OpenAI 相容 server 與劇本小幫手 |
| `dead_brain.py` | 「腦壞了」的網址（連上去馬上被拒） |
| `spy_bin/aos-fsm` | 旁觀者：放在 PATH 最前面，記下呼叫再轉給真的 aos-fsm |
| `bench_intent_context.py` | 手動跑的對比（不是測試）：整份 history vs 按意圖組 context 的 token 與答對率 |

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
| `test_tick.py` | `bin/aos-tick` 與 demo tick |
| `test_llm_kernel.py` | aos-llm-send＋aos-llm-kernel 經 aos-loop 端到端：撤信、排隊、slots、重起、額度 |
| `test_claim_dotfiles.py` | demo 的認領題目跳過 `.` 開頭的暫存檔 |

## `tests/`（lib）

| 檔 | 涵蓋 |
|---|---|
| `test_lib.py` | `lib/` 每個工具的形狀、base 的行為、agent-liv 經捷徑用庫 |
| `test_pi_tools.py` | `lib/base` 的 read、write、edit、bash 與 agent-pip |
| `test_file_tools.py` | `lib/base` 的 ls、stat、view、json_edit、mkdir、move、copy、trash 與 agent-pip |
| `test_cli_tools.py` | `lib/agent/claude`、`codex` 與 `cli_session.py`（假的 claude／codex） |

## `tests/`（demo 的 agent）

| 檔 | 涵蓋 |
|---|---|
| `test_eve.py` | agent-eve 叫 pyfix：委派修好與 diff、子 agent 用自己的模型 |
| `test_gus.py` | agent-gus：規劃、fork、只帶結論、深度與額度、`PlanBad` |
| `test_compact.py` | agent-hal 的土法 compact |
| `test_kai.py` | agent-kai：按意圖挑題、recall 工具 |
| `test_meg.py` | agent-meg：記憶庫、`HeapBad`、同時寫不互蓋 |
| `test_talk.py` | demo/talk：send_message、團隊三隻分工、手數上限 |

## `tests/`（extras）

| 檔 | 涵蓋 |
|---|---|
| `test_human.py` | `aos-say`、`aos-listen`（對臨時組的 eca 定義＋假 claude） |
| `test_aos_mcp.py` | `aos-mcp`：測試自己當 MCP client |
| `test_grow.py` | `aos-grow`：長上去再縮回、行為不變 |
| `test_janet.py` | Janet 編成 aos |
| `test_lua_aos.py` | Lua 編成 aos：lua／luajit／`nvim -l` 產物一樣、真跑 |
| `test_sandbox.py` | `aos-sandbox`：路徑、ro／rw、斷網、上限、`setup.sh` |

## `tests/`（外部 coding agent）

| 檔 | 涵蓋 |
|---|---|
| `test_eca_turn.py` | `bin/aos-eca-turn`：`--one`、`--on-empty`、`--on-busy` |
| `test_eca.py` | 範本 `demo/eca-claude`、`eca-codex`：say → 跑 → listen、停著等 |
| `test_eca_cmd.py` | `extras/eca` 的 `aos-eca`：open／close、start／stop、add／rm、ls／state |
