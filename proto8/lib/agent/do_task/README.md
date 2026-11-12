# do_task — 在自己的 history 裡做一段任務，做完只留總結（save／load）

← [lib](../../README.md)｜設計、代定、待裁：[thinking 11-11 fork-and-do-task/02](../../../thinking/2026-11/11/fork-and-do-task/02-do_task.md)

使用者 11-11：「另一種是save/load，也就是從在呼叫do_task那時候留下一個紀錄點，等做完task後使用self_history修改history，將進行這段task的過程中的history做總結，然後退回load那邊」；選項框裁「do_task有兩個子指令，一個是開始，一個是結束。結束的時候要附上總結」「eca 不給 do_task」。派工用 `subagent` 或 `fork`。

| op | 參數 | 做什麼 |
|---|---|---|
| `start` | `task`（選填，一句話） | 叫我的那則 assistant＝紀錄點，記進工具小格 `tasks.json`；任務裡再 start＝巢狀（最多 5 層） |
| `end` | `summary`（必給）、`keep_others`（選填，預設 false） | 收最裡面那段：紀錄點那則與它的 tool 結果之後、到叫 end 的那則之前的訊息換成一則 `[aos] summary: lines A-B, N messages. Task "…" ended: …`（role user）。別人給的 user 訊息（信、goal 提醒、new_mail 通知）預設一起摺（使用者 11-11「可選。預設清掉。」；原文照舊留檔，end 的結果說摺了幾則別人的）；`keep_others: true`＝這些不摺，照原順序接在總結後面 |
| `status` | — | 列開著的任務（外到內）、紀錄點現在第幾行 |

改 history 全走 `aos-agent history`（同 self_history：`ctl who`、`ls --json`、`keep_others` 有要留的訊息時先 `set` 挪到段尾、再 `summarize` 一次），原文照舊進 `history_removed.jsonl`。叫 end 那則與它的結果照常由 act 接在後面。只看 history 的形狀判身體：沒有「叫到一半的 tool call」＝`BodyUnsupported`（eca）。只在 daemon 下跑的 agent 能用。

摺疊前後（真 daemon＋假腦實跑）：

```
before end                                   after
1 user       Go.                             1 user       Go.
2 assistant  -> do_task(start)               2 assistant  -> do_task(start)
3 tool       Task started (depth 1) ...      3 tool       Task started (depth 1) ...
4 assistant  -> peek_now_time({})            4 user       [aos] summary: lines 4-7, 4 messages. Task "Find the time" ended: It is today.
5 tool       2026-11-11T06:55:05Z            5 assistant  -> do_task(end)
6 assistant  -> peek_now_time({})            6 tool       Task ended (depth 1) "Find the time".
7 tool       2026-11-11T06:55:06Z                         4 messages (lines 4-7) are now one summary at line 4; the originals are in history_removed.jsonl in the stack of bob.
8 assistant  -> do_task(end)                 7 assistant  Done.
```

測試：`tests/test_do_task.py`（假 aos-agent，history 那半是真的 `aos_agent.history`）；`templates/tests/agent-fsm/test_do_task_fold.py`（真 daemon＋假腦：摺疊、巢狀、任務中等信〔預設信一起摺、`keep_others` 信留著〕、停掉再起來）。
