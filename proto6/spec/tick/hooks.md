# hooks：外掛掛點

← [通用 tick](../tick.md)｜[整理區](../README.md)｜格式：[tick 協議](../protocol/tick.md)

## B-635：hooks

**做什麼**：任務表頂層鍵 `hooks`（跟 `tasks` 同層，不是模組）讓使用者在一格的某些時機插一串 inst，寫法比照 `tasks`（可 `id`、吃頂層預設、同樣的展開與 `exec_failed`）。沒寫就跟沒有這功能一樣。

**掛點**：`before_all`、`before_kind.<kind>`、`after_task.<任務 id>`、`after_kind.<kind>`、`after_every_task`、`after_all`。一項任務前後的順序是由專到泛：tasks-blocked 檢查 → `before_kind` → 任務 → `after_task` → `after_kind` → `after_every_task`。`kind` 是任務自己寫的任意字串，沒有就不觸發 `*_kind`。

**原則**：

- hooks 是**外掛**，不是任務：碼只記進紀錄的 `hooks.<掛點>`（0 不記）、**不影響 tick 結束碼**、不算 `ran`、hook 之間不看 tasks-blocked。
- `after_all` 在被 tasks-blocked 擋下時**照跑**（它跟任務無關，這正是它存在的理由）；busy、擋板檔、`bad_table` 時全部掛點都不跑。被擋下沒跑到的任務不觸發它的 hook。
- 所有 hooks 跑完才寫 `ended:true`，所以 hook 跑到一半被殺，下一格的 `last/` 是 `ended:false`；`before_all` 可據此做當機還原。
- hook 拿 `AOS_HOOK_*`、不拿一般任務的 `AOS_TASK_*`；只有 `after_task`／`after_every_task`／`after_kind` 另拿剛跑完那項的 `AOS_TASK_ID`、`AOS_TASK_INDEX`、`AOS_TASK_EXIT`（見 C-10）。
- 版本管理不內建：用 hooks 加普通 git 指令即可（`before_all` 看 `last/` 是否 `ended:false` 就還原，`after_every_task` 依 `AOS_TASK_EXIT` 提交或還原；`.aos/` 自己排除）。

程式：`lib/aos_tick_hooks.py`、`lib/aos_tick_table.py`；測試：`tests/test_tick_hooks_after_all.py`、`tests/test_tick_hooks_points.py`、`tests/test_tick_kind.py`。範例：`protocol/examples/tick/tasks.hooks*.json`。
