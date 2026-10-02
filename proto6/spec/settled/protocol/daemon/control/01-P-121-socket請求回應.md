← [daemon 協議：控制 socket 與 aos-ctl](../control.md)（分檔 1/2）｜[下一份](02-P-121-aos-ctl.md)

## P-121．控制 socket、環境變數與 aos-ctl〔使用者方向 2026-10-01；欄位名照現行程式〕

### 設定

daemon 設定檔（[P-120](../core.md)）頂層 `modules` 裡寫：

```json
{"modules": {"control": {"socket": "./aos.sock"}}}
```

`socket` 必填，字串；相對以起點為準，daemon 算成絕對路徑。〔第十九批〕`kill_grace_ms` 可省，非負數（毫秒），`kill`／`restart` 送 SIGTERM 後等多久才送 SIGKILL；省略＝5000。

### socket 上的一來一回

- Unix stream socket。**一條連線只問一次**：客戶端送一行 JSON（UTF-8、LF 結尾），daemon 回一行 JSON，然後關掉。
- daemon 只讀第一行；**每條連線 1 秒內**要送完那一行，超過就直接關掉、不回。對面沒送完一行就關了寫的那一邊，回 `bad_request`。
- 連線一條一條處理。一條連線出錯不影響下一條。
- 不驗身分：連得上就能下任何指令（[B-641](../../../daemon/control.md)）。

### 請求

**指令名當鍵、inst 字面值當值**，剛好一個指令名：

```json
{"wake":"a"}
{"wake":"jobs/report.json","skip_while_running":true,"keep_schedule":true}
{"pause":"a"}
{"resume":"a"}
{"status":"a"}
{"kill":"a"}
{"restart":"daemons/lorkhan.json"}
```

| 欄位 | 型別 | 意思 |
|---|---|---|
| `wake`／`pause`／`resume`／`status`／`kill`／`restart` | 字串 | 六個裡剛好出現一個（後兩個〔第十九批〕）；值是 inst 字面值，跟設定檔 `insts` 的鍵逐字比對 |
| `skip_while_running` | 布林，可省，預設 false | 只有 `wake` 看；正在跑就不補，這次請求什麼都不改（已記下的補跑與它的選項照舊，[B-641](../../../daemon/control.md)）〔astra 報告必修 4〕 |
| `keep_schedule` | 布林，可省，預設 false | 只有 `wake` 看；不動原本的週期排程 |

- 〔使用者方向 2026-10-01〕**不認得的欄位照收不理**，不回 `bad_request`；`pause`／`resume`／`status` 帶了那兩個選項也忽略（不管型別）。
- 這是 [C-07](../../../../contracts.md)「哪裡放寬」表裡單列的一行：現行控制 socket 忽略不認得的欄位；嚴格拒絕只剩舊設計的 daemon IPC（[暫緩區 P-103](../../../deferred/protocol/daemon/startup-and-ipc.md)）。

### 回應

| 情況 | 回應 |
|---|---|
| 成功（`wake`、`pause`、`resume`、`kill`、`restart`） | `{"ok":true}`（`kill`／`restart` 送出 SIGTERM 就回，不等那一次結束） |
| 成功（`status`） | `{"ok":true,"inst":…,"running":…,"pending":…,"paused":…,"stopped":…,"last_exit":…,"last_end":…,"next":…}`（下表） |
| 失敗 | `{"ok":false,"error":"<代碼>","detail":"<字串>"}` |

**錯誤代碼**

| `error` | 什麼時候 | `detail` |
|---|---|---|
| `unknown_inst` | 指名的 inst 不在 `insts` 裡 | 那個 inst 字面值 |
| `stopped` | 對被 `stop_on_nonzero` 停掉的項送 `wake` 或 `restart` | 那個 inst 字面值 |
| `bad_request` | 不是 JSON、不是物件、指令名不是剛好一個、指令的值不是字串、`wake` 的選項不是布林、沒送完一行 | 白話說明 |

**`status` 的欄位**

| 欄位 | 型別 | 意思 |
|---|---|---|
| `inst` | 字串 | 這一項的 inst 字面值 |
| `running` | 布林 | 現在有 `aos-exec` 在跑 |
| `pending` | 布林 | 有一次叫醒記下、還沒跑 |
| `paused` | 布林 | 暫停中 |
| `stopped` | 布林 | 被 `stop_on_nonzero` 停掉 |
| `last_exit` | 整數或 null | 上一次的碼（被訊號 N 殺掉是 128+N）；還沒跑完過是 null |
| `last_end` | 字串或 null | 上一次結束的本地時間（格式同 [P-120](../core.md) 的 stdout）；還沒跑完過是 null |
| `next` | 字串或 null | 下次照週期該跑的本地時間；正在跑、暫停、已停時是 null |

回應一律是不帶多餘空白的一行 JSON，非 ASCII 字照原樣輸出。

schema：[daemon-ctl](../../../../protocol/schemas/daemon-ctl.schema.json)（請求與回應都在裡面）。〔astra 報告必修 5、設計 3〕請求與回應**分開驗**：請求照 `$defs/Request`、回應照 `$defs/Reply`，不為了合併成一個驗證入口而多加協議沒有的限制（例如請求的陌生欄位要照收）。範例：請求 [wake 帶選項](../../../../protocol/examples/daemon/ctl_request.wake.valid.json)、[status](../../../../protocol/examples/daemon/ctl_request.status.valid.json)、[帶不認得的欄位照收](../../../../protocol/examples/daemon/ctl_request.extra-field.valid.json)；反例 [兩個指令名](../../../../protocol/examples/daemon/ctl_request.two-commands.invalid.json)、[inst 不是字串](../../../../protocol/examples/daemon/ctl_request.inst-not-string.invalid.json)。回應 [成功](../../../../protocol/examples/daemon/ctl_reply.ok.valid.json)、[status](../../../../protocol/examples/daemon/ctl_reply.status.valid.json)、[已停](../../../../protocol/examples/daemon/ctl_reply.stopped.valid.json)；反例 [錯誤代碼不認得](../../../../protocol/examples/daemon/ctl_reply.unknown-error.invalid.json)、[status 缺 next](../../../../protocol/examples/daemon/ctl_reply.status-missing-next.invalid.json)。〔第十九批〕請求 [kill](../../../../protocol/examples/daemon/ctl_request.kill.valid.json)、[restart](../../../../protocol/examples/daemon/ctl_request.restart.valid.json)；反例 [kill 與 restart 同時](../../../../protocol/examples/daemon/ctl_request.kill-and-restart.invalid.json)。

### 環境變數

掛了控制模組時，daemon 每次開 `aos-exec` 都在環境裡放（總表 [C-10](../../../conventions.md)）：

| 變數 | 值 |
|---|---|
| `AOS_DAEMON_SOCKET` | 控制 socket 的絕對路徑 |
| `AOS_DAEMON_INST` | 這一項的 inst 字面值 |

名字 `AOS_DAEMON_SOCKET` 沿用舊設計 [P-117](../../../deferred/protocol/daemon/channel.md)，意思改成控制 socket；通道憑證 `AOS_TICK_TOKEN` 現行控制不使用；舊通道憑證暫緩，未來另定〔astra 報告必修 7〕。沒掛控制模組時不放 `AOS_DAEMON_SOCKET`；`AOS_DAEMON_INST` 掛了控制或訊息模組任何一個就放（〔第十二批〕M2，[P-125](../mq.md)）。

### socket 檔

daemon 開的時候，路徑上已有檔（含舊的 socket）先刪掉；收到 SIGINT／SIGTERM 退出前刪掉。父資料夾要先在（默認一切正常，daemon 不建）。
