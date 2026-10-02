# proto6/src/py — hooks 與 tasks-blocked

← [proto6/src/py README](../README.md)｜上一份：[aos-tick](tick.md)｜下一份：[aos-daemon](daemon.md)

## hooks：外掛掛點（m1h）

照 [plan m1h](../../../plan/m1h-hooks-module.md) 寫的，spec 正本 [B-635](../../../spec/settled/tick/hooks.md)。在任務表頂層寫 `hooks`（跟 `tasks` 同層；不當模組）。2026-10-01 第十七批起四個掛點：

```json
{
  "tasks": [{"id": "build", "argv": ["make"]}, {"argv": ["./report.sh"]}],
  "hooks": {
    "before_all": [{"id": "recover", "argv": ["./recover.sh"]}],
    "after_task": {"build": [{"id": "notify", "argv": ["./notify.sh"]}], "1": [{"argv": ["./after-report.sh"]}]},
    "after_every_task": [{"id": "log", "argv": ["sh", "-c", "echo \"$AOS_TASK_ID $AOS_TASK_EXIT\" >> tasks.log"]}],
    "after_all": [{"argv": ["sh", "-c", "date >> ticks.log"]}]
  }
}
```

| 掛點 | 什麼時候 | 另給的環境變數 |
|---|---|---|
| `before_all` | 開格後、第一項（含 tasks-blocked 的檢查）之前 | `AOS_HOOK_*` |
| `after_task.<任務 id>` | 那一項跑完（沒寫 id 的任務用位置字串當鍵；不存在的 id 不跑、不報錯） | `AOS_HOOK_*`＋剛跑完那一項的 `AOS_TASK_ID`、`AOS_TASK_INDEX`、`AOS_TASK_EXIT`（被訊號 N 殺＝128+N） |
| `after_every_task` | 每一項跑完；同一項也有 `after_task` 時排在它後面 | 同上 |
| `after_all` | 照表跑完或被 tasks-blocked 擋下之後 | `AOS_HOOK_*` |

- 寫法與指示詞展開都比照 `tasks`（開格整份展開，第二十批）：每項一個 inst 物件，`id` 可省（沒寫＝在自己那個陣列的位置字串）、吃頂層預設、跑法跟任務一樣。`AOS_HOOK_INDEX` 是在自己那個陣列的位置（`after_task` 每個任務 id 各自從 0 數）。
- 跑每一項前，`AOS_TASK_ID`、`AOS_TASK_INDEX`、`AOS_TASK_EXIT`、`AOS_HOOK_*` 一律先從繼承的環境拿掉（`aos_tick_run.RUN_VARS`），所以 `AOS_TASK_EXIT` 只有那兩個掛點有。`aos_tick_hooks.run_point()`、`run_after_task()` 組變數。
- 不看 tasks-blocked；被它擋下沒跑的任務不觸發 `after_task`、`after_every_task`。每項的碼照實記、接著跑下一項；不影響 tick 的結束碼（照舊 0）。擋板、busy、表壞時一個都不跑。
- 格式錯（`hooks` 不是物件、陣列的掛點不是陣列、`after_task` 不是物件或某個值不是陣列、某項不是物件、合併後沒 `argv`）＝`bad_table:`、回 1，開格前就擋。`hooks` 裡其他鍵照收不理。寫在 `modules.hooks` 底下的不會跑。
- 紀錄：任務表寫了哪幾個掛點，**開格**時就把 `hook-exits.json`（各掛點 `[]`）寫好、`record.json` 帶 `hooks` 的 `$ref`；每跑完一個**結束碼不是 0** 的 hook 加一筆，格式同 `tasks`（`id`、`index`、`exit` 或 `signal`），`after_task`、`after_every_task` 另帶 `task_index`；0 的不記，hooks 不記 `ran`；下一格跟著進 `last/`。
- 某個 hook 沒跑成時 stderr 是 `exec_failed: <掛點>/<id>: …`（`after_task` 是 `after_task/<任務 id>/<id>`）。
- 用 hooks 加普通 git 指令取代 `aos-git`（第十七批暫緩）的寫法見 [B-635 範例](../../../spec/settled/tick/hooks.md#範例用-hook-加普通-git-指令管版本)。

## tick 模組 `modules["tasks-blocked"]`（B-636）

使用者 2026-10-01 第十六批，spec [B-636](../../../spec/settled/tick/tasks-blocked.md)、格式 P-214。任務表 `modules` 底下寫：

```json
"modules": {"tasks-blocked": {"insts": [{"id": "notify", "argv": ["sh", "-c", "echo $AOS_TASK_ID >> blocked.log"]}]}}
```

- 某一項之前發現 `<狀態資料夾>/tick/tasks-blocked`：先依序跑 `insts`（全部跑完、不看彼此的碼），再看一次——檔被刪了就放行這一項與後面的，還在就照預設擋下（`blocked_before`）。同一項之前只跑一次；放行後又被擋，那一項之前再跑。
- 碼不記進紀錄、非 0 沒影響。環境照任務：`AOS_TASK_ID`／`AOS_TASK_INDEX`＝被擋下的那一項、`AOS_TICK_CWD`；沒有 `AOS_HOOK_*`。
- 寫法與展開比照 `tasks`（開格整份展開；〔第二十批〕模組鍵由 `tasks_blocked` 改名 `tasks-blocked`，跟檔名一樣）。開不起來印 `exec_failed: tasks-blocked/<id>`。
- 沒掛＝看到就擋下。整格最後照樣刪 tasks-blocked。

測試 `tests/test_tick_blocked.py` 的 `TasksBlockedModule`（7 條）。
