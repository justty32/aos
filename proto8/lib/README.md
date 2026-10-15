# proto8/lib — 函式庫

← [proto8](../README.md)

只用 Python 標準庫。

四支程式一個手感：`aos_inst.py x.json`、`aos_loop.py x.json`、`aos_daemon.py x.json`、`aos_fsm.py x.json`；相對路徑一律從呼叫者的 cwd 算。TARGET 都可以接 `檔#/位置`（見[指示詞](directives.md)）。inst、loop、daemon 照 NORMS N-12 重做（10-14），fsm 10-15 照 N-36～N-41 做了基礎實作，LLM kernel（`aos_gate.py`＋`aos_gate_kernel.py`，N-42）10-15 做了基礎實作：命令列走 `aos_cli`——`[--key 值 ...] [TARGET | -] [-- argv...]`（N-21～N-27），`-`＝設定從 stdin 來，純量 key 有同名旗標；stdout／stderr 吐 JSON 串流。loop、daemon 的 ctl／state 窗與 fsm 的 state 窗必填（N-19）；daemon.json＝loop.json 的超集（N-28）。

## 細節（各一份）

| 檔 | 內容 |
|---|---|
| （`aos_cli.py` 檔頭） | 命令列與三扇門：TARGET／`-`／旗標／`--` 合成設定、JSON 串流讀寫（N-12 程式範本） |
| [directives.md](directives.md) | 指示詞 lib（`$ref`、`$env`、`resolve()`）與命令列 TARGET 的 `檔#/位置`（`split_target`、`target_id`、`locate`） |
| [inst.md](inst.md) | inst：TARGET、key、`run()`、exit 檔、訊號、API |
| [loop.md](loop.md) | loop：loop.json、每一次怎麼跑、ctl.json、state.json、退出碼、給 daemon 共用的 |
| [fsm.md](fsm.md) | fsm：方法表、一拍、prev、下一狀態、出錯與 error 格、連錯停住（`max_fails`／`halted`）、step、state 窗、巢狀與 `end`、lock、退出碼 |
| [agent.md](agent.md) | agent（實作慣例，還不是規範）：思考介面（換腦＝換一個 TARGET）、工具＝inst（`tools`＋`_tool`）、tool 訊息、邊緣狀況 |
| [daemon.md](daemon.md) | daemon：daemon.json（loop.json 超集）、每拍的身體、children、策略格、table 窗與接回、控制資料夾與指令、收工 |
| [kernel.md](kernel.md) | LLM kernel（N-42 第一種，基礎實作）：閘門的設定與信、kernel 一拍、排序規則、額度、只包葉子的慣例 |
| [ctl-state.md](ctl-state.md) | ctl 與 state 的慣例：各層的設定／ctl／state、key 分組、seq 回音、state 骨架（含心跳）、七個狀態值 |

## 程式

| 檔 | 是什麼 |
|---|---|
| `aos_directives.py` | 指示詞 lib；命令列 TARGET 的 `檔#/位置`（三支程式共用） |
| `aos_cli.py` | 命令列與 stdio（`config()`、`parse_argv()`、`load_target()`、`read_stream()`、`emit()`／`error()`／`warn()`、`CliError`）；三支共用，N-12 的程式範本；proto8-1 的 tasks、aos-tick 也借 `error()` 吐 stderr |
| `aos_inst.py` | inst：設定從 TARGET／stdin／旗標來、解好、挑認得的 key、跑一次、stdout 吐一份結果（命令列＋`run()`） |
| `aos_loop.py` | loop：包一個 inst，跑幾次、隔多久、讀 ctl 窗、寫 state 窗、stdout 每次一份結果（命令列＋`run()`＋拍引擎 `Loop`＋`check_config()`／`load_config()`）；re-export 下面兩檔的名字 |
| `aos_ctl_state.py` | ctl 窗（`parse_ctl`、`want`、`CtlFile`，含 seq）、state 窗（`STATES`、`state_doc`、`read_state`、`StateFile`，含心跳）、`proc_started`、`require`（窗必填）、`write_json`；loop、daemon 共用 |
| `aos_proc.py` | 子程序的行程群組：等結束、整群送訊號、收屍（`kill`、`reap`）；loop、daemon 共用 |
| `aos_daemon.py` | daemon：命令列＋`run()`、daemon.json、`Daemon`（`aos_loop.Loop` 的子類：每拍掃資料夾＋跑 inst、每圈收屍）；re-export 下面兩檔的名字 |
| `aos_daemon_table.py` | daemon 的表：`Table`（一條指令一個方法、子項六態、table 窗與接回、`child_exit` 策略格、收工）、`DaemonError` |
| `aos_daemon_folder.py` | daemon 的指令（`handle()`）與控制資料夾（掃、回覆 `.done`） |
| `aos_methods.py` | 方法表 lib：驗表（`check_table`）、找一格（`cell`：TARGET／內嵌 inst／`{target, next}`）、跑一格（`run_cell`：蓋 stdin／stdout、本行程 `aos_inst.run()`、撿格 stderr 的 N-29 錯誤當 `cell_error`）、取 stdout 最後一份（`last_json`） |
| `aos_fsm.py` | fsm：命令列＋`run()`、一拍（讀 ctl、讀寫 state 窗、跑格、換狀態、error 格、連錯停住、巢狀 `end`、lock） |
| `aos_agent_lib.py` | agent 的現成格庫（不是 agent 本體；10-15 由 `aos_agent.py` 改名）：設定從 fsm 給的 stdin `cfg` 拿；`think`（讀 history、組請求、跑腦、接 assistant 訊息）、`tool`（跑第一個 tool_call、接 tool 訊息）、`route`（有 tool_calls＝next tool，否則 idle）、`ask`（轉給 `aos_agent_call`）；`tool_specs`、`pending`；brain／tools 可以是 TARGET 或內嵌 inst |
| `aos_agent_call.py` | agent 當函數＋binding（10-15 使用者定的概念 C-46）：`Agent(bob/agent.json).call(frame, history, engine_args, tools, tools_append, cwd)`——定義的路徑從 bob/ 算、攤成內嵌 inst，執行期（history／state／work／lock）放 frame，本行程一拍一拍敲 aos_fsm 到 `end`；`ask()`＝`aos_agent_lib.py ask` 的本體（agent 當工具：frame、lock、MaxTicks、Busy、遞迴層數） |
| `aos_brain_openai.py` | 真的腦：照思考介面 POST 到 OpenAI 相容的 `/chat/completions`（urllib，不串流，預設 LiteLLM） |
| `aos_brain_ollama.py` | 真的腦（ollama 原生）：POST `/api/chat`，帶 `options.num_ctx`、`keep_alive`；兩邊訊息形狀互翻（arguments 字串↔物件、補 id／`tool_name`） |
| `aos_gate.py` | LLM kernel 的閘門：把真正的 inst（target）＋stdin＋priority＋`_metainfo` 寫成信丟進信箱、等回信、原樣吐 stdout／stderr、用 target 的碼退出；`wait_ms`→`QueueTimeout`、收訊號撤信 |
| `aos_gate_kernel.py` | LLM kernel 的身體（每拍一次，給 aos-loop 拍）：cur/ 殘信回錯、過期／額度見底回錯、排序挑 `slots` 封、`aos_inst.run()` 跑、回信；state 窗記拍數、aging、額度 |
| `tests/` | unittest，見[下面](#測試tests) |

相依只往下：`aos_directives` ← `aos_cli` ← `aos_inst` ← `aos_ctl_state`／`aos_proc` ← `aos_loop` ← `aos_daemon_table` ← `aos_daemon_folder` ← `aos_daemon`；fsm 另一支：`aos_inst` ← `aos_methods` ← `aos_fsm`（`aos_fsm` 也借 `aos_ctl_state` 的 ctl 與 `write_json`）；agent：`aos_methods` ← `aos_agent_lib`（也借 `write_json`），`aos_fsm` ← `aos_agent_call`（`aos_agent_lib` 只在 `ask` 時才載它），`aos_brain_openai`、`aos_brain_ollama` 只靠 `aos_cli`；kernel：`aos_inst` ← `aos_gate` ← `aos_gate_kernel`（也借 `write_json`）。

## ctl 與 state 的慣例

搬到 [ctl-state.md](ctl-state.md)（NORMS N-11 的骨架「設定檔讀一次 → ctl 蓋過 → state 回報」，lib 照著做的慣例）。

## 測試（`tests/`）

```
python3 -m unittest discover -s proto8/lib/tests
```

只用標準庫，126 個、約 40 秒。按受測的程式分八個檔（`test_cli.py`、`test_directives.py`、`test_inst.py`、`test_loop.py`、`test_daemon.py`、`test_fsm.py`、`test_agent.py`（整圈借 demo/fsm 含報時員 clerk、agent 當函數／當工具、兩顆真腦對本機假伺服器）、`test_gate.py`（LLM kernel）），共用的暫存資料夾基底 `Tmp` 與路徑在 `helpers.py`；loop 與 daemon 都起真的行程、走檔案；每個測試用 mktemp 的暫存資料夾，跑完刪掉；刪前查漏網的 aos_loop／aos_daemon，有＝失敗（`helpers.leftovers()`）。改 lib 就跑一次，新行為補一個測試。

## 行程與執行緒的規矩

inst、loop、daemon、fsm 都是單執行緒（loop 多一條轉 stderr 的小執行緒），子程式一律用 `subprocess.Popen` 起，不用 `os.fork()`、不用 `preexec_fn`；cwd、環境變數經 `Popen(cwd=, env=)` 只給子程式，不 `chdir`、不改 `os.environ`。fsm 的格在本行程用 `aos_inst.run()` 跑（不另起 aos_inst 行程）。誰起子程序誰負責收：loop 把 aos_inst 起在新 session、daemon 把 loop 起在新 session，收的時候整群送訊號、收屍前整群補 SIGKILL（群組號碼不會先被拿走）。
