完成，僅修改指定四檔：

- `aos_kernel.py`：新增 `done_exit`、`KHome.proc_done()`，`ls` 顯示設定與完成清單。
- `aos_kernel_init.py`：新增 `--done-exit`，建立 `procs/done/`。
- `aos_kernel_tick.py`：新增 `_finish()`，完成判斷置於 quantum 換人前，失敗時保留原 cpu。
- `test_kernel.py`：新增 3 條測試；初始化測試補驗 `done/` 與設定。
- 完整測試 188 條；最後一行原文：`OK`
- CMake/CTest：`100% tests passed out of 8`
- `done:` 只列 `.json` 普通檔，並依 `pid_key` 排序。
- 模組式測試因既有 `_util` 路徑失敗，改用 discover 成功執行。
- 沒做到的：無。未碰文件、未 commit、未 push；既有 `proto4-4/` 改動未碰。