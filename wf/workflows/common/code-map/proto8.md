← [code map 總圖](../code-map.md)｜[各分冊導覽](README.md)

## proto8 逐檔總覽（proto8-1 10-15 深夜併入）

（10-13 從 code-map.md 原文搬來；10-15 晚從一整段長文改成分項，內容沒刪。新增或刪檔時這裡與該 README 一起改。）

### `proto8/lib/`（Python）

逐檔表在 [proto8/lib/README.md](../../../../proto8/lib/README.md)；各程式的細節在同資料夾的 `inst.md`、`loop.md`、`daemon.md`、`fsm.md`、`agent.md`（＋拆出的 `agent_lib.md`、`frame.md`）、`kernel_llm.md`、`kernel_general.md`、`ctl_state.md`。

**命令列與共用**：命令列與 stdio 範本 `aos_cli.py`（含驗設定共用的 `is_int()`、值的雙形收成物件的 `expand()`；沒有寫 stderr 的警告，預料到的意外記進各自的窗 `last_warning`；`檔#/位置`＋指示詞（語法糖，`$ref` 只收「檔#/從根算的位置」）10-15 深夜從 `aos_directives.py` 併進來）。

**inst／loop／daemon**：inst `aos_inst.py`（沒有 exit 檔，10-15 深夜 KISS 批次 1；`*_inherit` 10-16 帶回來，N-26）；loop `aos_loop.py`（`stop_on_end`：包的 fsm 走到 end 就結束，N-44；只有「跑完再隔」一種節奏、每圈讀 ctl、收身體＝SIGTERM 後等 aos_inst 自己收）＋共用的 ctl／state `aos_ctl_state.py`（`paused`／`stop` 只收布林）與行程群組 `aos_proc.py`；daemon `aos_daemon.py`（重用 loop 的拍引擎）＋表與策略格 `aos_daemon_table.py`（收子項只看是物件、包 inst.json、填窗，裡面的 loop key 與 inst 不驗，C-52）＋指令與控制資料夾 `aos_daemon_folder.py`。

**fsm**：`aos_fsm.py`（只管狀態→格，state 窗只有 phase；格的 stderr 不讀；沒結束的拍自己那行帶 `next: null`，所以外層不必知道某格是 fsm）＋方法表 `aos_methods.py`（跑格：蓋 stdout、不碰 stdin／stderr）。

**agent**：現成格庫 `aos_agent_lib.py`——think（腦的 stderr 不讀，BrainFailed 只說結束碼）／tool（一拍內照順序跑完全部 tool_calls，每個在 `work/<n>/` 跑、寫 `args.json`；stdout 一格 `{"tools"}`、結果不截、被殺就重跑；工具裡面是什麼不管、不傳，C-52）／route／intake（args.json 只收 `question`、接進 history、接完刪）／done（寫 ret.json，不碰 ctl），外加給 loop.json 用的 `fsm`（照 lookup 找 fsm.json 跑一拍）；設定只有 `brain`／`tools`／`system`（格 inst 自己的 stdin＋frame 裡 `lookup()`），`history.json`、`work/` 固定在 cwd；錯直接丟 `CliError`（10-15 深夜 KISS 批次 1）。frame 查找（cwd → `frame.json` parent 鏈）在 `aos_frame.py`（格庫 re-export）。agent 當函數／當工具不另寫程式（`aos_agent_call.py` 10-15 退場）：定義資料夾＋frame、工具 inst 用 `sh -c` 三步。

**真的腦**：`aos_brain_openai.py`（OpenAI 相容；唯一一顆，ollama 原生那顆 10-15 深夜刪；自己不設逾時）；在 assistant 訊息頂層帶 `usage` 給 kernel 記額度。

**kernel**：信箱共用 `aos_mailbox.py`（信＝inst、回信＝N-30 結果、stdout／stderr 落旁檔；沒有 log）＋閘門 `aos_gate.py`（兩種 kernel 共用；`mailbox` 必填、不認環境變數、沒有 `wait_ms`／`QueueTimeout`，10-15 深夜 KISS 批次 1）；LLM kernel 的身體 `aos_kernel_llm.py`（N-42 第一種，細節 `kernel_llm.md`）；通用 kernel 的身體 `aos_kernel_general.py`（`slots` 只收物件、資源沒寫＝`ResourceUnknown`、一封也問判官）、判官那一半 `aos_kernel_judge.py`（答案 `{run, reject}`，不碰判官的環境與逾時）、規則判官 `aos_kernel_judge_rules.py`（N-42 第二種，細節 `kernel_general.md`）。

**薄入口**：`proto8/bin/aos`（`aos <名>`＝`python3 lib/aos_<名>.py`、`aos kernel llm|general`、`aos agent …`、`aos brain …`，放進 PATH 讓 argv 寫指令名；`tree` 隨 aos_tree 一起刪）。

**測試**：`tests/` 按程式分檔（`helpers.ENV` 把 `proto8/bin`、`demo/bin` 接到 PATH 前面）。

### `proto8/demo/`

總覽在 [proto8/demo/README.md](../../../../proto8/demo/README.md)。

**daemon**：`daemon.json`、`run.py`、`once/`、`tick/`（真的 `aos tick clock`；結果看 stdout 與 state 窗；見 demo README）。

**薄入口**：`demo/bin/aos-demo`（`aos-demo fsm/x.py`＝從 demo 資料夾算的腳本，其他指令照跑並給 `AOS_DEMO`）。

**fsm／agent**（`demo/fsm/`）：本身是 agent 定義資料夾——`fsm.json`、`loop.json`、`cells/`（idle.py、thinking＝內層 `think/fsm.json`、tool、done）、`brain.json`＝假腦 `brains/fake.py`、`system.md`、`tools/clerk.json`（agent 當工具：`sh -c` 三步叫報時員）；換用的腦 `brains/openai.json`／`litellm.json`／`lmstudio.json`；報時員定義資料夾 `clerk/`（含 `tools/clock.*`）；`run.py` 建 frame、在裡面跑 loop.json。

**LLM kernel**（`demo/kernels/llm/`）：daemon／loop／kernel 設定由 `run.py` 寫成完整檔、閘門 `gates/brain.json`／`gates/fake.json`（mailbox 寫 `{"$env": "AOS_KERNEL"}`，demo 省字）、假腦 `brain.py`、腦包閘門的 agent 定義資料夾 `boss/`（工具 `tools/clerk.json` 借 `demo/fsm/clerk/`；clerk 用自己的腦，不從上層伸手進它的 frame）。

**通用 kernel**（`demo/kernels/general/`）：設定由 `run.py` 寫成完整檔、活 `job.py`（llm／cpu／human）、閘門 `gates/*.json`、判官 `judges/rules.json`（`_schema`→`judges/schema.json`）／`judges/broken.json`／`judges/agent.json`＋agent 判官定義資料夾 `judges/agent/`（入口 `ask_judge.py [定義資料夾]`：暫存 frame（frame.json 指引數給的資料夾，預設 judge/）跑 `judge/loop.json`、讀 ret.json 原樣印；失敗一律 `JudgeFailed`）。

**畫家 demo**（[`demo/paint/`](../../../../proto8/demo/paint/README.md)）：兩個 agent 定義資料夾 `painter/`（工具 `tools/brush.json`＝`sh -c` 三步叫畫筆）、`brush/`（工具 `tools/palette.*` 調色盤），假腦 `brains/fake.py`（看帶哪個工具當畫家或畫筆）＋`brains/fake_alt.json`（換腦用），`run.py`＝三段展示＋`bind_brain()`（frame 放 brain.json，只換畫家這一層）；測試 `tests/test_paint_demo.py`。

改 proto8 的檔就同步那份。

### tasks 與 tick（10-15 深夜從 `proto8-1/` 併進 `proto8/lib/`）

tasks：`aos_seq.py`、`aos_par.py`、`aos_if.py`（`aos-not` 刪：反過來＝分支對調）、共用 `aos_tasks.py`（起 `aos_inst.py TARGET`、讀結果的 `code`、轉訊號；跑到哪讀到哪）、時鐘 `aos_tick.py`（`aos tick FILE`）；入口都在 `proto8/bin/aos`；測試 `tests/test_tasks.py`、`tests/test_tick.py`；demo（daemon 跑 tasks 樹＋寫起來的發現）在 [proto8/demo/tasks/README.md](../../../../proto8/demo/tasks/README.md)。
