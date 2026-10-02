# daemon 核心

← [daemon 目錄](README.md)｜[規格](../README.md)｜格式：[P-120](../protocol/daemon/core.md)

程式：`lib/aos_daemon.py`、`aos_daemon_config.py`、`aos_daemon_run.py`、`aos_daemon_output.py`；測試：`tests/test_daemon_config.py`、`test_daemon_run.py`、`test_daemon_kill.py`。

## B-640：最核心 daemon：定期叫 aos-exec

做什麼：讀設定檔，`insts` 的每一項（鍵就是 inst 字面值，原樣交給 `aos-exec`，daemon 不解析）照自己的 `interval_ms` 叫 `aos-exec`，結束後印一行；週期從上一次**結束**起算、不補跑；`stop_on_nonzero` 時非 0 就停那一項。

原則：

- 核心沒有 id、不認得工作資料夾、不讀任務表。一項就是它的 inst 字面值。
- 整份設定檔先展開指示詞再讀（跟 tasks.json 只展到 `tasks` 那層不同，對照見 [C-11](../conventions.md)）；`$ref` 以設定檔所在資料夾為準。
- 頂層 `cwd` 只是 `aos-exec` 子程序的工作目錄與相對路徑的起點，daemon 自己不 chdir。
- `aos-exec` 的 stdout／stderr 沒寫 `exec_out_path`／`exec_err_path` 就丟掉；收的時候有共用上限 `exec_output_max_bytes`，超過丟最早的（為了 daemon 跑 daemon：下層永遠不結束）。
- 停機：SIGINT／SIGTERM 直接退出、回 0，不殺也不等正在跑的 `aos-exec`。
- 拿不到鎖檔（另一個 daemon 在用這份設定）＝stderr 一行、回 1，什麼都不開。
- `modules` 核心只認得位置、不解讀；沒掛任何模組時不開 socket、不多傳環境變數、SIGHUP 照 Python 預設。
