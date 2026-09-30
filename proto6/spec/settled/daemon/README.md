# daemon：登記、喚醒與程序生死

← [整理區](../README.md)｜[kernel 樹](../../scheduling/README.md)｜[通用 tick](../tick.md)｜[daemon 協議](../protocol/daemon/README.md)

**daemon 是定期跑 `aos-tick` 的程式。** 它照登記的週期（或被叫醒時）開格，負責它開的程序的啟停與收尾，另開 tick–daemon 通道（B-612～614）。它以資料夾或 inst.json 路徑辨識一個 tick（B-601）。kernel 決定成員何時能做事，daemon 只管開格。

daemon 不是 tick 存在的前提：tick 怎麼被執行不管，cron、人手直接跑也行，只是沒有通道。

依據：[09-29 新架構](../../../notes/2026-09-29-kernel-tree.md)、[使用者裁定](../../../notes/2026-09-29-verdicts.md)、[第十八批](../../../notes/verdicts/09-special-computing-os.md)、[第十九批](../../../notes/verdicts/10-tick-minimal-core.md)、[第二十批](../../../notes/verdicts/11-tick-as-unit.md)。

### 本篇管什麼

- **本篇是 daemon 行為的正本**（[V-01](../../conformance.md)）。[daemon 協議](../protocol/daemon/README.md)（P-100～119）只留設定欄位、method 的 params／result、helper 通道、[runner](../terms.md#t-09收尾排空停機熱重載逃生口) 回報與錯誤碼。
- **daemon 不在任務表上，不是系統級任務。** 開格、格後收尾、重啟清空、排空與立即停機、熱重載、helper 與切換帳號的那一側，都是 daemon 自己的職責（[T-10](../terms.md)）。本篇只寫 daemon 那一側，tick 那一側見 [tick](../tick.md)。
- **daemon 跟 tick 之間只有通道這一條路**，通道是唯一逃生口（[T-07](../terms.md)、B-612）。

依據：第十八批（本篇是正本）；第十九批（daemon 是定期跑 `aos-tick` 的程式）；第二十批（daemon 的職責；取代第十九批「本篇的保證以標準配備全掛為前提」）。

### cgroup 與 git：有就用

**cgroup 與 git 都不是 daemon 跑起來的前提。**

| | 有 | 沒有 |
|---|---|---|
| cgroup | daemon 替每個 node 開框、寫資源上限；runner 那一套照做，格後收尾與收尾最後再用 `cgroup.kill` 兜底，重啟時也清得到舊程序（B-605、B-601、B-603、B-604） | 每一格、每個掛載行程由它自己的 runner 管名下的程序（B-601），收尾經 runner 做（B-604） |
| git | 只有任務表上的 `aos-git` 會用（[B-630](../tick.md)）；daemon 不讀 git | 同左 |

- **runner**＝daemon（或 helper）開每一格、每個掛載行程時用的固定程式 `aos-runner`：照 [inst](../../base/inst.md) 執行一次（就是 proto5 aos-exec 的慣例），並當收屍人管它名下的程序（[T-09](../terms.md)、B-601）。
- 兩種情形並存的做法寫在各條裡；沒有 cgroup 的情形就是原本的做法。

依據：第二十批進行順序（先不含 cgroup 與 git，下一步納入）；納入 cgroup 與 git 的疑點裁定（有就用、沒有就退回）。

### 時間：哪些用毫秒、哪些用格數

〔使用者方向 2026-09-30，astra 審整理區裁定裁-2〕只有外部或作業系統層的時間保留毫秒；aos 自己決定的政策性保留期改用所屬上層的格數。

| 計時 | 單位 | 為什麼 |
|---|---|---|
| 叫醒週期 `interval_ms` | 毫秒 | 外部規定；也是那個 tick「一格」的標準長度（[C-01](../../contracts.md)） |
| 收尾寬限 `shutdown_grace_ms`、排空上限 `drain_timeout_ms` | 毫秒 | 作業系統層的停程序；要跟 systemd 的停機逾時對得上（附錄） |
| 掛載診斷保留期 `mount_diag_ttl_ticks` | 掛它的上層的格數 | 政策性保留期（B-610） |
| pause 存檔間隔 `pause_save_interval_ms`、事項批次寫出（1000 ms） | 毫秒 | daemon 自己的寫檔批次，只決定當機時最多丟多少；daemon 不在任何一格裡，沒有「所屬上層的格」可數 |

依據：第二十批追答 4；astra 審整理區裁定裁-2（撤「daemon 不在格內，所以自己的計時都保留毫秒」）；修正輪暫定的裁定（pause 存檔間隔與事項批次保留毫秒）。


## 分檔目錄

| 檔案 | 條號／內容 |
|---|---|
| [核心：開格與 runner](runtime.md) | B-601、B-504 |
| [核心：重啟、收尾與停機](lifecycle.md) | B-603、B-604、B-611 |
| [核心：登記、叫醒與暫停](registration.md) | B-606、B-607 |
| [核心：通道、掛行程與診斷](channel.md) | B-610、B-612、B-613 |
| [維運：熱重載](reload.md) | B-608 |
| [維運：佈建與 helper 動作](helper-actions.md) | B-609 |
| [cgroup：框、上限與啟動自檢](cgroup.md) | B-605 |
| [訊息：暫存與急件](messaging.md) | B-614 |
| [附錄：systemd service](service.md) | 啟動範例 |
