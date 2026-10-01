"""aos-tick 的 hooks（掛點；plan m1h-hooks-module.md、spec B-635）：跑 `after_all` 那一串。

設定在任務表頂層 `hooks`（跟 `tasks` 同層）。〔使用者裁定 2026-10-01〕「hooks中的掛點所提供的，
比如"after_cell":[{},{},...]，就比照tasks」「可以一串」「會記錄」；同日改：「就不讓他當模組了，直接讓他變頂層key」。
讀表與極簡檢查在 aos_tick_table.check_table（展開時機比照 tasks，結果是 `Table.after_all`），這裡只管跑：

- 目前只開 `after_all`：照表跑完（含被停格檔停下）之後跑；擋板、busy、tick 自己出錯時走不到這裡。
- 跑法跟任務一模一樣（aos_tick.run_one：吃頂層預設、同樣的 cwd 規則、`AOS_TICK_CWD`），只有環境變數不同。
  〔使用者裁定 2026-10-01 第十批〕「幫我添加AOS_HOOK_TYPE, AOS_HOOK_INDEX, AOS_HOOK_ID……AOS_HOOK_INDEX, _ID會替代TASK_ID, INDEX」：
  hook 拿到 `AOS_HOOK_POINT`（掛點名，例如 `after_all`；使用者暫名 AOS_HOOK_TYPE）、`AOS_HOOK_INDEX`（在該掛點陣列的位置，從 0）、
  `AOS_HOOK_ID`（hook 的 id，沒寫＝位置轉字串），不給 `AOS_TASK_ID`／`AOS_TASK_INDEX`（after_all 不屬於任何任務；
  連 tick 自己環境裡繼承來的也拿掉，見 aos_tick_run._env）。之後開 before_task／after_task 這類掛點時，
  才會再加 `AOS_TASK_ID`／`AOS_TASK_INDEX` 指向被掛的那個任務（只寫進 spec，沒做）。
- 不看停格檔、每項的碼照實記、接著跑下一項，不影響 tick 的結束碼。
- 紀錄：本格紀錄的 `hooks.after_all`（格式同 `tasks` 每項；第九批拆檔後在 `tick/current/hook-exits.json`，
  record.json 用 `"hooks":{"$ref":"hook-exits.json"}` 指過去）。收尾（Record.finish，`ended:true`）時已先寫好
  `{"after_all":[]}`，每項跑完由 Record.add_hook 記。
  〔使用者 2026-10-01 第八批〕「hooks也是」：只記不是 0 的，每筆 `{"id","index","exit"}`；hooks 不記 ran
  （hooks 不看停格檔、一定全跑，收尾時 `after_all: []` 先寫好就知道要開始跑了；tick 中途被殺的情況照 POC 默認不管）。

POC 總原則：默認一切正常，不寫邊緣處理。
"""

__all__ = ["run_after_all", "hook_vars"]


def hook_vars(point, hook_id, index):
    """hook 自己的 `AOS_*`（不含 `AOS_TICK_CWD`，那個 run_one 加）。"""
    return {"AOS_HOOK_POINT": point, "AOS_HOOK_INDEX": str(index), "AOS_HOOK_ID": str(hook_id)}


def run_after_all(cwd, defaults, after_all, record, run_one):
    """照順序跑每個 after_all 項（[(項, id)]）；`run_one` 是 aos_tick.run_one。每項跑完記進紀錄。"""
    for index, (item, hook_id) in enumerate(after_all):
        kind, value = run_one(cwd, defaults, item, hook_id, hook_vars("after_all", hook_id, index), label="after_all/")
        record.add_hook("after_all", hook_id, index, kind, value)
