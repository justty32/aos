# daemon 協議：tick–daemon 通道

← [舊 daemon 協議（暫緩區）](README.md)｜[共用約定](../../../protocol/README.md)｜行為正本：[舊 daemon](../../daemon/README.md)｜[第十九批](../../../../notes/verdicts/10-tick-minimal-core.md)

> **這篇整篇在暫緩區**（2026-10-01）：舊協議的 tick–daemon 通道。`AOS_DAEMON_SOCKET` 這個名字沿用到 [P-121](../../../protocol/daemon/control.md)。原因：daemon 改成只叫 aos-exec、不認得 node；管 node 之後另做成模組（使用者 2026-10-01），最核心 daemon 第一版不做。每條標題下有一行狀態。

本檔只留通道的環境變數、憑證格式、method 的 params／result 與錯誤碼（第十九批）。行為去這裡找：

| 要找什麼 | 正本 |
|---|---|
| 誰有通道；憑證怎麼發放、核對、作廢 | [B-612](../../daemon/channel.md) |
| 掛行程與砍掉 | [B-613](../../daemon/channel.md) |
| 系統訊息佇列與急件 | [B-614](../../daemon/messaging.md)；tick 那一側 [B-623、B-624](../../mq.md) |

封包、schema 與通用錯誤同 [P-103](startup-and-ipc.md)、[P-111](provision-and-runner.md)，一律嚴格（[C-07](../../../../notes/archive/spec-2026-10-02/contracts.md)）。

## 分檔目錄

> 本檔只留前言與目錄，內容按標題拆在 `channel/`。

<!-- wf-nav -->
| # | 檔 | 段落 |
|---|---|---|
| 1 | [01-P-117-P-118-變數與掛行程.md](channel/01-P-117-P-118-變數與掛行程.md) | P-117．通道變數與憑證〔使用者方向 2026-09-30，第十九批；名字與格式為建議預設〕；P-118．掛行程與砍掉〔使用者方向 2026-09-30，第十九批；參數為建議預設〕 |
| 2 | [02-P-119-送取訊息與錯誤碼.md](channel/02-P-119-送取訊息與錯誤碼.md) | P-119．送訊息、取訊息與通道錯誤碼〔使用者方向 2026-09-30，第十九批；參數與上限為建議預設〕 |
