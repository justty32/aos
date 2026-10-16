# proto8/lib — 函式庫

← [proto8](../README.md)

只用 Python 標準庫。

四支程式一個手感：`aos_inst.py x.json`、`aos_loop.py x.json`、`aos_daemon.py x.json`、`aos_fsm.py x.json`（PATH 接上 [`../bin`](../bin/aos) 就寫 `aos inst x.json`、`aos agent think` 等指令名，C-50）；相對路徑一律從呼叫者的 cwd 算（fsm 表上的字串格例外：從 fsm 設定檔所在的資料夾算，N-36）。TARGET 都可以接 `檔#/位置`（N-35）。10-15 深夜 KISS 批次 1（[彙整](../thinking/2026-10-15-kiss/README.md)）純刪：exit 檔、`*_inherit`、loop 的 fixed 節奏與三個 ms 旋鈕、ctl 的 `now`、指示詞的 `$at`／相對位置、aos_tree 都沒了。inst、loop、daemon 照 NORMS N-12 重做（10-14），fsm 10-15 照 N-36～N-41 做了基礎實作，LLM kernel（`aos_gate.py`＋`aos_kernel_llm.py`，N-42）與通用 kernel（`aos_kernel_general.py`）10-15 做了基礎實作：命令列走 `aos_cli`——`[--key 值 ...] [TARGET | -] [-- argv...]`（N-21～N-27），`-`＝設定從 stdin 來，純量 key 有同名旗標；stdout／stderr 吐 JSON 串流。loop、daemon 的 ctl／state 窗與 fsm 的 state 窗必填（N-19）；daemon.json＝loop.json 的超集（N-28）。

## 細節（各一份）

| 檔 | 內容 |
|---|---|
| （`aos_cli.py` 檔頭） | 命令列與三扇門：TARGET／`-`／旗標／`--` 合成設定、JSON 串流讀寫（N-12 程式範本）；`檔#/位置`（N-35）與指示詞（`$ref` 只收「檔#/從根算的位置」、`$env`；語法糖，C-48、N-45）也在這一檔 |
| [inst.md](inst.md) | inst：TARGET、key、`run()`、結果、訊號、API |
| [loop.md](loop.md) | loop：loop.json、每一次怎麼跑、ctl.json、state.json、退出碼、給 daemon 共用的 |
| [fsm.md](fsm.md) | fsm（10-15 收工後瘦身）：方法表與相對路徑、一拍、格的 stdin 不碰、下一狀態、`end` 四種情形、出錯（phase 不動）、state 窗只有 phase、巢狀、不做的事、退出碼 |
| [agent.md](agent.md) | agent（實作慣例，還不是規範）：思考介面（換腦＝換一個 TARGET）、工具＝inst（`tools/`＋`_tool`、每次 `work/<n>/`）、tool 訊息；拆出去的兩份：[agent_lib.md](agent_lib.md)（現成格庫＋邊緣狀況）、[frame.md](frame.md)（agent 當函數／當工具：定義資料夾＋frame、`sh -c` 三步） |
| [daemon.md](daemon.md) | daemon：daemon.json（loop.json 超集）、每拍的身體、children、策略格、table 窗與接回、控制資料夾與指令、收工 |
| [kernel_llm.md](kernel_llm.md) | LLM kernel（N-42 第一種，基礎實作）：閘門的設定與信、kernel 一拍、排序規則、額度、只包葉子的慣例 |
| [kernel_general.md](kernel_general.md) | 通用 kernel（N-42 第二種，基礎實作）：資源格、判官 stdin＝state 窗子集、判官的 run／defer／reject、判官錯退回規則、human 格、agent 判官 |
| [ctl_state.md](ctl_state.md) | ctl 與 state 的慣例：各層的設定／ctl／state、key 分組、seq 回音、state 骨架（含心跳）、七個狀態值 |

## 程式

| 檔 | 是什麼 |
|---|---|
| `aos_cli.py` | 命令列與 stdio（`config()`、`parse_argv()`、`load_target()`、`read_stream()`、`emit()`／`error()`、`CliError`、驗設定共用的 `is_int()`、值的雙形收成物件的 `expand(v)`（C-55，gate 的 priority、think 的連錯計數用它））＋`檔#/位置`（`split_target`、`target_id`、`locate`；錯＝`PointerBad`）＋指示詞（`resolve()`：`$ref` 只收「檔#/從根算的位置」、`$env`；錯＝`DirectiveBad`；10-15 深夜從 `aos_directives.py` 併進來）；大家共用，N-12 的程式範本 |
| `aos_inst.py` | inst：設定從 TARGET／stdin／旗標來、解好、挑認得的 key、跑一次、stdout 吐一份結果（命令列＋`run()`）；資料夾 TARGET 找 `$AOS_DIRNAME/inst.json`（`dirname()`）；沒有 exit 檔；要接呼叫者的串流寫 `*_inherit: true`（10-16 帶回來，N-26），`/dev/std*` 只是路徑、照字面開 |
| `aos_loop.py` | loop（`stop_on_end`＝包的 fsm 走到 end 就結束，N-44）：包一個 inst，跑幾次、隔多久（只有「跑完再隔 interval_ms」一種節奏）、每圈讀 ctl 窗、寫 state 窗、stdout 每次一份結果（命令列＋`run()`＋拍引擎 `Loop`＋`check_config()`／`load_config()`）；收身體＝SIGTERM 後等 aos_inst 自己收 |
| `aos_ctl_state.py` | ctl 窗（`parse_ctl`：`paused`／`stop` 只收布林、`times`／`interval_ms`／`seq`；`want`、`CtlFile`）、state 窗（`STATES`、`state_doc`、`read_state`、`StateFile`，含心跳；ctl 壞檔的原因放 `CtlFile.warning`→state 窗 `last_warning`，state 寫不了放 `StateFile.failed`）、`proc_started`、`require`（窗必填）、`write_json`（資料夾沒有就 makedirs）；loop、daemon 共用 |
| `aos_proc.py` | 子程序的行程群組：等結束、整群送訊號、收屍（`stop`＝SIGTERM 後等到底、`kill`＝SIGTERM 等 grace 再 SIGKILL、`reap`）；loop、daemon 共用 |
| `aos_daemon.py` | daemon：命令列＋`run()`、daemon.json、`Daemon`（`aos_loop.Loop` 的子類：每拍掃資料夾＋跑 inst、每圈收屍） |
| `aos_daemon_table.py` | daemon 的表：`Table`（一條指令一個方法、子項六態、table 窗與接回、`child_exit` 策略格、收工；收子項只看是物件、包 inst.json、填窗，裡面不驗，C-52）、`DaemonError` |
| `aos_daemon_folder.py` | daemon 的指令（`handle()`）與控制資料夾（掃、回覆 `.done`） |
| `aos_methods.py` | 方法表 lib：驗表（`check_table`）、找一格（`cell`：TARGET／內嵌 inst／`{val, next}`）、跑一格（`run_cell`：蓋 stdout（給了 args 才蓋 stdin；fsm 跑格不蓋）、本行程 `aos_inst.run()`；格的 stderr 不碰、不撿，C-52）、取 stdout 最後一份（`last_json`） |
| `aos_fsm.py` | fsm（10-15 收工後瘦身）：命令列＋`run()`、一拍（讀寫只有 `phase` 的 state 窗、跑格（不碰 stdin、不讀 stderr）、換狀態（`next: null`＝留原格；沒結束的拍自己那行也帶 `next: null`，外層不必知道這格是 fsm）、`end` 四種情形、格出錯 phase 不動退 1） |
| `aos_agent_lib.py` | agent 的現成格庫（不是 agent 本體）：`think`、`tool`（stdout 一格 `{"tools"}`，結果不截、被殺就重跑）、`route`、`intake`（只收 `question`、吃完刪 args.json）、`done`、`fsm [NAME]`（照 lookup 找 fsm.json 跑一拍，給定義資料夾的 loop.json 用）；設定只有 `brain`／`tools`／`system`（stdin 那份＋frame 裡 `lookup()`），`history.json`、`work/` 固定在 cwd；錯直接丟 `CliError`、代號六個。細節在 [agent_lib.md](agent_lib.md)；agent 當函數／當工具見 [frame.md](frame.md) |
| `aos_frame.py` | frame 查找（C-46）：`chain()`（frame → `frame.json` 的 parent 鏈）、`lookup()`（找第一個）、`lookup_dir()`（資料夾逐項合併、近的蓋過遠的）；10-15 晚從 `aos_agent_lib.py` 拆出，格庫照樣 re-export |
| `aos_brain_openai.py` | 真的腦（唯一一顆；ollama 原生那顆 10-15 深夜刪）：照思考介面 POST 到 OpenAI 相容的 `/chat/completions`（urllib，不串流，預設 LiteLLM；自己不設逾時，靠包它的 inst 的 `timeout_ms`） |
| `aos_mailbox.py` | kernel 信箱共用（閘門、兩種 kernel）：`mailbox`、旁檔路徑 `side`、`read_letter`、`claim`、`reply`（寫不進去回「ReplyFailed: …」給 kernel 記進 state 窗 `last_warning`）、`run_letter`（信＝inst，`aos_inst.run(信)`，stdout／stderr 落旁檔，回 N-30 結果＋token） |
| `aos_gate.py` | 兩種 kernel 共用的閘門：信＝target 那張 inst 本身＋私有 key `priority`／`reply`／`sent`，stdin 內容寫旁檔、`stdin` 放路徑；丟進信箱（`mailbox` 必填，不認環境變數）、等回信（N-30 結果）、讀旁檔原樣吐 stdout／stderr、用 target 的碼退出；收訊號撤信；排隊逾時只靠包它那張 inst 的 `timeout_ms` |
| `aos_kernel_llm.py` | LLM kernel 的身體（每拍一次，給 aos-loop 拍）：cur/ 殘信回錯、過期／額度見底回錯、排序挑 `slots` 封、`aos_inst.run()` 跑、回信；state 窗照 loop 骨架（`state`、`pid`、`runs`、`last_error`、`beat`）＋`seen`、`budget`、`served` |
| `aos_kernel_general.py` | 通用 kernel 的身體（N-42 第二種，給 aos-loop 拍；一拍＝一段忙碌期）：每種資源各幾格（`slots` 只收物件；資源沒寫＝`ResourceUnknown`）、局面變了才問判官（有信有空格就問，一封也問）、照決定起跑（一封一條執行緒）、格在子程式結束時放；判官的 stdin＝state 窗的 queue／running／slots／budget；沒有 log 檔 |
| `aos_kernel_judge.py` | 通用 kernel 的判官那一半：跑判官 inst（環境、逾時一個 key 都不碰）、驗 `{run, reject}`、判官錯時的確定規則 |
| `aos_kernel_judge_rules.py` | 規則判官（假判官）：human 先、再級數、再先來後到，每種資源補滿空格；回 `{run, reject}` |
| `aos_tasks.py` | tasks 共用（10-15 深夜從 proto8-1 併進來）：起 `aos_inst.py TARGET`、讀它 stdout 結果的 `code`、接訊號轉給它們；跑到哪讀到哪（不先驗全部） |
| `aos_seq.py`、`aos_par.py`、`aos_if.py` | tasks：`aos seq`（像 `&&`）、`aos par`（一起跑、等全部）、`aos if COND THEN [ELSE]`（反過來＝分支對調；aos-not 刪） |
| `aos_tick.py` | 時鐘 `aos tick FILE`：讀出回合數 n、寫回 n＋1（檔格式是它自己的，不進規範） |
| `tests/` | unittest，見[下面](#測試tests) |

相依只往下：`aos_cli` ← `aos_inst` ← `aos_ctl_state`／`aos_proc` ← `aos_loop` ← `aos_daemon_table` ← `aos_daemon_folder` ← `aos_daemon`；fsm 另一支：`aos_inst` ← `aos_methods` ← `aos_fsm`（`aos_fsm` 也借 `aos_ctl_state` 的 `read_state`、`write_json`）；agent：`aos_methods` ← `aos_agent_lib`（也借 `write_json`、`aos_frame`；`fsm` 子命令才載 `aos_fsm`），`aos_brain_openai` 只靠 `aos_cli`；tasks：`aos_cli` ← `aos_tasks` ← `aos_seq`／`aos_par`／`aos_if`（起 `aos_inst.py` 子程序）；`aos_tick` 只靠 `aos_cli`；kernel：`aos_inst` ← `aos_mailbox`（也借 `write_json`）← `aos_gate` ← `aos_kernel_llm` ← `aos_kernel_judge` ← `aos_kernel_general`；`aos_kernel_judge_rules` 獨立（只用標準庫）。

## ctl 與 state 的慣例

搬到 [ctl_state.md](ctl_state.md)（NORMS N-11 的骨架「設定檔讀一次 → ctl 蓋過 → state 回報」，lib 照著做的慣例）。

## 測試（`tests/`）

```
python3 -m unittest discover -s proto8/lib/tests
```

只用標準庫，約 170 個、約 60～80 秒。按受測的程式分十二個檔（`test_cli.py`（含 `檔#/位置`、指示詞）、`test_inst.py`、`test_tasks.py`、`test_tick.py`、`test_loop.py`、`test_daemon.py`、`test_fsm.py`、`test_agent.py`（整圈借 demo/fsm 含報時員 clerk、真腦對本機假伺服器）、`test_agent_frame.py`（frame、agent 當函數／當工具、ask_judge 換定義資料夾）、`test_gate.py`（LLM kernel）、`test_kernel_general.py`（通用 kernel）、`test_paint_demo.py`（畫家 demo：畫家經工具叫畫筆、frame 巢狀、同 frame 續聊、brain.json 綁定只到那一層）），共用的暫存資料夾基底 `Tmp` 與路徑在 `helpers.py`；loop 與 daemon 都起真的行程、走檔案；每個測試用 mktemp 的暫存資料夾，跑完刪掉；刪前查漏網的 aos_loop／daemon／fsm／gate／kernel 行程（cwd 或命令列路徑在暫存資料夾內），有＝失敗（`helpers.leftovers()`）。改 lib 就跑一次，新行為補一個測試。

## 行程與執行緒的規矩

inst、loop、daemon、fsm 都是單執行緒（loop 多一條轉 stderr 的小執行緒），子程式一律用 `subprocess.Popen` 起，不用 `os.fork()`、不用 `preexec_fn`；cwd、環境變數經 `Popen(cwd=, env=)` 只給子程式，不 `chdir`、不改 `os.environ`。fsm 的格在本行程用 `aos_inst.run()` 跑（不另起 aos_inst 行程）。誰起子程序誰負責收：loop 把 aos_inst 起在新 session、daemon 把 loop 起在新 session，收的時候整群送訊號、收屍前整群補 SIGKILL（群組號碼不會先被拿走）。
