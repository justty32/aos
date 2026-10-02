← [tick：工作資料夾、任務表與一格 tick](../tick.md)（分檔 6/6）｜所在段落：P-213．每項結束碼紀錄、tasks-blocked 與擋板檔〔建議預設，未拍板〕｜[上一份](05-P-213-結束碼紀錄.md)

### tasks-blocked 與擋板檔

| 檔 | 內容 | 行為 |
|---|---|---|
| `.aos/tick/tasks-blocked`（ignored） | 〔使用者 2026-10-01 第十六批〕核心只看存不存在、不讀內容（可以是空檔、資料夾） | 每一項前看：在就這一項與後面都不跑、stderr 不印、`after_all` 照跑，紀錄記 `blocked_before`；整格最後核心刪掉。見 [B-620](../../tick.md) |
| `.aos/tick-blocked`（擋板檔，ignored） | 〔使用者 2026-10-01 第十六批〕核心只看存不存在、不讀內容（可以是空檔、資料夾）；要留原因給人看可以寫 | 擋之後各格（不開格、hooks 不跑、stderr 不印、回 0），見 [B-620](../../tick.md) |

範例：正例 [跑到一半](../../../protocol/examples/tick/tick-record.minimal.valid.json)、[全部成功](../../../protocol/examples/tick/tick-record.done.valid.json)、[被 tasks-blocked 擋下](../../../protocol/examples/tick/tick-record.blocked-exit-0.valid.json)、[第一項就被擋](../../../protocol/examples/tick/tick-record.blocked-first.valid.json)、[有任務失敗照樣回 0](../../../protocol/examples/tick/tick-record.exit-0-with-failure.valid.json)、[沒寫 id 的位置字串](../../../protocol/examples/tick/tick-record.position-id.valid.json)、[擋下後照跑 hooks](../../../protocol/examples/tick/tick-record.hooks.valid.json)（B-635）；反例 [有 hooks 而且四個掛點都記到](../../../protocol/examples/tick/tick-record.hooks-points.valid.json)、[跑到一半就有 hooks](../../../protocol/examples/tick/tick-record.hooks-running.valid.json)；反例 [跟任務有關的 hook 沒帶 task_index](../../../protocol/examples/tick/tick-record.hooks-task-no-index.invalid.json)、 [同一項同時有 exit 與 signal](../../../protocol/examples/tick/tick-record.exit-and-signal.invalid.json)、[ended 卻沒有 exit](../../../protocol/examples/tick/tick-record.ended-without-exit.invalid.json)、[沒收場卻記了 blocked_before](../../../protocol/examples/tick/tick-record.blocked-not-ended.invalid.json)、[整格回 1](../../../protocol/examples/tick/tick-record.blocked-exit-1.invalid.json)、[整格回 2](../../../protocol/examples/tick/tick-record.exit-2.invalid.json)、[整格回 3](../../../protocol/examples/tick/tick-record.exit-3.invalid.json)；[記了結束碼 0](../../../protocol/examples/tick/tick-record.zero-recorded.invalid.json)、[hook 記了結束碼 0](../../../protocol/examples/tick/tick-record.hook-zero-recorded.invalid.json)、[沒有 ran](../../../protocol/examples/tick/tick-record.no-ran.invalid.json)、[沒有 index](../../../protocol/examples/tick/tick-record.no-index.invalid.json)；`record.json` 本體：正例 [開格時](../../../protocol/examples/tick/tick-record-file.open.valid.json)、[有 hooks 而且被擋下](../../../protocol/examples/tick/tick-record-file.hooks.valid.json)、[跑到一半就有 hooks](../../../protocol/examples/tick/tick-record-file.hooks-running.valid.json)，反例 [ran 直接寫數字](../../../protocol/examples/tick/tick-record-file.inline-ran.invalid.json)、[$ref 指錯檔](../../../protocol/examples/tick/tick-record-file.wrong-ref.invalid.json)；補查反例 [index 不小於 ran](../../../protocol/examples/tick/tick-record.index-not-below-ran.invalid.json)、[blocked_before 不是 id](../../../protocol/examples/tick/tick-record.blocked-not-id.invalid.json)。

## P-214．tick 模組 `tasks-blocked`〔使用者 2026-10-01 第十六批；第二十批改名〕

行為正本：[B-636](../../tick/tasks-blocked.md)。本條只定寫法。〔使用者 2026-10-01 第二十批：「模組的鍵改成 tasks-blocked」〕原本叫 `tasks_blocked`，改成跟檔名一樣；寫舊名就是陌生的模組鍵，不掛。

```json
{"tasks": [...],
 "modules": {"tasks-blocked": {"insts": [
   {"id": "notify", "argv": ["sh", "-c", "echo \"$AOS_TASK_ID 被擋下\" >> blocked.log"]},
   {"$ref": "clear-if-ok.json"}]}}}
```

| 位置 | 約束 |
|---|---|
| `modules["tasks-blocked"]` | 物件（可以是 `$ref`）；有寫就掛上。不是物件＝`bad_table`。裡面的陌生鍵不解 |
| `modules["tasks-blocked"].insts` | 必填；陣列（可以是 `$ref`）；可以是空陣列。不是陣列、沒寫＝`bad_table` |
| `insts` 每一項 | 寫法與展開同 `tasks` 每一項（P-202）：inst 物件或整項 `$ref`，已知的鍵開格就展開、`_metainfo` 與陌生鍵不解；合併頂層預設後要有 `argv`；`id` 可省（沒寫＝它在 `insts` 的位置轉字串，只用在 `exec_failed: tasks-blocked/<id>`） |

- 環境變數照任務（P-203）：`AOS_TASK_ID`、`AOS_TASK_INDEX`＝被擋下的那一項，`AOS_TICK_CWD`；沒有 `AOS_HOOK_*`。
- 結束碼不記進紀錄（P-213 的 `ran`、`tasks`、`hooks` 都不動）。
- schema：[tick-tasks](../../../protocol/schemas/tick-tasks.schema.json) 的 `modules["tasks-blocked"]`。範例：正例 [掛了 tasks-blocked](../../../protocol/examples/tick/tasks.tasks-blocked.valid.json)；反例 [沒有 insts](../../../protocol/examples/tick/tasks.tasks-blocked-no-insts.invalid.json)、[某項缺 argv](../../../protocol/examples/tick/tasks.tasks-blocked-no-argv.invalid.json)。

依據：使用者 2026-10-01 第十六批（「1.modules底下 2.對 3.b 4.對，不記錄進記錄，非0沒影響。 5.對」）；第二十批（改名、整份展開）。
