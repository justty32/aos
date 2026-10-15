← [code map 總圖](../code-map.md)｜[各分冊導覽](README.md)

## proto8／proto8-1 逐檔總覽

（10-13 從 code-map.md 原文搬來；10-15 晚從一整段長文改成分項，內容沒刪。新增或刪檔時這裡與該 README 一起改。）

### `proto8/lib/`（Python）

逐檔表在 [proto8/lib/README.md](../../../../proto8/lib/README.md)；各程式的細節在同資料夾的 `directives.md`、`inst.md`、`loop.md`、`daemon.md`、`fsm.md`、`agent.md`（＋拆出的 `agent-lib.md`、`agent-frame.md`）、`kernel.md`、`kernel2.md`、`ctl-state.md`。

**命令列與共用**：命令列與 stdio 範本 `aos_cli.py`（含驗設定共用的 `is_int()`）、`檔#/位置`＋指示詞（語法糖）`aos_directives.py`。

**inst／loop／daemon**：inst `aos_inst.py`；loop `aos_loop.py`（`stop_on_end`：包的 fsm 走到 end 就結束，N-44）＋共用的 ctl／state `aos_ctl_state.py` 與行程群組 `aos_proc.py`；daemon `aos_daemon.py`（重用 loop 的拍引擎）＋表與策略格 `aos_daemon_table.py`＋指令與控制資料夾 `aos_daemon_folder.py`。

**fsm**：`aos_fsm.py`（只管狀態→格，state 窗只有 phase）＋方法表 `aos_methods.py`。

**agent**：現成格庫 `aos_agent_lib.py`——think／tool（一拍內照順序跑完全部 tool_calls，每個在 `work/<n>/` 跑、寫 `args.json`）／route／intake（args.json 接進 history、接完改名 `args.taken.json`，也刪上一輪 ret.json）／done（寫 ret.json，不碰 ctl），外加給 loop.json 用的 `fsm`（照 lookup 找 fsm.json 跑一拍）；設定＝格 inst 自己的 stdin＋frame 裡 `lookup()`；`system` 選填＝系統提示檔，不進 history。frame 查找（cwd → `env.json` parent 鏈）在 `aos_frame.py`（格庫 re-export）。agent 當函數／當工具不另寫程式（`aos_agent_call.py` 10-15 退場）：定義資料夾＋frame、工具 inst 用 `sh -c` 三步。

**真的腦**：`aos_brain_openai.py`（OpenAI 相容）與 `aos_brain_ollama.py`（ollama 原生 `/api/chat`，能設 num_ctx）；兩顆都在 assistant 訊息頂層帶 `usage` 給 kernel 記額度。

**kernel**：信箱共用 `aos_mailbox.py`（信＝inst、回信＝N-30 結果、stdout／stderr 落旁檔）＋閘門 `aos_gate.py`（兩種 kernel 共用）；LLM kernel 的身體 `aos_gate_kernel.py`（N-42 第一種，細節 `kernel.md`）；通用 kernel 的身體 `aos_kernel.py`、判官那一半 `aos_kernel_judge.py`、規則判官 `judge_rules.py`（N-42 第二種，細節 `kernel2.md`）。

**小工具**：inst 樹工具 `aos_tree.py`（print／inline，同像性；看狀況用，不屬規範）。

**薄入口**：`proto8/bin/aos`（`aos <名>`＝`python3 lib/aos_<名>.py`、`aos agent …`、`aos brain …`，放進 PATH 讓 argv 寫指令名）。

**測試**：`tests/` 按程式分檔（`helpers.ENV` 把 `proto8/bin`、`demo/bin` 接到 PATH 前面）。

### `proto8/demo/`

總覽在 [proto8/demo/README.md](../../../../proto8/demo/README.md)。

**daemon**：`daemon.json`、`run.py` 等（見 demo README）。

**薄入口**：`demo/bin/aos-demo`（`aos-demo fsm/x.py`＝從 demo 資料夾算的腳本，其他指令照跑並給 `AOS_DEMO`）。

**fsm／agent**（`demo/fsm/`）：本身是 agent 定義資料夾——`fsm.json`、`loop.json`、`cells/`（idle.py、thinking＝內層 `think/fsm.json`、tool、done）、`brain.json`＝假腦 `brain/fake.py`、`system.md`、`tools/clerk.json`（agent 當工具：`sh -c` 三步叫報時員）；換用的腦 `brain/openai.json`／`litellm.json`／`lmstudio.json`／`ollama146.json`／`qwen146.json`；報時員定義資料夾 `clerk/`（含 `tools/clock.*`）；`run.py` 建 frame、在裡面跑 loop.json。

**LLM kernel**（`demo/kernel/`）：daemon／loop／kernel 設定由 `run.py` 寫成完整檔、閘門 `gate.json`／`gate-fake.json`、假腦 `brain.py`、腦包閘門的 agent 定義資料夾 `boss/`（工具 `tools/clerk.json` 借 `demo/fsm/clerk/` 並在它的 frame 綁 boss 的腦）。

**通用 kernel**（`demo/kernel2/`）：設定由 `run.py` 寫成完整檔、活 `job.py`（llm／cpu／human）、閘門 `gate-*.json`、判官 `judge-rules.json`（`_schema`→`judge.schema.json`）／`judge-broken.json`／`judge-agent.json`＋agent 判官定義資料夾 `judge/`（入口 `ask_judge.py [定義資料夾]`：暫存 frame（env.json 指引數給的資料夾，預設 judge/）跑 `judge/loop.json`、讀 ret.json）。

**畫家 demo**（[`demo/paint/`](../../../../proto8/demo/paint/README.md)）：兩個 agent 定義資料夾 `painter/`（工具 `tools/brush.json`＝`sh -c` 三步叫畫筆）、`brush/`（工具 `tools/palette.*` 調色盤），假腦 `brain/fake.py`（看帶哪個工具當畫家或畫筆）＋`brain/fake-alt.json`（換腦用），`run.py`＝三段展示＋`bind_brain()`（frame 放 brain.json＋改寫 tools/brush.json 讓畫筆也換）；測試 `tests/test_paint_demo.py`。

改 proto8 的檔就同步那份。

### `proto8-1/`

tasks：`aos_seq.py`、`aos_par.py`、`aos_if.py`、`aos_not.py`、時鐘 `aos_tick.py`、共用 `aos_tasks.py`（stderr 的錯誤重用 proto8 的 `aos_cli.error()`）、`bin/` 薄入口、測試 `tests/`。逐檔表在 [proto8-1/README.md](../../../../proto8-1/README.md)，demo（daemon 跑 tasks 樹＋寫起來的發現）在 [proto8-1/demo/README.md](../../../../proto8-1/demo/README.md)。
