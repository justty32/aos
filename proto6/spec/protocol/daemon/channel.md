# daemon 協議：tick–daemon 通道

← [daemon 協議](README.md)｜[共用約定](../README.md)｜行為正本：[daemon](../../daemon.md)｜[第十九批](../../../notes/verdicts/10-tick-minimal-core.md)

〔使用者方向 2026-09-30，第十九批〕本檔只留通道的環境變數、憑證格式、method 的 params／result 與錯誤碼。誰有通道、憑證怎麼發放／核對／作廢見 [B-612](../../daemon.md)，掛行程與砍掉見 [B-613](../../daemon.md)，暫存訊息與急件見 [B-614](../../daemon.md)。封包、schema 與通用錯誤同 [P-103](startup-and-ipc.md)、[P-111](provision-and-runner.md)，嚴格（[C-07](../../contracts.md)）。

## P-117．通道變數與憑證〔使用者方向 2026-09-30，第十九批；名字與格式為建議預設〕

| 環境變數 | 值 |
|---|---|
| `AOS_DAEMON_SOCKET` | daemon 設定的 `socket_path`（絕對路徑） |
| `AOS_TICK_TOKEN` | 本格憑證：32 個小寫 hex（128 位元），schema 見 [daemon-registration](../schemas/daemon-registration.schema.json) 的 `Token` |

- 收憑證的 method：`node.register`、`node.unregister`、`node.wake`、`node.mount`、`node.kill` 的 params 可多帶 `token`；`node.send`、`node.take` 與 `node.provision` 的 `spawn_as`（[P-107](provision-and-runner.md)）必帶。其餘 method 與 `node.provision` 的其他動作不收 `token`，帶了就是 `invalid_params`；所以客戶端（含 kernel、agent 的工具）只對上面這幾個附憑證，`daemon.info`、`node.show`、其他佈建動作照舊不帶，以 socket 對面的帳號授權（[B-612](../../daemon.md)）。
- 客戶端（標準配備的傳訊任務、aos 指令）要走通道卻缺任一個變數時，自己擋下、報代碼 `no_channel`，不連 socket；這個代碼不會出現在 daemon 的回應裡。
- helper 私有通道的 `daemon.helper.start` 另帶 `token`，由 helper 放進 runner 的環境（[P-108](provision-and-runner.md)）。

## P-118．掛行程與砍掉〔使用者方向 2026-09-30，第十九批；參數為建議預設〕

| method | params | result |
|---|---|---|
| `node.mount` | `node_id` 必填（掛載目標 inst 的絕對路徑，資料夾或單檔）；`parent_id` 可省（資源歸屬的 node）；`token` 可省。不帶 `token` 時 `parent_id` 必填（schema 以 `anyOf` 驗） | `{node_id, registration_id}` |
| `node.kill` | `node_id` 必填；`token` 可省 | `{node_id}` |

- `node.mount` 不收週期、身分額度或佈建權；inst 的 `user` 核對上層的額度（B-613）。`node_id` 照給的路徑，不正規化。
- 常見錯誤：上層或目標不存在、`node.kill` 的目標已結束 `not_registered`；同一個 id 還在跑或已是登記 `registration_conflict`；對登記的 node 送 `node.kill` `kind_mismatch`；inst user 超出上層額度 `user_not_granted`、不存在 `user_invalid`；排空或停機中 `stopping`；收尾確認不了全空 `cleanup_failed`。
- 範例：[掛行程](../examples/daemon/mount.minimal.valid.json)、[回應](../examples/daemon/mount_result.minimal.valid.json)、[反例：帶週期](../examples/daemon/mount.interval.invalid.json)、[反例：沒憑證也沒上層](../examples/daemon/mount.no-token-no-parent.invalid.json)、[砍掉](../examples/daemon/kill.minimal.valid.json)、[反例：多一個欄位](../examples/daemon/kill.extra.invalid.json)。

## P-119．送訊息、取訊息與通道錯誤碼〔使用者方向 2026-09-30，第十九批；參數與上限為建議預設〕

| method | params | result |
|---|---|---|
| `node.send` | `token`、`to`（收件 tick 的 node id）、`message` 必填；`urgent` 可省，布林，預設 false | `{node_id}`（收件 tick 的 id） |
| `node.take` | `token` 必填；`limit` 可省，1～256，預設 256 | `{messages, more}` |

- `message` 是一份檔案收件用的請求物件（common 的 `FileRpcRequest`，[P-301](../messages.md)），照檔案 RPC 放寬、不認得的欄位忽略；外層 params 仍嚴格（[C-07](../../contracts.md)）。序列化後最多 196608 bytes。
- `messages` 按送到的先後排，一次最多 `limit` 件且整個回應不超過 256 KiB，有就至少給一件；`more:true` 表示還有沒取完的。
- 上限：每個收件 tick 最多 256 件、合計 16 MiB（按 `message` 序列化後的 bytes 算），寫死、不開放設定（[B-608](../../daemon.md)）。
- 範例：[送急件](../examples/daemon/send.minimal.valid.json)、[反例：沒帶憑證](../examples/daemon/send.no-token.invalid.json)、[取](../examples/daemon/take.minimal.valid.json)、[回應](../examples/daemon/take_result.minimal.valid.json)、[反例：憑證格式不對](../examples/daemon/take.bad-token.invalid.json)、[憑證不認得](../examples/daemon/error.token_invalid.valid.json)。

**通道的業務錯誤碼**（-32000，`data.code`；其餘沿用 [P-111](provision-and-runner.md)）：

| code | 意思；預設 retryable |
|---|---|
| `token_invalid` | 憑證不認得、已作廢、跟 node 對不上，或 socket 對面的帳號不合；false |
| `kind_mismatch` | 目標種類不符：對掛載行程送 unregister／wake／pause／resume，對登記的 node 送 kill，對掛載行程送 send 或由掛載行程 take；false |
| `mailbox_full` | 收件 tick 的暫存已達上限；true，稍後再送或改走檔案收件 |
| `message_too_large` | 單件訊息超過上限；false |

通道上沿用的：寄件帳號對收件 `requests/` 沒寫權、或用憑證的 tick 不在目標的上層鏈上 `forbidden`；收件 tick 不在這個 daemon `not_registered`；停機中 `stopping`；活程序或維護狀態不合 `busy`。
