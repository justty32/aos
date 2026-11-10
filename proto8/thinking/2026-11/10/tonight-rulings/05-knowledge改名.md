# 05 knowledge 改名：memory 整家改叫 knowledge，舊名一律不留

← [tonight-rulings](README.md)

## 結論

使用者：「memory_read/write感覺應該改名爲knowledge_read/write」；範圍表：「都改，照這個範圍排進最後一輪」。proto8 不留舊名、不做相容（舊名＝不認得）。

## 改名對照

| 舊 | 新 |
|---|---|
| 工具 `lib/agent/memory_read`、`memory_write`、`memory_export`、`memory_sync`（夾名、登記名、`_tooldef.json` 的 name 與內文） | `knowledge_read`、`knowledge_write`、`knowledge_export`、`knowledge_sync` |
| 共用模組 `lib/agent/memory_fs.py`（函式 `memory_root`） | `knowledge_fs.py`（`knowledge_root`） |
| 工具包 `lib/packs/memory.json`（包名 memory） | `lib/packs/knowledge.json`（包名 knowledge）；兩份範本 `tools.json` 的 `$override` 與兩格跟著改 |
| 環境變數 `AOS_MEMORY` | `AOS_KNOWLEDGE` |
| 工具夾設定檔 `_memory.json` | `_knowledge.json` |
| 錯誤代號 `MemoryMissing`、`MemoryBad` | `KnowledgeMissing`、`KnowledgeBad` |
| brain.py、aos-mcp 的 `--memory NAME`；範本 fsm.json、eca 的 cli.json 傳 `--memory memory_read` | `--knowledge NAME`；`--knowledge knowledge_read` |
| `lib/aos/defs` 讀的 interfaces 鍵 `aos-agent.memory`、分群欄 `memory`（review_round 跟著） | `aos-agent.knowledge`、`knowledge` |
| kernel 假腦 `fake-demo-memory` | `fake-demo-knowledge` |
| knowledge 節點 `aos/memory.json`（根表、packs 節點的 `#/memory`） | `aos/knowledge.json`、`aos/packs.json#/knowledge` |
| 測試檔 `test_memory_root.py`、`test_memory.py` | `test_knowledge_root.py`、`test_knowledge.py` |

工具說明裡講「the shared memory」「memory root」的句子改成 knowledge base；`Details: knowledge_read aos/…` 指標從根逛過、都指得到。

## 沒改的（例外）

- 跟本件無關的 memory：cgroup `memory.max`／`MemoryMax`、`memory_max` 上限、`MemoryError`、ctl state 的 `memory_bytes`、aos-json help 的 in memory、progress_board 讀 `/proc/meminfo`、心智模型「stack = memory」。
- 歷史：`thinking/`（含夾名 `json-memory`）、`wf/session_logs`、`wf/inbox/done`、`wf/workflows/*/reports`、各 archive；`proto8/feedback/memory_write.jsonl`（舊回饋紀錄，之後新回饋會進 `knowledge_write.jsonl`）；brain.py、templates/docs 講「原本是 MemoryFailed」的舊事；packs README 的使用者原話「memory_*一組」。
- 條文（CONCEPTS、CONVENTION、NORMS）講到舊名的地方只加「（11-10 改名 knowledge_…）」註；NORMS 環境變數表（四種性質 ②）、附錄 3 舊名對照、附錄 4 持久檔直接改成新名。
- P-41 的例子 `aos-exec memory/add`、登記名 `memory_add` 是講子資料夾的假想例，不改。

## 要重建什麼

- 舊定義裡的 `_memory.json` 要改名成 `_knowledge.json`（不改＝當沒設，退 `AOS_KNOWLEDGE`）。
- 設了 `AOS_MEMORY` 的地方（`.env`、登記檔 `env`、殼）改設 `AOS_KNOWLEDGE`，舊名不再讀。
- stack 覆蓋層（`aos-agent tools add` 登記過的）或 repo 外登記檔裡指 `lib/agent/memory_*` 的格，路徑失效：重登記成 `knowledge_*`（或整份 stack 重建）；用 `--memory` 起的 brain.py／aos-mcp 改 `--knowledge`。
- 定義 `interfaces.json` 若宣告了 `memory` 鍵，改成 `knowledge`。
- repo 外的 `~/.cache/aos-mcp-aos/tools.json`（使用者 Claude 接 aos MCP）兩格的 `path` 與 `AOS_MEMORY` 要手改，改完重啟 MCP server。
