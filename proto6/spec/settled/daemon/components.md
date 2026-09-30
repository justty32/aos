# daemon 部件與核心開關

← [daemon 目錄](README.md)｜[設定格式](../protocol/daemon/startup-and-ipc.md)

## B-615：部件形式與開關

〔使用者方向 2026-09-30 晚〕**同一支程式，用設定檔開關。** 不拆成獨立程式，不另開部件介面。保證跟著掛了什麼走：

- **A 組核心**：登記、定時開格、叫醒／暫停、收尾、重啟、通道憑證；runner 開程序、清自己名下程序與收屍都留核心（B-601、B-603、B-604、B-606、B-607、B-612）。掛行程的 runner 路線與診斷照舊（B-613、B-610）。
- **B 組訊息部件**：同一 daemon 內 node 之間的訊息與急件（[B-614](messaging.md)）。
- **C 組 cgroup 部件**：node 框與上限、格後／重啟／收尾的清框、cgroup 子樹鎖、掛行程的框、helper 的 cgroup 動作（[B-605 及各條 cgroup 部分](cgroup.md)）。
- **D 組留核心、各自可關**：熱重載（[B-608](reload.md)）、排空停機（[B-604](lifecycle.md)）、helper 動作（[B-609](helper-actions.md)）。

### 開關總表

〔建議預設，未拍板〕下列名稱、預設值、套用時機與關閉行為都是建議；「可以關」已裁定，這些細節尚未拍板。五個開關都是 daemon 設定檔頂層的可省布林值，**省略為 true**，保留既有啟用行為；型別不合照設定錯處理。

| 設定開關 | false 時 | 行為正本 |
|---|---|---|
| `enable_messaging` | 不提供訊息佇列；合法 send 回 `not_available`，合法 take 回空；不產生急件 wake，任務表照用 | [B-614](messaging.md)；客戶端 [B-623、B-624](../tick.md) |
| `enable_cgroup` | 等於沒有 cgroup，走現成 `cgroup=off` 路線；runner 照做 | [B-605](cgroup.md) |
| `enable_reload` | SIGHUP 只警告、不重讀、不退出 | [B-608](reload.md) |
| `enable_drain` | `stop_mode` 即使為 drain 也採立即停，照常收尾與存檔 | [B-604](lifecycle.md) |
| `enable_helper_actions` | 非 cgroup 的對外佈建與 `spawn_as` 回 `not_available`；保留核心 helper 開格／收尾，cgroup 動作由其部件開關決定 | [B-609](helper-actions.md) |

〔建議預設，未拍板〕**五個開關一律重開才生效**，不在運行中掛上或卸下部件。熱重載開著時，改開關照 B-608 的 `restart_required` 處理；熱重載關著時，照該條不重讀。啟用只代表允許使用，仍須通過原有授權與環境條件：cgroup 開著但環境不可用仍是 off，helper 動作開著但 helper 不在仍回 `helper_unavailable`，都不繞過原規則。

依據：[09-30 晚裁定](../../../notes/2026-09-30-daemon-split-and-multi-daemon.md)（A／B／C／D 分工、同程式設定開關）；沒掛時的行為與開關細節為〔建議預設，未拍板〕。

**驗收：**只用同一支 `aos daemon` 及設定檔切換；兩個部件與三個核心功能都關掉時，通用 user 的 node 仍能登記、開格、叫醒／暫停、runner 收尾、重啟與核對通道憑證。〔建議預設，未拍板〕省略五鍵時沿用原行為；每鍵單獨關閉及全部關閉各驗一次，結果見表中正本。部件都關時仍可 mount／kill；同一張任務表不需改，mq-post 回 1 不會讓 daemon 停格。改開關只在重開後生效。

### 這輪待拍板

- 五個開關的名稱、省略為 true、全部要重開。
- cgroup 關閉時沿用 off，設定仍驗格式但不動新舊框；訊息關閉時 send／post 報錯、take／get 回空，以及 `not_available` 不自動重試、沿用失敗紀錄。
- 關熱重載只警告、關排空改立即停；helper 開關只關對外非 cgroup 動作，保留核心內部路徑的界線。

這些只待裁定，不阻擋本輪規格拆檔。既有暫定事項仍見[整理區疑點](../README.md#疑點)，本輪不重裁。
