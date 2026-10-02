# daemon 控制模組

← [daemon 目錄](README.md)｜[核心 B-640](core.md)｜格式：[P-121](../protocol/daemon/control.md)

程式：`lib/aos_daemon_ctl.py`、`lib/aos_ctl.py`；測試：`tests/test_ctl_protocol.py`、`test_ctl_loop.py`、`test_daemon_kill.py`。

## B-641：控制模組與 aos-ctl

做什麼：設定檔寫了 `modules.control.socket` 才開一個 socket，讓人或任務對清單上的**某一項**下 `wake`、`pause`、`resume`、`status`、`kill`、`restart`（`aos-ctl` 是送指令的小工具）。沒有「對全部」，也不收 reload、shutdown。

原則：

- **能連就能做，不驗身分**；socket 666、誰能連靠所在資料夾權限（見 [README](README.md)）。
- 每次開 `aos-exec` 放環境變數 `AOS_DAEMON_CTL_SOCKET`、`AOS_DAEMON_INST`；它們一路被各層任務繼承，所以任何一層跑 `aos-ctl wake` 叫醒的都是 daemon 清單上最頂層那一項。
- 暫停中 `wake` 跑一次、跑完照樣暫停；被 `stop_on_nonzero` 停掉的項 `wake` 回 `stopped`，要 `resume`；`resume` 一律馬上跑一次。`wake` 連叫只補一次。
- `kill`／`restart` 是為了 daemon 跑 daemon（下層永遠不結束）：先 SIGTERM，等 `kill_grace_ms` 還沒結束才 SIGKILL（掛了收屍模組就整框殺）。
- 暫停、已停只放記憶體；要跨重開掛記住狀態模組（B-643）。
- 一條連線出錯只影響那一條。
