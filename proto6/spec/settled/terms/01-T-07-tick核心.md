← [整理區名詞：tick 核心、四類程式與 daemon 核心](../terms.md)（分檔 1/3）｜[下一份](02-T-10-四類程式.md)

## T-07．tick 核心

**tick 是一個定期被執行的程式**（`aos-tick`）。誰來跑都行：daemon、cron、人手；人手或 cron 直接跑的風險自己承擔。它本質上是加了一些功能的 aos-exec（跑一份 [inst](../../base/inst.md)）。

| 詞 | 一句話 | 正本 |
|---|---|---|
| tick 核心 | 只做三件事：簡單互斥鎖、照表跑、每項結束碼紀錄；照表跑時另外只認 tasks-blocked 與擋板檔（只看存不存在；tasks-blocked 另讀 `kinds` 一個鍵，第二十四批）；任務沒有 `user`（寫了照陌生鍵）。不靠 daemon、git、cgroup、helper，也不靠任何系統級任務。上下層判定已搬暫緩區（[B-628](../deferred/tick/01-B-628上下層與B-602-B-620細節.md#b-628上下層判定預設看資料夾包含可登記覆蓋)） | [B-626](../tick.md)、[B-620](../tick.md) |
| 工作資料夾 | 這一格 `aos-tick` 跑的資料夾（它的 cwd），由命令列的目標決定（`aos-tick [<目標>]`）；任務拿到的 `AOS_TICK_CWD` 就是它的絕對路徑。tick 這層只講工作資料夾（英文 `tick dir`〔使用者 2026-10-01〕）；node 是之後 node 模組才出場的詞 | [B-620](../tick.md)、[P-203](../protocol/tick.md) |
| 拆出去的 | 原本算在 tick 裡的其餘事，成了系統級任務或普通程式（T-10）；舊設計裡一格結束後殺殘留歸 daemon，那套在暫緩區、現行 daemon 不做〔astra 報告必修 1〕 | [B-626](../tick.md)、[B-601](../deferred/daemon/runtime.md) |
| 衡量基準 | 整個 aos 以格計：「花十格」算安排它的上層的格；排程本身也是任務表上每格跑一次的程式；反應速度就是一格，只有通道急件例外 | [C-01](../../contracts.md)、[B-614](../deferred/daemon/messaging.md) |
| 唯一逃生口 | tick–daemon 通道；通道外的事都要在某一格裡做，不准有背景程序或常駐服務繞過 tick。通道是舊 daemon 的設計，在暫緩區 | [B-612](../deferred/daemon/channel.md) |
| tick 外的寫入者 | CLI 或工具在 tick 之外自己取鎖改檔，當外部世界，aos 不管 | [B-602](../tick.md) |

tick 不跟其他計算單位（once、LLM 嘗試、agent 一輪等）放進同一個外殼；那些的外殼、逾時與取消延後（P-008）。

依據：第十八批（外殼）；第十九批（定期被執行的程式）；第二十批（衡量基準、系統級任務與普通程式）、疑點裁定 1（停格靠檔案）、8（tick 外的寫入者）；使用者 2026-10-01（核心縮成三件事、不判上下層、撤回 `user`、工作資料夾）。
