# proto6/src/py — 訊息與 aos-mq

← [proto6/src/py README](../README.md)｜上一份：[收屍／cgroup](cgroup.md)｜下一份：[帳號](account.md)

## 訊息與 aos-mq（m3m 模組四）

照 [plan m3m](../../../plan/m3m-daemon-modules.md) 模組四寫的，2026-10-02 第二十五批改成**多扇門**（[verdicts 11 第二十五批](../../../notes/verdicts/11-tick-as-unit/26-1002-第二十五批.md#2026-10-02-第二十五批訊息多扇門控制-socket-改名)）。`lib/aos_daemon_mq.py`、`lib/aos_mq.py`、`bin/aos-mq`。設定檔寫 `modules.mq` 才掛，沒寫時 daemon 跟上面一模一樣。

```json
{"interval_ms": 60000,
 "modules": {"mq": {"SOCKET_1": "./mq-1.sock", "ALERTS": "/srv/aos/doors/alerts/s"}},
 "insts": {"a": {"mq": ["SOCKET_1", "ALERTS"]}, "b": {"mq": ["ALERTS"]}, "c": {}}}
```

- `modules.mq`＝「門名 → socket 路徑」（相對以起點為準）。每扇門一個 unix socket，一連線一請求、一行 JSON 來回，伺服器那套跟控制模組共用（`aos_daemon_ctl.serve()` 多收一個 `answer`）。門名限 `[A-Za-z0-9_]+`、至少一扇；兩扇門同路徑、或跟控制 socket 同路徑＝設定錯。
- 每項 `mq`＝訂哪幾扇門（字串陣列，沒寫＝不訂；寫了沒有的門＝設定錯；重複照一次算）。沒掛模組時每項的 `mq` 忽略。
- **每項一個信箱**（`Item.mailbox`），記憶體裡、先進先出，daemon 重開就丟。從某扇門收到 `{"send": <信>}`：信（原樣，不加任何欄位）放進訂了那扇門的每一項的信箱（寄件人自己有訂也收），回 `{"ok":true}`；沒人訂就丟掉、照樣回 ok。
- **合併叫醒**：放進信箱後，沒停掉的項記一次「待補跑」（同控制模組 `wake` 不帶選項）：沒在跑馬上跑、正在跑跑完補一次（連來幾封都只補一次）、暫停中跑一次照樣暫停、已停不跑（信照收）。不用掛控制模組。
- `{"take":"<inst>"}`／`{"peek":"<inst>"}` 從**任何一扇門**都行，回 `{"ok":true,"messages":[…]}`；daemon 不核對身分（能連就能做）。
- 掛了之後每次開 `aos-exec`，每一項都拿到**每一扇門**的 `AOS_DAEMON_MQ_<門名>=<絕對路徑>`（不管有沒有訂），加 `AOS_DAEMON_INST`（掛了控制或訊息任一個就放）。
- **socket 檔一律 chmod 666**（bind 之後立刻；控制 socket 也一樣，不管有沒有掛帳號）。誰能連由 socket 所在資料夾的擁有者／群組／權限決定，資料夾由管理者事先建好，daemon 不建不改。
- 重讀設定：每項 `mq` 照新設定，但照**開起來時的門**核（寫了沒有的門＝重讀出錯、整份不套用）；`modules.mq` 改了不套用、警告；還在的項信箱照留，拿掉的項連信箱一起丟。

```text
aos-mq send <socket 路徑> <JSON|->     # 寄到那扇門（跨 daemon 就寫對方的門）；成功什麼都不印
aos-mq take <socket 路徑>              # 取自己（AOS_DAEMON_INST）全部的信，一封一行
aos-mq peek <socket 路徑>              # 同上，但不取走
```

- `<socket 路徑>` 相對以呼叫者 cwd 為準，通常寫 `"$AOS_DAEMON_MQ_SOCKET_1"` 這樣。`send` 不需要任何環境變數；`take`／`peek` 只用 `AOS_DAEMON_INST`，不收 inst 參數。
- 結束碼照 `aos-ctl`：成功 0；`usage:`（參數個數不對、`<JSON>` 不是 JSON、任何 `--` 旗標）、`no_inst:`、`connect:`、`unknown_inst:`、`bad_request:` 一律 1，stderr 一行。檢查順序 usage → no_inst → connect。

| 函式 | 做什麼 |
|---|---|
| `aos_daemon_mq.serve(name, path, items)`、`parse()`、`handle()` | 開一扇門；收 send／take／peek、放信取信看信、合併叫醒 |
| `aos_daemon_mq.doors_of(modules_mq, start, ctl_sock)` | 核 `modules.mq`，回 `{門名: 絕對路徑}`（`Setup.mq_doors`） |
| `aos_daemon_mq.item_doors(entry, doors)` | 讀一項的 `mq`（`Item.doors`） |
| `aos_daemon.give_env()` | 放 `AOS_DAEMON_CTL_SOCKET`／`AOS_DAEMON_MQ_<門名>`／`AOS_DAEMON_INST` |
| `aos_daemon._quit()` | 退出前刪所有 socket 檔 |
| `aos_mq.main()`、`bin/aos-mq` | 小工具 |

拿掉的舊做法（第十四、十五、二十一、二十二批）：收件 inst、`--urgent`、`--from`、`--to`、`--all`、`--channel`、`mq.subscribe`、`--socket`、信的 `from`／`from_socket`／`to`、`delivered`。

測試 `tests/test_mq_send.py`（寄取看、叫醒、錯誤與設定錯）、`tests/test_mq_doors.py`（多扇門、訂閱、環境變數、跨 daemon、重讀、666）。
