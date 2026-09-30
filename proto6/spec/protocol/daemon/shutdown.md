# daemon 協議：停機與存檔格式

← [daemon 協議](README.md)｜[共用約定](../README.md)｜行為正本：[daemon](../../daemon.md)、[身分](../../base/identity-resources.md)、[inst](../../base/inst.md)｜[裁定](../../../notes/2026-09-29-verdicts.md)

## P-114．停機：訊號與設定〔使用者方向 2026-09-29，裁定「軟性標準」／CLI H-036 第 1、7 步；第十八批加排空〕

`aos daemon --config F` 收到 SIGINT（Ctrl-C）或 SIGTERM 就停機，停機流程（立即停與排空停）以 [B-604](../../daemon.md) 為正本。

- 走哪一種看設定 `stop_mode`（`"immediate"` 預設／`"drain"`）；排空上限 `drain_timeout_ms`，收尾寬限 `shutdown_grace_ms`，欄位見 [P-101](startup-and-ipc.md)。排空中再收到一次 SIGINT／SIGTERM 改立即停。
- 結束碼：清空、存檔（P-116）、helper 退出、清掉 socket 與 PID 檔之後回 0；清不空或存檔失敗回 125：node 問題寫 node 事項／stdout 警告，自身錯誤寫 daemon 事項／stderr。
- 沒有跨終端的 `aos daemon stop` 或停機 IPC（第十八批 Q14 維持）；只 kill helper 不是停止 daemon。非正常死亡後由下次啟動依 [B-603](../../daemon.md) 檢查舊程序，不因 socket 不見就推論已全空。

**驗收：**有執行中 node 時 Ctrl-C／SIGTERM 都不開新格，等全部受管後代與 helper 全空才回 0；清不空不得回 0。排空的驗收見 B-604。

## P-116．state.json 格式〔使用者方向 2026-09-29〕

`state_dir/state.json` 用 [daemon-state schema](../schemas/daemon-state.schema.json)（持久檔，不認得的欄位忽略，[C-07](../../contracts.md)）：`{version:1,clean_shutdown,registrations:[...]}`。每項存 `node_id`、`parent_id`（根為 null）、`identity_grant`、`once`、`paused`、`pending`，以及有設定的 `interval_ms`／`provision`。不保存 PID、程序、業務結果、`registration_id` 或格次序號（讀回的登記一律換新，見 [B-603](../../daemon.md)）。

`clean_shutdown`：正常停機寫完整狀態時為 true；pause 批次存檔與讀回後改成 false。寫入採 [P-003](../README.md) 的完整暫檔與原子替換。什麼時候寫、讀回怎麼核對、once 與 wake 怎麼接回，以 [B-603](../../daemon.md) 為正本。daemon 自身 attention 依 [P-601](../ops.md) 接回、透過 IPC 查；node 事項留在各自目錄。

範例：[最小](../examples/daemon/state.minimal.valid.json)、[反例：pending 不是布林](../examples/daemon/state.pending.invalid.json)。
