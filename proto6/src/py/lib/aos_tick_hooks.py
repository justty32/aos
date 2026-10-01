"""aos-tick 的 hooks（掛點；plan m1h-hooks-module.md、spec B-635）：跑 `after_all` 那一串。

設定在任務表頂層 `hooks`（跟 `tasks` 同層）。〔使用者裁定 2026-10-01〕「hooks中的掛點所提供的，
比如"after_cell":[{},{},...]，就比照tasks」「可以一串」「會記錄」；同日改：「就不讓他當模組了，直接讓他變頂層key」。
讀表與極簡檢查在 aos_tick_table.check_table（展開時機比照 tasks，結果是 `Table.after_all`），這裡只管跑：

- 掛點（第十七批起四個）：`before_all`（開格後、第一項〔含 tasks-blocked 的檢查〕之前）、`after_task`（{任務 id: [inst…]}，
  那一項跑完）、`after_every_task`（每一項跑完；同一項兩個都有時先 after_task 再 after_every_task）、`after_all`
  （照表跑完或被 tasks-blocked 擋下之後）。擋板、busy、tick 自己出錯時都走不到這裡；被擋下沒跑的任務不觸發。
  〔使用者 2026-10-01 第十七批〕「那確實是需要AOS_TASK_EXIT」「"hooks":{"after_task":{"a":..., "b":...}}，然後是after_every_task。」
  跟任務有關的兩個掛點另給 `AOS_TASK_ID`、`AOS_TASK_INDEX`、`AOS_TASK_EXIT`（剛跑完那一項；被訊號 N 殺＝128+N）。
- 跑法跟任務一模一樣（aos_tick.run_one：吃頂層預設、同樣的 cwd 規則、`AOS_TICK_CWD`），只有環境變數不同。
  〔使用者裁定 2026-10-01 第十批〕「幫我添加AOS_HOOK_TYPE, AOS_HOOK_INDEX, AOS_HOOK_ID……AOS_HOOK_INDEX, _ID會替代TASK_ID, INDEX」：
  hook 拿到 `AOS_HOOK_POINT`（掛點名，例如 `after_all`；使用者暫名 AOS_HOOK_TYPE）、`AOS_HOOK_INDEX`（在該掛點陣列的位置，從 0）、
  `AOS_HOOK_ID`（hook 的 id，沒寫＝位置轉字串），不給 `AOS_TASK_ID`／`AOS_TASK_INDEX`（after_all 不屬於任何任務；
  連 tick 自己環境裡繼承來的也拿掉，見 aos_tick_run._env）。之後開 before_task／after_task 這類掛點時，
  才會再加 `AOS_TASK_ID`／`AOS_TASK_INDEX` 指向被掛的那個任務（只寫進 spec，沒做）。
- 不看 tasks-blocked、每項的碼照實記、接著跑下一項，不影響 tick 的結束碼。
- 紀錄：本格紀錄的 `hooks.<掛點>`（格式同 `tasks` 每項；跟任務有關的另帶 `task_index`；在 `tick/current/hook-exits.json`，
  record.json 用 `"hooks":{"$ref":"hook-exits.json"}` 指過去）。第十七批起開格（Record.open）就寫好各掛點的 `[]`，
  每項跑完由 Record.add_hook 記。
  〔使用者 2026-10-01 第八批〕「hooks也是」：只記不是 0 的，每筆 `{"id","index","exit"}`；hooks 不記 ran
  （hooks 不看停格檔、一定全跑，收尾時 `after_all: []` 先寫好就知道要開始跑了；tick 中途被殺的情況照 POC 默認不管）。

POC 總原則：默認一切正常，不寫邊緣處理。
"""

__all__ = ["run_point", "run_after_task", "hook_vars", "task_exit"]


def hook_vars(point, hook_id, index):
    """hook 自己的 `AOS_*`（不含 `AOS_TICK_CWD`，那個 run_one 加）。"""
    return {"AOS_HOOK_POINT": point, "AOS_HOOK_INDEX": str(index), "AOS_HOOK_ID": str(hook_id)}


def task_exit(kind, value):
    """第十七批 `AOS_TASK_EXIT`：結束碼；被訊號 N 殺＝128+N（跟 aos-exec、inst 的 exit 一樣）。"""
    return value if kind == "exit" else 128 + value


def run_point(cwd, defaults, point, items, record, run_one, task=None):
    """照順序跑一個掛點的一串（[(項, id)]）；每項跑完記進紀錄。`task`＝(任務 id, index, kind, value)：
    跟任務有關的掛點（after_task、after_every_task）才給，多放 `AOS_TASK_ID`／`AOS_TASK_INDEX`／`AOS_TASK_EXIT`、紀錄帶 task_index。"""
    for index, (item, hook_id) in enumerate(items):
        env = hook_vars(point, hook_id, index)
        label = point + "/"
        task_index = None
        if task is not None:
            task_id, task_index, kind, value = task
            env.update(AOS_TASK_ID=str(task_id), AOS_TASK_INDEX=str(task_index),
                       AOS_TASK_EXIT=str(task_exit(kind, value)))
            if point == "after_task":
                label = "after_task/%s/" % task_id
        k, v = run_one(cwd, defaults, item, hook_id, env, label=label)
        record.add_hook(point, hook_id, index, k, v, task_index)


def run_after_task(cwd, tbl, task_id, index, kind, value, record, run_one):
    """第十七批：一項任務跑完之後——先 `after_task.<這一項的 id>`（鍵比字串；沒寫 id 的任務 id 是位置字串），
    再 `after_every_task`。被 tasks-blocked 擋下、沒跑的任務不會走到這裡。"""
    task = (task_id, index, kind, value)
    if tbl.after_task is not None and str(task_id) in tbl.after_task:
        run_point(cwd, tbl.defaults, "after_task", tbl.after_task[str(task_id)], record, run_one, task)
    if tbl.after_every_task is not None:
        run_point(cwd, tbl.defaults, "after_every_task", tbl.after_every_task, record, run_one, task)
