# daemon 協議：停機與存檔格式

← [daemon 協議](README.md)｜[共用約定](../README.md)｜行為正本：[daemon](../../daemon.md)、[身分](../../base/identity-resources.md)、[inst](../../base/inst.md)｜[裁定](../../../notes/2026-09-29-verdicts.md)

## P-114．停機：訊號與設定〔使用者方向 2026-09-29，裁定「軟性標準」／CLI H-036 第 1、7 步；第十八批加排空〕

`aos daemon --config F` 收到 SIGINT（Ctrl-C）或 SIGTERM 就停機，停機流程（立即停與排空停）以 [B-604](../../daemon.md) 為正本。

- 走哪一種看設定 `stop_mode`（`"immediate"` 預設／`"drain"`）；排空上限 `drain_timeout_ms`，收尾寬限 `shutdown_grace_ms`，欄位見 [P-101](startup-and-ipc.md)。排空中再收到一次 SIGINT／SIGTERM 改立即停。
- 結束碼：正常停機 0；清不空或存檔失敗 125（什麼時候回哪個見 [B-604](../../daemon.md)）：node 問題寫 node 事項／stdout 警告，自身錯誤寫 daemon 事項／stderr。
- 沒有跨終端的 `aos daemon stop` 或停機 IPC（第十八批 Q14 維持）；只 kill helper 不是停止 daemon。

驗收（立即停與排空停）以 [B-604](../../daemon.md) 為正本。

## P-116．state.json 格式〔使用者方向 2026-09-29〕

`state_dir/state.json` 用 [daemon-state schema](../schemas/daemon-state.schema.json)（持久檔，不認得的欄位忽略，[C-07](../../contracts.md)）：`{version:1,clean_shutdown,registrations:[...]}`。每項存 `node_id`、`parent_id`（根為 null）、`identity_grant`、`paused`、`pending`，以及有設定的 `interval_ms`／`provision`；〔使用者方向 2026-09-30，第十九批〕上層來自登記覆蓋的另存 `parent_override:true`。原本的 `once` 欄拿掉：掛載行程不存檔；舊檔帶著也照 [C-07](../../contracts.md) 忽略。不保存 PID、程序、業務結果、通道的暫存訊息、`registration_id` 或格次序號。

`clean_shutdown`：正常停機寫完整狀態時為 true；pause 批次存檔與讀回後改成 false。什麼時候寫、怎麼寫、讀回怎麼核對，以 [B-603](../../daemon.md) 為正本。daemon 自身 attention 依 [P-601](../ops.md)。

範例：[最小](../examples/daemon/state.minimal.valid.json)、[反例：pending 不是布林](../examples/daemon/state.pending.invalid.json)。
