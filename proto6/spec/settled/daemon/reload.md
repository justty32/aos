# daemon 維運：熱重載

← [daemon 目錄](README.md)｜[整理區](../README.md)

## B-608：熱重載與「免重開／要重開」

**改設定、改樹不必重開 daemon**：除了重大或危險的操作要重開，其餘都盡量免重開（第十八批）。原本叫「即時改」，第二十批改叫「免重開」，免得跟「反應速度就是一格」（[T-07](../terms.md)）的「立刻處理」混；行為不變。

### 熱重載怎麼做

daemon 只在收到 **SIGHUP** 時重讀啟動時的同一份設定檔。能送訊號的只有同帳號或 root；不開 IPC、沒有 CLI 子命令（人手用 `kill -HUP`）。

1. 讀新設定並驗證整份；
2. 跟目前設定比對差異；
3. 依下表套用免重開的，其餘不套用。

| 情況 | 怎麼辦 |
|---|---|
| 新設定讀不進來或不合 schema | 整份不套用，舊設定繼續用；stderr 說明並寫 daemon 事項（`config_invalid`） |
| 有「要重開」的欄位改了 | 免重開的照套，這些欄位不套用；stdout 列出並寫 daemon 事項（`restart_required`），直到重開或改回為止 |
| 不認得的欄位 | 照 [C-07](../../contracts.md) 忽略並印出名字 |
| 停機或排空中收到 SIGHUP | 不重載，印一行警告 |

每次重載在 stdout 印一行，列出已套用與要重開的欄位。

**helper 的界線**（第十八批）：helper 在 fork 前固定一份設定副本，用它核對頂層額度（B-601）；重載不改 helper 那份。所以牽涉 helper 的欄位——**通用 user 以外帳號的身分額度、佈建權**——改了仍要重開。要少重開，就在啟動設定用前綴或範圍一次授出夠大的範圍（B-606）。

### 設定項

| 設定 | 改了怎麼辦 | 說明 |
|---|---|---|
| `version` | 重載時照樣檢查 | 版本不同整份不收（`config_invalid`） |
| `common_user` | **要重開** | daemon 已永久變成這個帳號，換帳號等於換一個 daemon |
| `socket_path` | **要重開** | 連線全斷、各 kernel 記的位置與已開 tick 的通道變數都會失效；防雙開的鎖在 socket 目錄 |
| `state_dir` | **要重開** | 恢復資料在舊位置，也是排他鎖的對象（B-611） |
| `cgroup_root` | **要重開** | 程序要跨子樹搬家，需要 root；也是排他鎖的對象（B-605、B-611） |
| `create_cgroup` | 改了沒效果 | 只在啟動時有用 |
| `pause_save_interval_ms` | 免重開 | 下一次存檔用新值 |
| `shutdown_grace_ms` | 免重開 | 只影響之後才開始的收尾 |
| `stop_mode`、`drain_timeout_ms` | 免重開 | 下一次停機用新值 |
| `kill_escape_cgroups` | 免重開 | 之後才開始的重啟清空與解除登記用新值（B-605） |
| `mount_diag_max`、`mount_diag_ttl_ticks` | 免重開 | 下一輪淘汰用新值（B-610） |
| `disable` | 免重開 | 只影響之後的 quota 動作，已設好的歸屬不收回；重新打開時再偵測一次 |
| roots：加一棵 | 免重開；額度含通用 user 以外帳號或帶 `provision` 的**要重開** | 等於一次沒有上層的登記加一次 wake |
| roots：刪一棵 | 免重開 | 走 B-606 的解除；清不空就一直擋著並寫事項 |
| roots：`node_id` 改名 | 當成刪一棵加一棵 | 舊的那棵要收尾 |
| roots：`interval_ms` | 免重開 | 從下一次到期開始算 |
| roots：`identity_grant` | 只動通用 user 的免重開；動到其他帳號（含前綴、範圍）的**要重開** | 重開後依 B-603 重核讀回的登記；超出的子孫照 B-607 停格 |
| roots：`provision` | **要重開** | helper 核對的是啟動時那份 |
| 有沒有 helper（用不用 sudo 開） | **要重開** | 拉起 helper 需要 root |
| 啟動旗標 `--firstdo-fsync`、`--create-cgroup` | **要重開** | 旗標只在啟動時讀（[B-633](../tick.md)、B-605） |

寫死、不開放成設定的：IPC 封包上限 256 KiB、`node.ls` 每頁 64 筆、socket 權限預設值、最低版本、通道的暫存上限與單件上限（B-614）。版本檢查只在啟動時做。

### 操作

| 操作 | 免重開／要重開 | 說明 |
|---|---|---|
| 啟動 `aos daemon` | — | 啟動自檢、取鎖、清空舊程序都只在這時做 |
| 立即停、排空停 | — | B-604 |
| 熱重載（SIGHUP） | — | 本條 |
| `daemon.info` | 免重開 | 查本次啟動 ID |
| `node.register`：新登記、重送、更新、覆蓋上層、換父 | 免重開 | B-606；換父只要求被搬的那棵先停 |
| `node.unregister` | 免重開 | B-606 |
| `node.wake`、`node.pause`、`node.resume` | 免重開 | B-607 |
| `node.mount`、`node.kill` | 免重開 | B-613 |
| `node.send`、`node.take` | 免重開 | B-614 |
| `node.show`、`node.ls` | 免重開 | 最近一格含格次序號 |
| `mount.clear` | 免重開 | B-610 |
| `node.provision`（含 helper 新動作、改 cgroup 上限） | 免重開 | B-609 |
| `daemon.attention.*` | 免重開 | [P-601](../../protocol/ops.md) |
| helper 被 kill 之後恢復特權操作 | **要重開** | 需要 root 才拉得起來（[B-303](../helper.md)） |

要重開的共同原因：一改就等於換了 daemon 的身分、恢復資料、整棵資源樹，或 helper 的授權依據，而且大多要 root 才做得到。其餘最多只要求被動到的那一棵先停下，不影響別的樹。

**驗收：**SIGHUP 後改 `interval_ms`、加一棵只用通用 user 的 root 免重開就生效；改 `socket_path` 或 root 的其他帳號額度時其餘照套、這些欄位回報要重開且不生效；壞設定整份不套用、舊設定照跑；非同帳號送不了 SIGHUP。

