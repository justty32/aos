# daemon 協議：控制 socket 與 aos-ctl

← [daemon 協議](README.md)｜行為：[B-641](../../daemon/control.md)｜[慣例](../../conventions.md)

## P-121：控制 socket、環境變數與 aos-ctl

schema：`proto6/spec/protocol/schemas/daemon-ctl.schema.json`（`$defs/Request`、`$defs/Reply` 分開驗）；範例：`proto6/spec/protocol/examples/daemon/ctl_request.*`、`ctl_reply.*`。程式：`aos_daemon_ctl.py`、`aos_ctl.py`。

### 設定

```json
{"modules": {"control": {"socket": "./aos.sock", "kill_grace_ms": 5000}}}
```

`socket` 必填（相對以起點為準）；`kill_grace_ms` 可省、非負數，`kill`／`restart` 送 SIGTERM 後等多久才送 SIGKILL，省＝5000。

### 請求

一條連線一問一答，一行 JSON；**指令名當鍵、inst 字面值當值**，剛好一個指令名：

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
| `wake`／`pause`／`resume`／`status`／`kill`／`restart` | 字串 | 剛好出現一個；值逐字比對 `insts` 的鍵 |
| `skip_while_running` | 布林，預設 false | 只 `wake` 看：正在跑就不補 |
| `keep_schedule` | 布林，預設 false | 只 `wake` 看：不動原本週期排程 |

陌生欄位照收不理（其他指令帶了兩個選項也忽略）。

### 回應

| 情況 | 回應 |
|---|---|
| 成功 | `{"ok":true}`（`kill`／`restart` 送出 SIGTERM 就回） |
| `status` 成功 | `{"ok":true,"inst":…,"running":…,"pending":…,"paused":…,"stopped":…,"last_exit":…,"last_end":…,"next":…}` |
| 失敗 | `{"ok":false,"error":"<代碼>","detail":"<字串>"}` |

| `error` | 什麼時候 |
|---|---|
| `unknown_inst` | inst 不在 `insts` |
| `stopped` | 對被 `stop_on_nonzero` 停掉的項送 `wake`／`restart` |
| `bad_request` | 不是 JSON／物件、指令名不是剛好一個、值型別錯、沒送完一行 |

| `status` 欄位 | 型別 | 意思 |
|---|---|---|
| `inst` | 字串 | inst 字面值 |
| `running`、`pending`、`paused`、`stopped` | 布林 | 在跑／有叫醒還沒跑／暫停／被停掉 |
| `last_exit` | 整數或 null | 上次碼（訊號 N＝128+N） |
| `last_end` | 字串或 null | 上次結束的本地時間 |
| `next` | 字串或 null | 下次週期時間；跑著、暫停、已停時 null |

### 環境變數與 socket 檔

掛了控制模組時，daemon 開 `aos-exec` 的環境放：

| 變數 | 值 |
|---|---|
| `AOS_DAEMON_CTL_SOCKET` | 控制 socket 絕對路徑 |
| `AOS_DAEMON_INST` | 該項 inst 字面值（掛了控制或訊息任一個就放） |

socket 檔開好後 chmod 666；開時路徑上的舊檔先刪、退出前刪掉；父資料夾要先在。

### aos-ctl

```sh
aos-ctl [--socket <路徑>] wake [--skip-while-running] [--keep-schedule] [<inst>]
aos-ctl [--socket <路徑>] pause|resume|status|kill|restart [<inst>]
```

socket 取 `--socket`，沒給取 `AOS_DAEMON_CTL_SOCKET`；給了 `--socket` 就一定要寫 `<inst>`，否則 `<inst>` 省略時取 `AOS_DAEMON_INST`。`status` 把回應原樣印到 stdout，其他不印。詳見 `aos-ctl --help` 或 `aos_ctl.py`。

結束碼：0＝daemon 回 `ok:true`；1＝其他，stderr 一行 `<代碼>: <說明>`，代碼為 `usage`、`no_daemon`、`no_inst`、`connect`，或 daemon 回的 `unknown_inst`／`stopped`／`bad_request`。
