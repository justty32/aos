# tools/task：派工、看任務表、審查、問人、縮記憶

← [tools README](../README.md)｜格式：[spec/team/](../../spec/team/README.md)

給團隊成員（領隊、工人、審查）用的五支工具，**不叫模型、不直接改任務表**：寫的只有自己的 outbox（牢裡 `/work/outbox`），郵差再驗一次、開單、改狀態。
`aos-team init` 照模板裝（`--only` 挑幾支）並寫好 `config.json`；不在團隊裡的 agent 用不了（`ConfigInvalid`）。

| 工具 | 誰有 | 做什麼 | 參數（* 必填） |
|---|---|---|---|
| `handoff` | 領隊 | 寫一份 `kind: handoff` 申請；郵差開 `t-NNNN` 並派給負責人 | `assignee`*、`workflow`*（入口檔，沒有寫「無」）、`goal`*、`done_when`*、`facts`、`max_attempts`（1～10）、`deadline_minutes` |
| `board` | 全部 | 唯讀看 `/work/board`（＝`team/tasks/`）：`op: ls`（`all: true` 含結束的）、`op: show` | `op`、`task`、`all` |
| `review_result` | 審查 | 逐條回一張審查子單（`t-0001.r1`），每條 `{i, pass, why}` 都要有 | `task`*、`items`* |
| `ask_human` | 領隊、工人 | 寫一份 `kind: ask` 申請；答案之後是一封新信 | `question`*、`options`、`default`（要在 options 裡）、`reply_to` |
| `compact_me` | 領隊、工人 | 寫一份 `kind: compact` 申請縮**自己**的記憶（不收 `member`）；郵差投進自己家的 `compact-req/`，下一次閒著時縮（[compact-more.md §5](../../spec/agent/compact-more.md)） | `reason`（≤ 500 字）、`keep_rounds`（0～1000）、`max_tokens`（≥ 100） |

- 寫完就回一句「queued … end this turn」：沒有「等回信」的工具，回信到了是新的一輪。
- 擋手誤（名冊外的負責人、派給自己、`done_when` 種類不對、審查漏條）回 `BadArguments`；名冊的快照在 `config.json`，真正的把關在郵差。
- 錯誤格式跟 base 一樣：退 1、stdout 最後一行 `{"ok": false, "error": …, "message": …}`；另有 `ConfigInvalid`（沒團隊設定）、`NoOutbox`／`NoBoard`（沒掛進牢）、`WriteFailed`。
- 給模型看的描述（`function` 整段 JSON）五支合計約 2640 字元（約 660 token），其中 `compact_me` 369 字元；每個成員只裝 `only` 列的幾支。
- 測試：[`lib/test/test_team_init.py`](../../lib/test/test_team_init.py)（`ToolUnitTests` 不關牢直接跑；`TeamIntegrationTests` 真 kernel＋bwrap）；`compact_me` 在 [`test_team_notes_compact.py`](../../lib/test/test_team_notes_compact.py)。
