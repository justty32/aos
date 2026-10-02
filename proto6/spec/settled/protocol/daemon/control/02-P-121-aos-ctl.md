← [daemon 協議：控制 socket 與 aos-ctl](../control.md)（分檔 2/2）｜所在段落：P-121．控制 socket、環境變數與 aos-ctl〔使用者方向 2026-10-01；欄位名照現行程式〕｜[上一份](01-P-121-socket請求回應.md)

### aos-ctl

```sh
aos-ctl wake [--skip-while-running] [--keep-schedule] [<inst>]
aos-ctl pause [<inst>]
aos-ctl resume [<inst>]
aos-ctl status [<inst>]
aos-ctl kill [<inst>]
aos-ctl restart [<inst>]
AOS_DAEMON_SOCKET=./aos.sock aos-ctl status jobs/report.json    # 人在 shell 手打
aos-ctl --socket /srv/aos/B/aos.sock wake b.json                 # 對別的 daemon 的項（跨 daemon）
```

- `--socket <控制 socket 路徑>`〔[第二十一批](../../../../../notes/verdicts/11-tick-as-unit/23-1001-第二十一批.md#2026-10-01-第二十一批跨-daemon-用-socket-路徑當前綴)〕可以放在任何位置（指令名前後都行），先拿掉再看其他參數。其餘：第一個參數是指令名；旗標可以放在後面任何位置，只有 `wake` 收 `--skip-while-running`／`--keep-schedule`。`<inst>` 最多一個。
- socket 從 `AOS_DAEMON_SOCKET` 拿；給了 `--socket` 就連那個（相對路徑以呼叫者的 cwd 為準），這時不需要 `AOS_DAEMON_SOCKET`、**一定要明寫 `<inst>`**。沒給 `--socket` 時，沒給 `<inst>` 用 `AOS_DAEMON_INST`。
- 成功：`status` 把 daemon 回的那一行原樣印到 stdout；其他指令不印。
- 不重試、不另設逾時。

**結束碼**（[C-08](../../../conventions.md)）

| 碼 | 什麼時候 | stderr |
|---|---|---|
| 0 | daemon 回 `ok:true` | 不印 |
| 1 | 其他所有情況 | 一行 `<代碼>: <說明>`（下表）；沒接住的錯照 Python 預設印 traceback |

| 代碼 | 什麼時候 |
|---|---|
| `usage` | 沒給指令、指令名錯（含 `-h`）、不認得的旗標、旗標給了 `wake` 以外的指令、`<inst>` 給了兩個以上、`--socket` 後面沒接路徑、給了 `--socket` 卻沒寫 `<inst>` |
| `no_daemon` | 沒給 `--socket`，也沒有 `AOS_DAEMON_SOCKET`（或是空字串） |
| `no_inst` | 沒給 `<inst>`，也沒有 `AOS_DAEMON_INST`（或是空字串） |
| `connect` | 連不上 socket |
| `unknown_inst`、`stopped`、`bad_request` | daemon 回的錯，原樣轉出；說明是 daemon 回的 `detail` |

依據：[第十九批](../../../../../notes/verdicts/11-tick-as-unit/21-1001-第十九批.md#2026-10-01-第十九批daemon-上下層用到的三件事)（`kill`、`restart`、`kill_grace_ms`）；[第二十一批](../../../../../notes/verdicts/11-tick-as-unit/23-1001-第二十一批.md#2026-10-01-第二十一批跨-daemon-用-socket-路徑當前綴)（`--socket`）；使用者方向 2026-10-01（控制模組裁定：一個 socket、能連就能做、四指令各對一項、wake 的 `skip_while_running`／`keep_schedule`、status 只看一項、兩個環境變數）；plan m3n。
