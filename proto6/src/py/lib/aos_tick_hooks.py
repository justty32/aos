"""aos-tick 的 hooks（掛點；plan m1h-hooks-module.md、spec B-635）：跑 `after_all` 那一串。

設定在任務表頂層 `hooks`（跟 `tasks` 同層）。〔使用者裁定 2026-10-01〕「hooks中的掛點所提供的，
比如"after_cell":[{},{},...]，就比照tasks」「可以一串」「會記錄」；同日改：「就不讓他當模組了，直接讓他變頂層key」。
讀表與極簡檢查在 aos_tick_table.check_table（展開時機比照 tasks，結果是 `Table.after_all`），這裡只管跑：

- 目前只開 `after_all`：照表跑完（含被停格檔停下）之後跑；擋板、busy、tick 自己出錯時走不到這裡。
- 跑法跟任務一模一樣（aos_tick.run_one：吃頂層預設、同樣的 cwd 規則、`AOS_TICK_CWD`、`AOS_TASK_ID`、
  `AOS_TASK_INDEX`——ID／INDEX 是該 hook 在 after_all 裡的 id／位置）。
- 不看停格檔、每項的碼照實記、接著跑下一項，不影響 tick 的結束碼。
- 紀錄：本格 `current.json` 的 `hooks.after_all`（格式同 `tasks` 每項），寫在 `ended:true` 之後（Record.add_hook）。

POC 總原則：默認一切正常，不寫邊緣處理。
"""

__all__ = ["run_after_all"]


def run_after_all(cwd, defaults, after_all, record, run_one):
    """照順序跑每個 after_all 項（[(項, id)]）；`run_one` 是 aos_tick.run_one。每項跑完記進紀錄。"""
    record.start_hooks("after_all")
    for index, (item, hook_id) in enumerate(after_all):
        kind, value = run_one(cwd, defaults, item, hook_id, index, label="after_all/")
        record.add_hook("after_all", hook_id, kind, value)
