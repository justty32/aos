# daemon 附錄：systemd service

← [舊 daemon 目錄（暫緩區）](README.md)｜[整理區](../../README.md)

> **這篇整篇在暫緩區**（2026-10-01）：舊 daemon 的 systemd 範例，寫的是舊設定檔與舊停機流程。現行怎麼用 systemd 見 [daemon 目錄](../../daemon/README.md)最後一段。原因：daemon 改成只叫 aos-exec、不認得 node；管 node 之後另做成模組（使用者 2026-10-01），最核心 daemon 第一版不做。每條標題下有一行狀態。

## 附錄：開機自動啟動的 systemd service 範例

> **暫緩**（2026-10-01）：寫的是舊設定檔、`Delegate=yes` 與舊停機流程；最核心 daemon 第一版不做（使用者 2026-10-01）。條號保留、不重用。

〔使用者方向 2026-09-29 晚〕要開機自動啟動，就把 daemon 寫成一個 systemd service；這只是範例，不算執行期依賴。兩種都寫 `Delegate=yes`，讓 systemd 把 daemon 所在的 cgroup 委派給它，daemon 才認得到有 cgroup（B-605）；拿掉就是 `cgroup=off`。

### 使用者層（不用 sudo，單帳號）

〔納入 cgroup 與 git 改寫計畫〕單位名固定，框路徑也固定；重啟時 systemd 會先殺舊程序。要先對這個帳號 `loginctl enable-linger <帳號>`，登出後才不會被停。

```ini
# ~/.config/systemd/user/aos-daemon.service（範例）
[Unit]
Description=aos daemon (user)

[Service]
ExecStart=/usr/local/bin/aos daemon --config %h/.config/aos/daemon.json
ExecReload=/bin/kill -HUP $MAINPID
# 委派 cgroup 子樹給 daemon（B-605）
Delegate=yes
KillMode=mixed
TimeoutStopSec=15min

[Install]
WantedBy=default.target
```

### 系統層（sudo 模式，有 helper）

```ini
# /etc/systemd/system/aos-daemon.service（範例）
[Unit]
Description=aos daemon
After=local-fs.target

[Service]
# 以 root 開＝sudo 模式（有 helper）。服務啟動沒有 SUDO_UID，所以設定檔一定要寫 common_user（B-303）
# 要單帳號模式（沒 helper）就加 User=<帳號>，common_user 可省
ExecStart=/usr/local/bin/aos daemon --config /etc/aos/daemon.json
# 熱重載（B-608）
ExecReload=/bin/kill -HUP $MAINPID
# 讓 systemd 把 daemon 所在的 cgroup 劃給它，當成準備好的子樹（B-605）
Delegate=yes
# 停服務時先只對 daemon 送 SIGTERM，讓它自己收尾在途程序（B-604）
KillMode=mixed
# 設定用 stop_mode:"drain" 時，這個值要大於 drain_timeout_ms 加 shutdown_grace_ms，否則 systemd 會先強殺
TimeoutStopSec=15min

[Install]
WantedBy=multi-user.target
```
