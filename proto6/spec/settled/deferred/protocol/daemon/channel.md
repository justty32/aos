# daemon 協議：tick–daemon 通道

← [舊 daemon 協議（暫緩區）](README.md)｜[共用約定](../../../../protocol/README.md)｜行為正本：[舊 daemon](../../daemon/README.md)｜[第十九批](../../../../../notes/verdicts/10-tick-minimal-core.md)

> **這篇整篇在暫緩區**（2026-10-01）：舊協議的 tick–daemon 通道。`AOS_DAEMON_SOCKET` 這個名字沿用到 [P-121](../../../protocol/daemon/control.md)。原因：daemon 改成只叫 aos-exec、不認得 node；管 node 之後另做成模組（使用者 2026-10-01），最核心 daemon 第一版不做。每條標題下有一行狀態。

本檔只留通道的環境變數、憑證格式、method 的 params／result 與錯誤碼（第十九批）。行為去這裡找：

| 要找什麼 | 正本 |
|---|---|
| 誰有通道；憑證怎麼發放、核對、作廢 | [B-612](../../daemon/channel.md) |
| 掛行程與砍掉 | [B-613](../../daemon/channel.md) |
| 系統訊息佇列與急件 | [B-614](../../daemon/messaging.md)；tick 那一側 [B-623、B-624](../../../tick/mq.md) |

封包、schema 與通用錯誤同 [P-103](startup-and-ipc.md)、[P-111](provision-and-runner.md)，一律嚴格（[C-07](../../../../contracts.md)）。

## P-117．通道變數與憑證〔使用者方向 2026-09-30，第十九批；名字與格式為建議預設〕

> **部分已被取代、其餘暫緩**（2026-10-01）：`AOS_DAEMON_SOCKET` 這個名字沿用到 [P-121](../../../protocol/daemon/control.md)，意思改成控制 socket，另加 `AOS_DAEMON_INST`；憑證 `AOS_TICK_TOKEN`：現行控制不使用（連得上 socket 就能用，不驗身分）；舊通道憑證暫緩，未來另定，不是永久取消〔astra 報告必修 7〕；其餘（哪些 method 收憑證、`no_channel`、helper 那一段）暫緩，最核心 daemon 第一版不做（使用者 2026-10-01）。條號保留、不重用。

| 環境變數 | 值 |
|---|---|
| `AOS_DAEMON_SOCKET` | daemon 設定的 `socket_path`（絕對路徑） |
| `AOS_TICK_TOKEN` | 本格憑證：32 個小寫 hex（128 位元），schema 見 [daemon-registration](../../../../protocol/schemas/daemon-registration.schema.json) 的 `Token` |

**哪些 method 收 `token`**：

| method | `token` |
|---|---|
| `node.register`、`node.unregister`、`node.wake`、`node.mount`、`node.kill` | 可帶可不帶 |
| `node.send`、`node.take`、`node.provision` 的 `spawn_as`（[P-107](provision-and-runner.md)） | 必帶 |
| 其餘 method，以及 `node.provision` 的其他動作 | 不收；帶了就是 `invalid_params` |

所以客戶端（含 kernel、agent 的工具）只對上表前兩列附憑證；`daemon.info`、`node.show`、其他佈建動作照舊不帶，以 socket 對面的帳號授權（[B-612](../../daemon/channel.md)）。

**缺變數**：客戶端（`aos-mq`、`aos-as`、aos 指令）要走通道卻缺任一個變數時，自己擋下、報代碼 `no_channel`，不連 socket。這個代碼不會出現在 daemon 的回應裡。

**helper 那一段**：私有通道的 `daemon.helper.start` 另帶 `token`，由 helper 放進 runner 的環境（[P-108](provision-and-runner.md)）。

## P-118．掛行程與砍掉〔使用者方向 2026-09-30，第十九批；參數為建議預設〕

> **暫緩**（2026-10-01）：掛行程與砍掉；最核心 daemon 第一版不做（使用者 2026-10-01）。條號保留、不重用。

| method | params | result |
|---|---|---|
| `node.mount` | `node_id` 必填（掛載目標 inst 的絕對路徑，資料夾或單檔）；`parent_id` 可省（資源歸屬的 node）；`token` 可省。不帶 `token` 時 `parent_id` 必填（schema 以 `anyOf` 驗） | `{node_id, registration_id}` |
| `node.kill` | `node_id` 必填；`token` 可省 | `{node_id}` |

- `node.mount` 不收週期、身分額度或佈建權；inst 的 `user` 核對上層的額度（B-613）。
- `node_id` 照給的路徑用，不正規化。

**常見錯誤**：

| 情況 | code |
|---|---|
| 上層或目標不存在；`node.kill` 的目標已結束 | `not_registered` |
| 同一個 id 還在跑，或已是登記 | `registration_conflict` |
| 對登記的 node 送 `node.kill` | `kind_mismatch` |
| inst 的 user 超出上層額度／不存在 | `user_not_granted`／`user_invalid` |
| 排空或停機中 | `stopping` |
| 收尾確認不了全空 | `cleanup_failed` |

範例：[掛行程](../../../../protocol/examples/daemon/mount.minimal.valid.json)、[回應](../../../../protocol/examples/daemon/mount_result.minimal.valid.json)、[反例：帶週期](../../../../protocol/examples/daemon/mount.interval.invalid.json)、[反例：沒憑證也沒上層](../../../../protocol/examples/daemon/mount.no-token-no-parent.invalid.json)、[砍掉](../../../../protocol/examples/daemon/kill.minimal.valid.json)、[反例：多一個欄位](../../../../protocol/examples/daemon/kill.extra.invalid.json)。

## P-119．送訊息、取訊息與通道錯誤碼〔使用者方向 2026-09-30，第十九批；參數與上限為建議預設〕

> **暫緩**（2026-10-01）：送訊息、取訊息；最核心 daemon 第一版不做（使用者 2026-10-01），訊息之後另做成模組，不走控制 socket。條號保留、不重用。

| method | params | result |
|---|---|---|
| `node.send` | `token`、`to`（收件 tick 的 node id）、`message` 必填；`urgent` 可省，布林，預設 false | `{node_id}`（收件 tick 的 id） |
| `node.take` | `token` 必填；`limit` 可省，1～256，預設 256 | `{messages, more}` |

**`message`**：一份請求或回應物件（common 的 `FileRpcRequest` 或 `FileRpcResponse`，[P-301](../../../../protocol/messages.md)；回應也走佇列〔使用者方向 2026-09-30，修正輪暫定的裁定〕）。`node.take` 回的 `messages` 也是兩種都有。它照檔案 RPC 放寬、不認得的欄位忽略；外層 params 仍嚴格（[C-07](../../../../contracts.md)）。序列化後最多 196608 bytes。

**`node.take` 的回應**：

- `messages` 照送到的先後排；一次最多 `limit` 件，整個回應不超過 256 KiB；有訊息就至少給一件。
- `more:true`＝還有沒取完的。

〔建議預設，未拍板〕訊息部件關閉時，登記 node 的合法 `node.take` 回應格式為 `{"messages":[],"more":false}`（[B-614](../../daemon/messaging.md)）。

**上限**：每個收件 tick 最多 256 件、合計 16 MiB（照 `message` 序列化後的 bytes 算）。寫死，不開放設定（[B-608](../../daemon/reload.md)）。

範例：[送急件](../../../../protocol/examples/daemon/send.minimal.valid.json)、[送回應](../../../../protocol/examples/daemon/send.response.valid.json)、[反例：沒帶憑證](../../../../protocol/examples/daemon/send.no-token.invalid.json)、[取](../../../../protocol/examples/daemon/take.minimal.valid.json)、[回應](../../../../protocol/examples/daemon/take_result.minimal.valid.json)、[反例：憑證格式不對](../../../../protocol/examples/daemon/take.bad-token.invalid.json)、[憑證不認得](../../../../protocol/examples/daemon/error.token_invalid.valid.json)。

### 通道的業務錯誤碼

-32000，放在 `data.code`；其餘沿用 [P-111](provision-and-runner.md)。

| code | 意思 | 預設 retryable |
|---|---|---|
| `not_available`〔建議預設，未拍板〕 | daemon 訊息部件關閉時的 `node.send`（[B-614](../../daemon/messaging.md)）；B-609 關閉動作同 P-111 | false |
| `token_invalid` | 憑證不認得、已作廢、跟 node 對不上，或 socket 對面的帳號不合 | false |
| `kind_mismatch` | 目標種類不符：對掛載行程送 unregister／wake／pause／resume；對登記的 node 送 kill；send 的收件方是掛載行程；take 的呼叫者是掛載行程 | false |
| `mailbox_full` | 收件 tick 的佇列已達上限 | true，稍後再送 |
| `message_too_large` | 單件訊息超過上限 | false |

通道上沿用 P-111 的：

| 情況 | code |
|---|---|
| 寄件帳號對收件 tick 的 `.aos/mq/get/` 沒寫權（[B-614](../../daemon/messaging.md)）；用憑證的 tick 不在目標的上層鏈上 | `forbidden` |
| 收件 tick 不在這個 daemon | `not_registered` |
| 停機中 | `stopping` |
| 活程序或維護狀態不合 | `busy` |
