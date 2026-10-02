# daemon 協議：停機與存檔格式

← [舊 daemon 協議（暫緩區）](README.md)｜[共用約定](../../../protocol/README.md)｜行為正本：[舊 daemon](../../daemon/README.md)、[helper](../../helper.md)、[身分](../../../../notes/archive/spec-2026-10-02/base/identity-resources.md)、[inst](../../../inst.md)｜[裁定](../../../../notes/2026-09-29-verdicts.md)

> **這篇整篇在暫緩區**（2026-10-01）：舊協議的停機設定與 `state.json`。現行停機見 [P-120](../../../protocol/daemon/core.md)。原因：daemon 改成只叫 aos-exec、不認得 node；管 node 之後另做成模組（使用者 2026-10-01），最核心 daemon 第一版不做。每條標題下有一行狀態。

## P-114．停機：訊號與設定〔使用者方向 2026-09-29，裁定「軟性標準」／CLI H-036 第 1、7 步；第十八批加排空〕

> **暫緩**（2026-10-01）：`stop_mode`、排空與收尾寬限；最核心 daemon 第一版不做（使用者 2026-10-01）。第一版停機見 [P-120](../../../protocol/daemon/core.md)：SIGINT／SIGTERM 直接退出、回 0。條號保留、不重用。

`aos daemon --config F` 收到 SIGINT（Ctrl-C）或 SIGTERM 就停機。停機流程（立即停與排空停）以 [B-604](../../daemon/lifecycle.md) 為正本。

| 設定 | 作用 |
|---|---|
| `stop_mode` | 走哪一種：`"immediate"`（預設）或 `"drain"` |
| `drain_timeout_ms` | 排空最多等多久 |
| `shutdown_grace_ms` | 收尾寬限 |

欄位定義見 [P-101](startup-and-ipc.md)。排空中再收到一次 SIGINT 或 SIGTERM，改立即停。

| 結束碼 | 意思 |
|---|---|
| `0` | 正常停機 |
| `125` | 清不空或存檔失敗；什麼時候回哪個見 [B-604](../../daemon/lifecycle.md) |

錯誤寫哪裡：node 問題寫 node 事項或 stdout 警告；daemon 自身錯誤寫 daemon 事項或 stderr。

沒有跨終端的 `aos daemon stop`，也沒有停機 IPC（第十八批 Q14 維持）。只 kill helper 不是停止 daemon。

驗收（立即停與排空停）以 [B-604](../../daemon/lifecycle.md) 為正本。

## P-116．state.json 格式〔使用者方向 2026-09-29〕

> **部分已被 [P-123](../../../protocol/daemon/state.md) 取代，其餘暫緩**（2026-10-01；第十一批改）：現行記住狀態模組的狀態檔見 P-123（只記暫停、已停，schema `daemon-module-state`）；本條的 `state.json`（登記、wake、`clean_shutdown`、`cgroup_root_last`）暫緩。條號保留、不重用。

`state_dir/state.json` 用 [daemon-state schema](../../../../notes/archive/spec-2026-10-02/protocol/schemas/daemon-state.schema.json)。持久檔，不認得的欄位忽略（[C-07](../../../../notes/archive/spec-2026-10-02/contracts.md)）。

形狀：`{version:1, clean_shutdown, cgroup_root_last?, registrations:[...]}`。

**`cgroup_root_last`**〔納入 cgroup 與 git 疑-8〕：可省；上次用的 cgroup 子樹根絕對路徑。重啟時用來找舊框、先清空（[B-603](../../daemon/lifecycle.md)）；沒有 cgroup 時不寫。

**`registrations` 每項存**：

| 欄位 | 說明 |
|---|---|
| `node_id` | |
| `parent_id` | 根為 null |
| `identity_grant` | |
| `paused`、`pending` | |
| `interval_ms`、`provision` | 有設定才存 |
| `parent_override:true` | 上層來自登記覆蓋時才存（第十九批） |

**不存**：PID、程序、業務結果、通道的暫存訊息、`registration_id`、格次序號。原本的 `once` 欄拿掉了：掛載行程不存檔；舊檔帶著也照 [C-07](../../../../notes/archive/spec-2026-10-02/contracts.md) 忽略（第十九批）。

**`clean_shutdown`**：正常停機寫完整狀態時為 true；pause 批次存檔與讀回後改成 false。什麼時候寫、怎麼寫、讀回怎麼核對，以 [B-603](../../daemon/lifecycle.md) 為正本。

daemon 自身 attention 依 [P-601](../../../../notes/archive/spec-2026-10-02/protocol/ops.md)。

範例：[最小](../../../../notes/archive/spec-2026-10-02/protocol/examples/daemon/state.minimal.valid.json)、[記了上次的子樹根](../../../../notes/archive/spec-2026-10-02/protocol/examples/daemon/state.cgroup.valid.json)、[反例：pending 不是布林](../../../../notes/archive/spec-2026-10-02/protocol/examples/daemon/state.pending.invalid.json)。
