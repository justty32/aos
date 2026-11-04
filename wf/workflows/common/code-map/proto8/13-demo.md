← [入口](../proto8.md)｜涵蓋：`proto8/demo/`（外部 coding agent 範本 eca-claude、loop／fsm agent 範本 agent-fsm）

用法、跑法與錯誤代號以 [demo/README](../../../../../proto8/demo/README.md) 為準。路徑相對於該段標題的資料夾。

11-04 使用者「demo中的，用不到的全部刪掉，也不用封存了」：`run.sh`、agent-gus、hal、kai、liv、meg、pip、talk、eca-codex、daemon、daemon-2、daemon-3 刪了；agent-bob、ann、eve 與 tick 先搬進 tests/fixtures，同天隨 proto8/tests 刪了。

## `demo/eca-claude/`（外部 coding agent 範本；aos-eca add 的預設範本）

| 檔 | 負責什麼 |
|---|---|
| `_entry` | `["aos-loop", "loop.json"]` |
| `loop.json` | 停著等版：`aos-eca-turn --on-empty idle --on-busy yield` |
| `cli.json`、`tools.json` | CLI 種類與旗標；工具註冊檔 |
| `interfaces.json` | 宣告遵守 `aos-agent` 介面，選配 `screen`、`tools`、`llm`（11-04） |
| `screen/`（`_entry`、`interfaces.json`） | 子介面 screen：`_entry`＝`["aos-eca-screen", ".."]`、宣告 `aos-agent/screen` |
| `llm/`（`_entry`、`interfaces.json`） | 子介面 llm：`_entry`＝`["aos-eca-llm", ".."]`、宣告 `aos-agent/llm` |

## `demo/agent-fsm/`（aos 自己的 loop／fsm agent 範本；11-04）

設計：[thinking 11-04 loop-fsm-agent](../../../../../proto8/thinking/2026-11/04/loop-fsm-agent/README.md)。三支 `.py` 純標準庫、不 import 隔壁，錯一律 `agent-fsm: 代號 原因`、退 1。

| 檔 | 負責什麼 |
|---|---|
| `_entry` | `["aos-loop", "loop.json"]` |
| `loop.json` | 停著等版：`exec` 是 `fsm.json`、`interval_ms` 300、開 `ctl`／`state` 窗 |
| `fsm.json` | 三格表：idle `{"0": "think", "10": "idle"}`、think `{"0": "act", "10": "idle"}`、act `"think"`；`_entry` 讓 aos-exec 也能直接跑一格 |
| `idle.py` | idle 格：`$AOS_STACK/queue/` 全部收進 `history.jsonl`、接進去就 `aos-post done`；壞信丟掉寫 `mailbox_warning.txt`；`--prompt` 開場白 |
| `brain.py` | think 格：history＋`--system`＋`--tools` 問 OpenAI 相容端點（沒設 `AOS_BRAIN_URL`＝假腦），接一則 assistant；有 `tool_calls` 退 0、沒有退 10 |
| `act.py` | act 格：最後一則 assistant 的 `tool_calls` 逐個 `aos-tools --file … call`，結果各接一則 tool；工具的錯回給腦 |
| `system.txt`、`tools.json`、`.env` | system 訊息；工具登記檔（clock）；`AOS_BRAIN_MODEL` |
| `interfaces.json` | 宣告遵守 `aos-agent` 介面，選配 `tools`、`llm`（11-04） |
| `llm/`（`_entry`、`interfaces.json`、`llm.py`） | 子介面 llm：`llm.py def\|stack show\|set\|reset`（def＝`../.env` 的 `AOS_BRAIN_*`、stack＝`$AOS_STACK/llm.json`）；brain.py 讀 `llm.json` 蓋過、brain.py／act.py 先看 `$AOS_STACK/tools.json`（11-04） |
