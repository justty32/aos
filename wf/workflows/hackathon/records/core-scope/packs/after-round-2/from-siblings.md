# 第 2 輪之後的資料包 — 兄弟專案裡可以抄的

← [本份索引](README.md)｜[資料包](../README.md)｜[本場索引](../../README.md)｜[hackathon](../../../../README.md)｜[同一塊：← R1 後](../after-round-1/from-siblings.md)

repo 之外、兄弟專案裡可以直接拿來抄的實作與測例。

## 4. 兄弟專案裡可以抄的

- `/mnt/c/code/mine/simple_tools/agent-machine/workbench/2026-08-14/p0-function-python/aos_p0.py` 的 `_save_result()`、`_terminal()` 與 `recover()` 已把 receipt JSON、receipt-ready 與 terminal 分成三步；receipt 完整時 recover 只補後續 marker，不再執行 effect。
- `/mnt/c/code/mine/simple_tools/agent-machine/workbench/2026-08-14/p0-function-python/test_p0.py` `test_recover_receipt_without_terminal_only_projects_terminal()` 正好是 p1 的 response／receipt 已 commit、done／terminal 未 commit 窗口；`test_invocation_id_table_cannot_escape_root()` 後段還已呼叫同一 invocation 的 `recover()` 驗重複恢復仍 terminal。
- `/mnt/c/code/mine/simple_tools/agent-machine/workbench/2026-08-14/p0-function-python/README.md`〈由小到大：一次呼叫〉已寫出「完整 receipt 缺 terminal 時只補 terminal projection」與「dispatch intent 後不自動重跑」，可直接當 p1 兩個 transition 的文字對照。
