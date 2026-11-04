← [入口](../proto8.md)｜涵蓋：`proto8/demo/`（外部 coding agent 範本 eca-claude、loop／fsm agent 範本 agent-fsm）

用法、跑法與錯誤代號以 [demo/README](../../../../../proto8/demo/README.md) 為準。路徑相對於該段標題的資料夾。

11-04 使用者「demo中的，用不到的全部刪掉，也不用封存了」：`run.sh`、agent-gus、hal、kai、liv、meg、pip、talk、eca-codex、daemon、daemon-2、daemon-3 刪了；agent-bob、ann、eve 與 tick 先搬進 tests/fixtures，同天隨 proto8/tests 刪了。

## `demo/eca-claude/`（外部 coding agent 範本；aos-eca add 的預設範本）

| 檔 | 負責什麼 |
|---|---|
| `_entry` | `["aos-loop", "loop.json"]` |
| `loop.json` | 停著等版：`aos-eca-turn --on-empty idle --on-busy yield` |
| `cli.json`、`tools.json`、`llm.json` | CLI 種類與旗標（沒有 `--model`）；工具註冊檔；腦設定 `{"model": "sonnet"}`（cli_session 疊 `$AOS_STACK/llm.json` 補 `--model`，11-04 晚） |
| `interfaces.json` | 宣告遵守 `aos-agent` 介面，選配 `screen`、`tools`、`llm`（`"llm.json"`＝設定檔路徑，11-04 晚） |
| `screen/`（`_entry`、`interfaces.json`） | 子介面 screen：`_entry`＝`["aos-eca-screen", ".."]`、宣告 `aos-agent/screen` |

## `demo/agent-fsm/`（aos 自己的 loop／fsm agent 範本；11-04）

設計：[thinking 11-04 loop-fsm-agent](../../../../../proto8/thinking/2026-11/04/loop-fsm-agent/README.md)；問腦經 llm kernel：[think-as-function 03 § 1](../../../../../proto8/thinking/2026-11/04/think-as-function/03-呼叫端.md)（11-04 晚）。四支 `.py` 純標準庫、不 import 隔壁，錯一律 `agent-fsm: 代號 原因`、退 1。

| 檔 | 負責什麼 |
|---|---|
| `_entry` | `["aos-loop", "loop.json"]` |
| `loop.json` | 停著等版：`exec` 是 `fsm.json`、`interval_ms` 300、開 `ctl`／`state` 窗 |
| `fsm.json` | 四格表：idle `{"0": "think", "10": "idle"}`、think `{"0": "wait", "10": "idle"}`、wait `{"0": "act", "10": "wait"}`、act `{"0": "think", "10": "idle"}`；`_entry` 讓 aos-exec 也能直接跑一格 |
| `idle.py` | idle 格：`$AOS_STACK/queue/` 全部收進 `history.jsonl`、接進去就 `aos-post done`；壞信丟掉寫 `mailbox_warning.txt`；`--prompt` 開場白 |
| `brain.py` | think 格：history＋`--system`＋`--tools`＋`llm.json`（定義疊 `$AOS_STACK/llm.json` 的 `endpoint`／`model`）組成請求信 body，寫 `$AOS_STACK/think/request.json`、退 0；不碰網路；沒事做退 10 |
| `wait.py` | wait 格：沒 `think/pending.txt`＝`aos-llm send --reply-to think/reply`、記名字、退 10；有＝`aos-llm recv`：沒到 10、到了接一則 assistant 進 history 退 0、kernel 回錯退 1 |
| `act.py` | act 格：最後一則 assistant 的 `tool_calls` 逐個 `aos-tools --file … call`，結果各接一則 tool、退 0；沒 `tool_calls`＝最後答案、退 10；工具的錯回給腦 |
| `system.txt`、`tools.json`、`llm.json` | system 訊息；工具登記檔（clock）；腦設定（範本 `{}`＝kernel 預設代號；鍵 `endpoint`、`model`） |
| `interfaces.json` | 宣告遵守 `aos-agent` 介面，選配 `tools`、`llm`（`"llm.json"`，11-04 晚）；brain.py／act.py 先看 `$AOS_STACK/tools.json` 副本 |

## `demo/llm-kernel/`（llm kernel 範本；11-04 晚）

設計：[thinking 11-04 think-as-function](../../../../../proto8/thinking/2026-11/04/think-as-function/README.md)；說明 [demo/docs/03-llm-kernel](../../../../../proto8/demo/docs/03-llm-kernel.md)。

| 檔 | 負責什麼 |
|---|---|
| `_entry` | `["aos-loop", "loop.json"]` |
| `loop.json` | 每 300 ms 拍一次 `aos-llm-kernel kernel.json` |
| `kernel.json` | 信箱、`slots`、`timeout_ms`、預設 endpoint 函數 `exec`（`lib/base/llm_http`）、預設代號 `endpoint`（`fake`）、代號表 `endpoints`（luna／sol／local-qwen／fake） |
