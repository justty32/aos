← [入口](../proto8.md)｜涵蓋：`proto8/demo/`（只剩外部 coding agent 範本 eca-claude）

用法、跑法與錯誤代號以 [demo/README](../../../../../proto8/demo/README.md) 為準。路徑相對於該段標題的資料夾。

11-04 使用者「demo中的，用不到的全部刪掉，也不用封存了」：`run.sh`、agent-gus、hal、kai、liv、meg、pip、talk、eca-codex、daemon、daemon-2、daemon-3 刪了；agent-bob、ann、eve 與 tick 搬到 `tests/fixtures/`（逐檔列在 [02-tests](02-tests.md)）。

## `demo/eca-claude/`（外部 coding agent 範本；aos-eca add 的預設範本）

| 檔 | 負責什麼 |
|---|---|
| `_entry` | `["aos-loop", "loop.json"]` |
| `loop.json` | 停著等版：`aos-eca-turn --on-empty idle --on-busy yield` |
| `cli.json`、`tools.json` | CLI 種類與旗標；工具註冊檔 |
