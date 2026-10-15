← [code map 總圖](../code-map.md)｜[各分冊導覽](README.md)

## proto8／proto8-1 逐檔總覽

（10-13 從 code-map.md 原文搬來；新增或刪檔時這裡與該 README 一起改。）

`proto8/`（Python）的逐檔表在 [proto8/lib/README.md](../../../../proto8/lib/README.md)（指示詞 `aos_directives.py`、命令列與 stdio 範本 `aos_cli.py`、inst `aos_inst.py`、loop `aos_loop.py`＋共用的 ctl／state `aos_ctl_state.py` 與行程群組 `aos_proc.py`、daemon `aos_daemon.py`（重用 loop 的拍引擎）＋表與策略格 `aos_daemon_table.py`＋指令與控制資料夾 `aos_daemon_folder.py`、fsm `aos_fsm.py`＋方法表 `aos_methods.py`、agent 的現成格庫 `aos_agent_lib.py`（think／tool 兩格，設定從 stdin 的 `cfg` 拿）＋真的腦 `aos_brain_openai.py`，測試在 `tests/` 按程式分檔；各程式的細節在同資料夾的 `directives.md`、`inst.md`、`loop.md`、`daemon.md`、`fsm.md`、`agent.md`、`ctl-state.md`），demo 在 [proto8/demo/README.md](../../../../proto8/demo/README.md)（daemon；fsm／agent 的在 `demo/fsm/`：假腦 `brain/fake.py`、工具 `tools/clock.*`）；改 proto8 的檔就同步那份。`proto8-1/`（tasks：`aos_seq.py`、`aos_par.py`、`aos_if.py`、`aos_not.py`、時鐘 `aos_tick.py`、共用 `aos_tasks.py`（stderr 的錯誤重用 proto8 的 `aos_cli.error()`）、`bin/` 薄入口、測試 `tests/`）的逐檔表在 [proto8-1/README.md](../../../../proto8-1/README.md)，demo（daemon 跑 tasks 樹＋寫起來的發現）在 [proto8-1/demo/README.md](../../../../proto8-1/demo/README.md)。
