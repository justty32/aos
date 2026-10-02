# daemon 帳號模組

← [daemon 目錄](README.md)｜[核心 B-640](core.md)｜格式：[P-126](../protocol/daemon/account.md)｜舊設計：[暫緩區 B-303](../deferred/helper.md)

程式：`lib/aos_daemon_account.py`、`lib/aos_daemon_root.py`；測試：`tests/test_account_policy.py`、`test_account_ns.py`。

## B-646：帳號模組

做什麼：設定檔寫了 `modules.account`，某一項指定用哪個帳號，daemon 就用那個帳號開它的 `aos-exec`。要用 root 開 daemon，沒用 root 回 1。

原則：

- **切帳號只在 daemon 設定檔做**：單位是 daemon 的一項，tick 不切帳號，也不在一格中途換。
- 兩支程序：root 端（`aos-daemon-root`）一直是 root、只做「用某帳號開一個程序」，不讀設定檔；主程式開起來就永久降成預設帳號（`modules.account.user`，沒寫用 `SUDO_USER`），其他事都它做，所以 socket、狀態檔、輸出檔都歸預設帳號。**主程式被攻破最多只能用名單准的帳號開程序，拿不到 root。**
- 名單：`allow`／`deny`，字串可用結尾 `*` 當前綴；先黑名單、再白名單、都沒比到不准；root 一律不准；`deny` 比得到預設帳號算設定錯。每項帳號開起來就核，之後 root 端開之前再核一次。
- root 端被殺 → 整個 daemon 回 1；主程式退出 → root 端自己退出，都不殺子程序。
