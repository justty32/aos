# proto6/src/py — 控制模組與 aos-ctl

← [proto6/src/py README](../README.md)｜上一份：[aos-daemon](daemon.md)｜下一份：[重讀設定與記住狀態](reload-state.md)

## 控制模組與 aos-ctl（m3n）

照 [plan m3n](../../../plan/m3n-control-module.md) 寫的，新寫。設定檔多寫一段就掛上；沒寫時 daemon 跟上面一模一樣（不建 socket、不傳環境變數）：

```json
{"interval_ms": 60000, "modules": {"control": {"socket": "./aos.sock"}}, "insts": {"a": {}, "jobs/report.json": {}}}
```

- `socket` 必填（沒寫＝設定錯、回 1），相對以起點（`cwd`）為準，算成絕對路徑。開的時候路徑上有舊檔先刪；SIGINT／SIGTERM 退出前刪掉。〔第二十五批〕bind 之後一律 chmod 666（不管有沒有掛帳號模組），誰能連由 socket 所在資料夾的權限決定。
- daemon 開每一次 aos-exec 都在環境加 `AOS_DAEMON_CTL_SOCKET=<socket 絕對路徑>`、`AOS_DAEMON_INST=<這一項的 inst 字面值>`。（〔第二十五批〕環境變數原名 `AOS_DAEMON_SOCKET`，改名、舊名不給。）inst 的任務、`aos-tick` 的任務、下層 `aos-tick <下層>` 的任務都繼承得到，所以**任何一層跑 `aos-ctl wake` 叫醒的都是頂層那一項**。
- 協議：一連線一請求，一行 JSON 進、一行 JSON 出。指令名當鍵、inst 字面值當值：`{"wake":"a"}`、`{"wake":"a","skip_while_running":true,"keep_schedule":true}`、`{"pause":"a"}`、`{"resume":"a"}`、`{"status":"a"}`。回 `{"ok":true}`（status 多帶狀態）或 `{"ok":false,"error":"unknown_inst|stopped|bad_request","detail":…}`。收到就回，不等那一項跑完。每條連線 1 秒逾時；壞請求只影響那一條。

| 指令 | 做什麼 |
|---|---|
| `wake` | 現在跑一次。正在跑：跑完補一次（叫幾次都只補一次）；帶 `skip_while_running` 就作廢。跑完後週期從這次結束重算；帶 `keep_schedule` 就不動原本排程（原本那次已被蓋過去才從這次結束重算）。暫停中：跑一次、跑完照樣暫停。被 `stop_on_nonzero` 停掉：回 `stopped`、不跑 |
| `pause` | 不再照週期跑；正在跑的不殺，待補的取消。stdout 印 `inst=<inst> paused` |
| `resume` | 清掉暫停與已停，馬上跑一次。stdout 印 `inst=<inst> resumed` |
| `status` | `{"ok":true,"inst":…,"running":…,"pending":…,"paused":…,"stopped":…,"last_exit":…,"last_end":…,"next":…}`；還沒跑完過時 `last_exit`／`last_end` 是 `null`，正在跑、暫停、已停時 `next` 是 `null` |

「暫停中 wake 跑一次」「停掉的 wake 回 `stopped`」「resume 一律跑一次」三條是 m3n 待問 1 照建議先做的，使用者可改。暫停只在記憶體，重開 daemon 就沒了（掛了[記住狀態](reload-state.md#重讀設定與記住狀態m3m)時例外）。

`aos-ctl`（socket 從 `AOS_DAEMON_CTL_SOCKET` 拿，`--socket <路徑>` 改連別的 daemon〔第二十一批，這時要明寫 `<inst>`〕；沒給 `<inst>` 用 `AOS_DAEMON_INST`）：

```sh
aos-ctl wake [--skip-while-running] [--keep-schedule] [<inst>]
aos-ctl pause|resume|status [<inst>]
AOS_DAEMON_CTL_SOCKET=./aos.sock aos-ctl status jobs/report.json    # 人在 shell 手打
```

成功回 0（status 把回應那一行原樣印到 stdout，其他不印）；其餘回 1、stderr 一行 `代碼: 說明`：`usage`（指令名錯、多給參數、旗標給錯指令）、`no_daemon`（沒 `AOS_DAEMON_CTL_SOCKET`）、`no_inst`、`connect`（連不上），或照 daemon 回的 `unknown_inst`／`stopped`／`bad_request`。

| 函式 | plan 步驟 |
|---|---|
| `aos_daemon.load_setup()`（`load_config()` 照舊回兩個值） | 1 設定檔 |
| `aos_daemon.loop()`、`_next_run()`、`Item` 的狀態與 `cond` | 2 叫得醒、停得住的迴圈 |
| `aos_daemon_ctl.serve()`、`_accept_loop()`、`_one()`、`parse()`、`handle()`、`status()` | 3 socket 與協議（4 指令都在 `handle()`） |
| `aos_daemon.main()` 設 `item.env`、`run_once()` 帶 `env=` | 4 往下傳環境變數 |
| `aos_ctl.main()`、`bin/aos-ctl` | 5 aos-ctl |
| `aos_daemon_ctl.serve()` 先刪舊檔、`aos_daemon._quit()` 刪 socket | 6 socket 檔的開與收 |

測試 `tests/test_ctl_loop.py`、`test_ctl_protocol.py`（原 `test_ctl.py`）：`Step1Config`～`Step6SocketFile`，一個類別一步，兩檔合計約 18 秒。任務量週期用 `/proc/uptime` 寫時間、不用 `date`：WSL 的牆上時鐘偶爾被校時往前跳好幾秒，`test_keep_schedule` 約十次錯一次就是這個（2026-10-01 改）。
