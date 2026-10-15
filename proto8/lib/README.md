# proto8/lib — 函式庫

← [proto8](../README.md)

只用 Python 標準庫。

四支程式一個手感：`aos_inst.py x.json`、`aos_loop.py x.json`、`aos_daemon.py x.json`、`aos_fsm.py x.json`（PATH 接上 [`../bin`](../bin/aos) 就寫 `aos inst x.json`、`aos agent think` 等指令名，C-50）；相對路徑一律從呼叫者的 cwd 算（fsm 表上的字串格例外：從 fsm 設定檔所在的資料夾算，N-36）。TARGET 都可以接 `檔#/位置`（N-35）。inst、loop、daemon 照 NORMS N-12 重做（10-14），fsm 10-15 照 N-36～N-41 做了基礎實作，LLM kernel（`aos_gate.py`＋`aos_kernel_llm.py`，N-42）與通用 kernel（`aos_kernel_general.py`）10-15 做了基礎實作：命令列走 `aos_cli`——`[--key 值 ...] [TARGET | -] [-- argv...]`（N-21～N-27），`-`＝設定從 stdin 來，純量 key 有同名旗標；stdout／stderr 吐 JSON 串流。loop、daemon 的 ctl／state 窗與 fsm 的 state 窗必填（N-19）；daemon.json＝loop.json 的超集（N-28）。

## 細節（各一份）

| 檔 | 內容 |
|---|---|
| （`aos_cli.py` 檔頭） | 命令列與三扇門：TARGET／`-`／旗標／`--` 合成設定、JSON 串流讀寫（N-12 程式範本） |
| [inst.md](inst.md) | inst：TARGET、key、`run()`、exit 檔、訊號、API |
| [loop.md](loop.md) | loop：loop.json、每一次怎麼跑、ctl.json、state.json、退出碼、給 daemon 共用的 |
| [fsm.md](fsm.md) | fsm（10-15 收工後瘦身）：方法表與相對路徑、一拍、格的 stdin 不碰、下一狀態、`end` 四種情形、出錯（phase 不動）、state 窗只有 phase、巢狀、不做的事、退出碼 |
| [agent.md](agent.md) | agent（實作慣例，還不是規範）：思考介面（換腦＝換一個 TARGET）、工具＝inst（`tools/`＋`_tool`、每次 `work/<n>/`）、tool 訊息；拆出去的兩份：[agent_lib.md](agent_lib.md)（現成格庫＋邊緣狀況）、[frame.md](frame.md)（agent 當函數／當工具：定義資料夾＋frame、`sh -c` 三步） |
| [daemon.md](daemon.md) | daemon：daemon.json（loop.json 超集）、每拍的身體、children、策略格、table 窗與接回、控制資料夾與指令、收工 |
| [kernel_llm.md](kernel_llm.md) | LLM kernel（N-42 第一種，基礎實作）：閘門的設定與信、kernel 一拍、排序規則、額度、只包葉子的慣例 |
| [kernel_general.md](kernel_general.md) | 通用 kernel（N-42 第二種，基礎實作）：資源格、判官 stdin＝state 窗子集、判官的 run／defer／reject、判官錯退回規則、human 格、agent 判官 |
| [ctl_state.md](ctl_state.md) | ctl 與 state 的慣例：各層的設定／ctl／state、key 分組、seq 回音、state 骨架（含心跳）、七個狀態值 |
| [directives.md](directives.md) | 語法糖（C-48：只是把 JSON 拆成小檔、讀環境變數的便利，設計不靠它）：指示詞 lib（`$ref`、`$env`、`resolve()`），以及命令列 TARGET 的 `檔#/位置`（N-35）的實作（`split_target`、`target_id`、`locate`） |

## 程式

| 檔 | 是什麼 |
|---|---|
| `aos_cli.py` | 命令列與 stdio（`config()`、`parse_argv()`、`load_target()`、`read_stream()`、`emit()`／`error()`、`CliError`（10-15 拿掉 `warn()`：不寫 stderr 警告，N-43）、驗設定共用的 `is_int()`、值的雙形收成物件的 `expand(v, key="val")`（C-55，ctl 的 paused／stop、gate 的 priority、think 的連錯計數都用它））；三支共用，N-12 的程式範本；proto8-1 的 tasks、aos-tick 也借 `error()` 吐 stderr |
| `aos_directives.py` | 命令列 TARGET 的 `檔#/位置`（大家共用）；順帶解指示詞（語法糖，有用才有作用） |
| `aos_inst.py` | inst：設定從 TARGET／stdin／旗標來、解好、挑認得的 key、跑一次、stdout 吐一份結果（命令列＋`run()`）；資料夾 TARGET 找 `$AOS_DIRNAME/inst.json`（`dirname()`） |
| `aos_loop.py` | loop（`stop_on_end`＝包的 fsm 走到 end 就結束，N-44）：包一個 inst，跑幾次、隔多久、讀 ctl 窗、寫 state 窗、stdout 每次一份結果（命令列＋`run()`＋拍引擎 `Loop`＋`check_config()`／`load_config()`）；re-export 下面兩檔的名字 |
| `aos_ctl_state.py` | ctl 窗（`parse_ctl`、`want`、`CtlFile`，含 seq）、state 窗（`STATES`、`state_doc`、`read_state`、`StateFile`，含心跳；ctl 壞檔的原因放 `CtlFile.warning`→state 窗 `last_warning`，state 寫不了放 `StateFile.failed`）、`proc_started`、`require`（窗必填）、`write_json`；loop、daemon 共用 |
| `aos_proc.py` | 子程序的行程群組：等結束、整群送訊號、收屍（`kill`、`reap`）；loop、daemon 共用 |
| `aos_daemon.py` | daemon：命令列＋`run()`、daemon.json、`Daemon`（`aos_loop.Loop` 的子類：每拍掃資料夾＋跑 inst、每圈收屍）；re-export 下面兩檔的名字 |
| `aos_daemon_table.py` | daemon 的表：`Table`（一條指令一個方法、子項六態、table 窗與接回、`child_exit` 策略格、收工）、`DaemonError` |
| `aos_daemon_folder.py` | daemon 的指令（`handle()`）與控制資料夾（掃、回覆 `.done`） |
| `aos_methods.py` | 方法表 lib：驗表（`check_table`）、找一格（`cell`：TARGET／內嵌 inst／`{val, next}`）、跑一格（`run_cell`：蓋 stdout（給了 args 才蓋 stdin；fsm 跑格不蓋）、本行程 `aos_inst.run()`、撿格 stderr 的 N-29 錯誤當 `cell_error`）、取 stdout 最後一份（`last_json`） |
| `aos_fsm.py` | fsm（10-15 收工後瘦身）：命令列＋`run()`、一拍（讀寫只有 `phase` 的 state 窗、跑格（不碰 stdin）、換狀態、`end` 四種情形、格出錯 phase 不動退 1） |
| `aos_agent_lib.py` | agent 的現成格庫（不是 agent 本體）：`think`、`tool`、`route`、`intake`、`done`、`fsm [NAME]`（照 lookup 找 fsm.json 跑一拍，給定義資料夾的 loop.json 用）；設定＝格 inst 自己的 stdin＋frame 裡 `lookup()`；`tool_specs`、`pending`。各格的細節在 [agent_lib.md](agent_lib.md)；agent 當函數／當工具不另寫程式（`aos_agent_call.py` 10-15 退場），見 [frame.md](frame.md) |
| `aos_frame.py` | frame 查找（C-46）：`chain()`（frame → `frame.json` 的 parent 鏈）、`lookup()`（找第一個）、`lookup_dir()`（資料夾逐項合併、近的蓋過遠的）；10-15 晚從 `aos_agent_lib.py` 拆出，格庫照樣 re-export |
| `aos_brain_openai.py` | 真的腦：照思考介面 POST 到 OpenAI 相容的 `/chat/completions`（urllib，不串流，預設 LiteLLM） |
| `aos_brain_ollama.py` | 真的腦（ollama 原生）：POST `/api/chat`，帶 `options.num_ctx`、`keep_alive`；兩邊訊息形狀互翻（arguments 字串↔物件、補 id／`tool_name`） |
| `aos_mailbox.py` | kernel 信箱共用（閘門、兩種 kernel）：`mailbox`、旁檔路徑 `side`、`read_letter`、`claim`、`reply`（寫不進去回「ReplyFailed: …」給 kernel 記進 state 窗 `last_warning`）、`run_letter`（信＝inst，`aos_inst.run(信)`，stdout／stderr 落旁檔，回 N-30 結果＋token）、`log` |
| `aos_gate.py` | 兩種 kernel 共用的閘門：信＝target 那張 inst 本身＋私有 key `priority`／`reply`／`sent`，stdin 內容寫旁檔、`stdin` 放路徑；丟進信箱（`mailbox`，沒寫＝`AOS_KERNEL`）、等回信（N-30 結果）、讀旁檔原樣吐 stdout／stderr、用 target 的碼退出；`wait_ms`→`QueueTimeout`、收訊號撤信 |
| `aos_kernel_llm.py` | LLM kernel 的身體（每拍一次，給 aos-loop 拍）：cur/ 殘信回錯、過期／額度見底回錯、排序挑 `slots` 封、`aos_inst.run()` 跑、回信；state 窗照 loop 骨架（`state`、`pid`、`runs`、`last_error`、`beat`）＋`seen`、`budget`、`served` |
| `aos_kernel_general.py` | 通用 kernel 的身體（N-42 第二種，給 aos-loop 拍；一拍＝一段忙碌期）：每種資源各幾格、局面變了才問判官、照決定起跑（一封一條執行緒）、格在子程式結束時放；判官的 stdin＝state 窗的 queue／running／slots／budget |
| `aos_kernel_judge.py` | 通用 kernel 的判官那一半：跑判官 inst（拿掉自己的 `AOS_KERNEL`）、驗 `{run, defer, reject}`、判官錯時的確定規則 |
| `aos_tree.py` | 看狀況的小工具，不屬規範（10-15 使用者）。inst 樹工具（同像性，10-15）：`print TARGET` 畫樹（每行 `位置: 種類 id`）、`inline TARGET` 把路徑參照全攤成一份 JSON（循環／深度限制留名字、那個 ref 帶 `stop`，print 行尾標出；不寫 stderr）；只看位置認 inst，不跑任何東西；`build()`／`render()`／`slots()` |
| `aos_kernel_judge_rules.py` | 規則判官（假判官）：human 先、再級數、再先來後到，每種資源補滿空格 |
| `tests/` | unittest，見[下面](#測試tests) |

相依只往下：`aos_directives` ← `aos_cli` ← `aos_inst` ← `aos_ctl_state`／`aos_proc` ← `aos_loop` ← `aos_daemon_table` ← `aos_daemon_folder` ← `aos_daemon`；fsm 另一支：`aos_inst` ← `aos_methods` ← `aos_fsm`（`aos_fsm` 也借 `aos_ctl_state` 的 `read_state`、`write_json`）；agent：`aos_methods` ← `aos_agent_lib`（也借 `write_json`、`aos_frame`；`fsm` 子命令才載 `aos_fsm`），`aos_brain_openai`、`aos_brain_ollama` 只靠 `aos_cli`；kernel：`aos_inst` ← `aos_mailbox`（也借 `write_json`）← `aos_gate` ← `aos_kernel_llm` ← `aos_kernel_judge` ← `aos_kernel_general`；`aos_kernel_judge_rules` 獨立（只用標準庫）。

## ctl 與 state 的慣例

搬到 [ctl_state.md](ctl_state.md)（NORMS N-11 的骨架「設定檔讀一次 → ctl 蓋過 → state 回報」，lib 照著做的慣例）。

## 測試（`tests/`）

```
python3 -m unittest discover -s proto8/lib/tests
```

只用標準庫，172 個、約 50～70 秒。按受測的程式分十二個檔（`test_cli.py`、`test_directives.py`、`test_inst.py`、`test_loop.py`、`test_daemon.py`、`test_fsm.py`、`test_agent.py`（整圈借 demo/fsm 含報時員 clerk、兩顆真腦對本機假伺服器）、`test_agent_frame.py`（frame、agent 當函數／當工具、ask_judge 換定義資料夾）、`test_gate.py`（LLM kernel）、`test_kernel_general.py`（通用 kernel）、`test_tree.py`（aos_tree、判官回話的 schema 用手寫最小驗證器驗）、`test_paint_demo.py`（畫家 demo：畫家經工具叫畫筆、frame 巢狀、同 frame 續聊、brain.json 綁定只到那一層）），共用的暫存資料夾基底 `Tmp` 與路徑在 `helpers.py`；loop 與 daemon 都起真的行程、走檔案；每個測試用 mktemp 的暫存資料夾，跑完刪掉；刪前查漏網的 aos_loop／daemon／fsm／gate／kernel 行程（cwd 或命令列路徑在暫存資料夾內），有＝失敗（`helpers.leftovers()`）。改 lib 就跑一次，新行為補一個測試。

## 行程與執行緒的規矩

inst、loop、daemon、fsm 都是單執行緒（loop 多一條轉 stderr 的小執行緒），子程式一律用 `subprocess.Popen` 起，不用 `os.fork()`、不用 `preexec_fn`；cwd、環境變數經 `Popen(cwd=, env=)` 只給子程式，不 `chdir`、不改 `os.environ`。fsm 的格在本行程用 `aos_inst.run()` 跑（不另起 aos_inst 行程）。誰起子程序誰負責收：loop 把 aos_inst 起在新 session、daemon 把 loop 起在新 session，收的時候整群送訊號、收屍前整群補 SIGKILL（群組號碼不會先被拿走）。
