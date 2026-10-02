# tick 模組 `tasks-blocked`

← [通用 tick](../tick.md)｜[hooks](hooks.md)｜格式：[tick 協議](../protocol/tick.md)

## B-636：tick 模組 `tasks-blocked`

**做什麼**：核心每一項之前看到 tasks-blocked 就直接擋下；任務表頂層 `modules["tasks-blocked"].insts` 讓它改成「先跑一串 inst，跑完再看一次」，檔被刪了就放行，還在才擋。

**原則**：

- 這串 inst 是**清障機會**，不是任務：碼不記、不算 `ran`、彼此不看碼，全部跑完才重看一次檔；同一項之前只跑一次。
- 環境變數照任務：`AOS_TASK_ID`／`AOS_TASK_INDEX` 是被擋下那一項的，沒有 `AOS_HOOK_*`。
- 按 kind 擋時，每個「本來要被擋」的項之前都先跑這串。
- 寫壞（不是物件、沒 `insts`、項沒 `argv`）＝`bad_table`；開不起來照任務印 `exec_failed` 後接著跑。
- 模組鍵就是 `tasks-blocked`（寫舊名 `tasks_blocked` 是陌生鍵，不掛）。

程式：`lib/aos_tick.py` 的 `run_on_blocked()`、`lib/aos_tick_table.py`；測試：`tests/test_tick_blocked.py`。
