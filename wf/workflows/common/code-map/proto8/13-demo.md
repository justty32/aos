← [入口](../proto8.md)｜涵蓋：`proto8/demo/`（外部 coding agent 範本 eca-claude、loop／fsm agent 範本 agent-fsm、llm-kernel、判官範本 daemon-judge／procs-kernel；新功能原型劇本在 demo/docs/05）

用法、跑法與錯誤代號以 [demo/README](../../../../../proto8/demo/README.md) 為準。路徑相對於該段標題的資料夾。

11-04 使用者「demo中的，用不到的全部刪掉，也不用封存了」：`run.sh`、agent-gus、hal、kai、liv、meg、pip、talk、eca-codex、daemon、daemon-2、daemon-3 刪了；agent-bob、ann、eve 與 tick 先搬進 tests/fixtures，同天隨 proto8/tests 刪了。

## `demo/eca-claude/`（外部 coding agent 範本；當時 aos-eca add 的預設範本，11-04 晚 aos-eca 併進 aos-agent、`aos-agent ctl add` 不給預設）

| 檔 | 負責什麼 |
|---|---|
| `_entry` | `["aos-loop", "loop.json"]` |
| `loop.json` | 停著等版：`aos-eca-turn --on-empty idle --on-busy yield` |
| `cli.json`、`tools.json`、`agents.json`、`llm.json` | CLI 種類與旗標（沒有 `--model`）；工具註冊檔（clock、self_tools、agents，11-05 裁「內建」；memory 指 `tools/memory/` 包裝資料夾〔同 agent-fsm〕）；`cli.json` 的 `tools_flags` `["--memory", "memory"]`＝aos-mcp 在 initialize 的 `instructions` 給知識庫根（11-05 晚 K3）；工具 agents 的設定 `{"max_children": 4}`；腦設定 `{"model": "sonnet"}`（cli_session 疊 `$AOS_STACK/llm.json` 補 `--model`，11-04 晚） |
| `interfaces.json` | 宣告遵守 `aos-agent` 介面，選配 `screen`、`tools`、`llm`（`"llm.json"`＝設定檔路徑，11-04 晚） |
| `screen/`（`_entry`、`interfaces.json`） | 子介面 screen：`_entry`＝`["aos-eca-screen", "--eca", ".."]`（11-05 D6）、宣告 `aos-agent/screen` |

## `demo/agent-fsm/`（aos 自己的 loop／fsm agent 範本；11-04）

設計：[thinking 11-04 loop-fsm-agent](../../../../../proto8/thinking/2026-11/04/loop-fsm-agent/README.md)；問腦經 llm kernel：[think-as-function 03 § 1](../../../../../proto8/thinking/2026-11/04/think-as-function/03-呼叫端.md)（11-04 晚）。四支 `.py` 純標準庫、不 import 隔壁，錯一律 `agent-fsm: 代號 原因`、退 1。

| 檔 | 負責什麼 |
|---|---|
| `_entry` | 單子 `aos-agent ctl add <AOS_CD>`（`cwd`＝`AOS_WS`）：`aos-exec 這個資料夾`＝掛上 daemon（11-05 portable-flow 題 4） |
| `body.json` | 身體的入口 `["aos-loop", "loop.json"]`（`interfaces.json` 的 `entry` 指它；直接跑＝`aos-exec body.json`；11-05 從 `_entry` 搬來） |
| `loop.json` | 停著等版：`exec` 是 `fsm.json`、`interval_ms` 300、開 `ctl`／`state` 窗 |
| `fsm.json` | 四格表：idle `{"0": "think", "10": "idle"}`、think `{"0": "wait", "10": "idle"}`、wait `{"0": "act", "10": "wait", "11": "think"}`（11 是 11-05 edge-agent 加的）、act `{"0": "think", "10": "idle"}`；`_entry` 讓 aos-exec 也能直接跑一格 |
| `idle.py` | idle 格：`$AOS_STACK/queue/` 全部收進 `history.jsonl`、接進去就 `aos-post done`；壞信丟掉寫 `mailbox_warning.txt`；`--prompt` 開場白 |
| `brain.py` | think 格：history＋`--system`＋`--tools`（沒給＝定義 `tools.json` 疊 `$AOS_STACK/tools.json` 覆蓋層，`aos-tools --overlay`，11-05）＋`llm.json`（定義疊 `$AOS_STACK/llm.json` 的 `endpoint`；不寫 `request.model`，11-05）組成請求信 body，寫 `$AOS_STACK/think/request.json`、退 0；不碰網路；沒事做退 10；`--memory NAME`＝工具清單有 NAME 就叫它 `{"op": "read"}`、印的根接在 system 後面（叫壞＝MemoryFailed；11-05 晚 K2） |
| `wait.py` | wait 格：沒 `think/pending.txt`＝`aos-llm send --reply-to think/reply`、記名字、退 10；有＝`aos-llm recv`：沒到 10、到了接一則 assistant 進 history 退 0、kernel 回錯＝自己一行 BrainFailed 退 1；寄之前 `request.json` 的 endpoint 跟現在的 llm.json（定義疊 stack）對不上＝退 11 回 think 重組（11-05 edge-agent） |
| `act.py` | act 格：最後一則 assistant 的 `tool_calls` 逐個 `aos-tools --file … [--overlay $AOS_STACK/tools.json] call`（11-05），結果各接一則 tool、退 0；沒 `tool_calls`＝最後答案、退 10；工具的錯回給腦（stderr 提醒行 `agent-fsm: warning: tool …`）；沒登記、arguments 壞＝回給腦一則 `act: error: ToolUnknown／ArgumentsBad …` |
| `tools/memory/`（`_entry`、`_memory.json`、`_tooldef.json`／`_metainfo.json` 捷徑） | memory 的包裝資料夾（11-05 晚 agent-knowledge K2）：`_entry`＝單子 `["../../../../lib/agent/memory/_entry"]`（不能是捷徑：會被解開、`AOS_CD` 變 lib 那格）、`_memory.json`＝這隻的知識庫 `knowledge/aos` |
| `system.txt`、`tools.json`、`agents.json`、`llm.json` | system 訊息（11-05 晚改英文）；工具登記檔（clock、self_tools、agents，11-05 裁「內建」；memory→`tools/memory`，11-05 晚）；工具 agents 的設定 `{"max_children": 4}`；腦設定（範本 `{}`＝kernel 預設代號；鍵 `endpoint`） |
| `interfaces.json` | 宣告遵守 `aos-agent` 介面，`entry`＝`body.json`（11-05）、選配 `tools`、`llm`（`"llm.json"`，11-04 晚）；brain.py／act.py 疊 `$AOS_STACK/tools.json` 覆蓋層（11-05） |

## `demo/llm-kernel/`（llm kernel 範本；11-04 晚，11-05 改成一台 daemon）

設計：[thinking 11-04 think-as-function](../../../../../proto8/thinking/2026-11/04/think-as-function/README.md)、[11-05 kernel-daemon 07](../../../../../proto8/thinking/2026-11/05/kernel-daemon/07-llm-daemon佈局.md)、[feat-proto 02](../../../../../proto8/thinking/2026-11/05/feat-proto/02-endpoint-packs.md)；說明 [demo/docs/03-llm-kernel](../../../../../proto8/demo/docs/03-llm-kernel.md)。

| 檔 | 負責什麼 |
|---|---|
| `_entry` | `["aos-daemon", "daemon.json"]`（`cd ~/llm_kernel && aos-exec --stack . def`） |
| `daemon.json` | daemon 的身體＝每 300 ms 拍一次 `aos-llm-kernel kernel.json`；表上只有問腦的 `llm_<信件名稱>` 列 |
| `kernel.json` | `slots`、`timeout_ms`、預設 endpoint 函數 `exec`（`lib/base/llm_http`）、預設代號 `endpoint`（`fake`）、`budget.senders` 一格例子（`/tmp/aos-demo-sender` 每天 1 次）、能力包表 `endpoints`（11-05 午 feat-proto：`smart-high`／`stupid-fast`／`luna`／`sol`／`fake`，劇本假腦 `fake-demo-self`／`fake-demo-memory`（先 `memory read me/self_tools` 再加 math，11-05 晚 K5）／`fake-demo-spawn`〔`llm_fake` 的 `script`，路徑用 `$env AOS_CD`＋`$path`〕、慢假腦 `fake-demo-fast`／`fake-demo-slow`〔`fake_slow`，`slots` 1〕） |
| `fake_slow/_entry` | demo 用的慢假腦 endpoint 函數（python3）：睡 `endpoint.delay_s` 秒（沒寫 2、0～60），再把同一份 stdin 交給 `lib/base/llm_fake`、結束碼原樣交回（llm_fake 被訊號殺＝128＋N）；錯 `fake_slow: error: ArgumentsBad`（demo/docs/05 件 3） |

## `demo/daemon-judge/`、`demo/procs-kernel/`（判官範本：kernel 模式 1、2；11-05）

設計：[thinking 11-05 kernel-daemon 02](../../../../../proto8/thinking/2026-11/05/kernel-daemon/02-兩種模式.md)；說明 [demo/docs/04-kernel-modes](../../../../../proto8/demo/docs/04-kernel-modes.md)；判官本體 [`lib/base/judge`](09-lib.md)。

| 檔 | 負責什麼 |
|---|---|
| `daemon-judge/_entry` | `["aos-daemon", "daemon.json"]`（模式 1：`aos-exec` 這個資料夾＝起一台帶判官的 daemon） |
| `daemon-judge/daemon.json` | 身體 `exec`＝單子 `aos-exec ../../lib/base/judge <AOS_CD>/judge.json`、`interval_ms` 300；`procs` 不寫＝空名單，全靠 `requests/` 進來 |
| `procs-kernel/_entry` | `["aos-loop", "loop.json"]`（模式 2：`aos-daemon-ctl add` 它＝0 號 proc） |
| `procs-kernel/loop.json` | 每 300 ms 跑同一張判官單子 |
| `*/judge.json` | 政策範例 `{"allowed": [...], "max_running": N}`：daemon-judge 的白名單 `clock`、`clock2`、`fsm1`、`kid`、`kid1`～`kid4`、`max_running` 4（11-05 午，給 demo/docs/05 件 4）；procs-kernel 白名單 `clock`、`clock2`、`max_running` 2（含 0 號自己） |
