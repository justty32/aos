# proto6/src/py — 訊息與 aos-mq

← [proto6/src/py README](../README.md)｜上一份：[收屍／cgroup](cgroup.md)｜下一份：[帳號](account.md)

## 訊息與 aos-mq（m3m 模組四）

照 [plan m3m](../../../plan/m3m-daemon-modules.md) 模組四寫的（2026-10-01 第十二批，M1～M4 照建議），`lib/aos_daemon_mq.py`、`lib/aos_mq.py`、`bin/aos-mq`。設定檔寫 `modules.mq` 才掛，沒寫時 daemon 跟上面一模一樣。

```json
{"interval_ms": 60000, "modules": {"mq": {"socket": "./aos-mq.sock"}}, "insts": {"a": {}, "b": {}}}
```

- 另開一個 unix socket（`socket` 相對以起點為準；不走控制 socket），一連線一請求、一行 JSON 來回，伺服器那套跟控制模組共用（`aos_daemon_ctl.serve()` 多收一個 `answer`）。
- **每項一個信箱**（`Item.mailbox`），記憶體裡、先進先出，daemon 重開就丟。重讀設定時還在的項信箱照留，拿掉的項連信箱一起丟，加回來從空的開始。
- 掛了之後每次開 `aos-exec` 多放 `AOS_DAEMON_MQ_SOCKET`；`AOS_DAEMON_INST` 掛了控制或訊息任一個就放（M2）。
- **急件**（`--urgent`）：信放進信箱後照控制模組 `wake`（不帶選項）叫醒收件那一項：正在跑就補一次、暫停中跑一次、已停不跑（信照收）。不用掛控制模組。

```text
aos-mq send [--urgent] [--socket <對方訊息 socket>] (<收件 inst> | --all | --channel <頻道>) <JSON|->
                                                # from 自動填 AOS_DAEMON_INST、from_socket 自動填自己的 socket（沒有＝null）
aos-mq take [--from [<寄件 inst>…]]… [--to [<收件地址>…]]…
                                                # 只取自己（AOS_DAEMON_INST）的信箱；每封一行 {"from":…,"from_socket":…,"to":…,"msg":…}
aos-mq peek [--from [<寄件 inst>…]]… [--to [<收件地址>…]]…   # 同上，但不取走
```

結束碼照 `aos-ctl`：成功 0；`usage:`（含 `<JSON>` 不是 JSON）、`no_inst:`、`no_daemon:`、`connect:`、`unknown_inst:`、`bad_request:` 一律 1，stderr 一行。

| 函式 | 做什麼 |
|---|---|
| `aos_daemon_mq.serve()`、`parse()`、`handle()` | 收 send／broadcast／channel／take／peek、放信取信看信、急件叫醒 |
| `aos_daemon_mq.item_subscribe()` | 讀一項的 `mq.subscribe`（第二十二批） |
| `aos_daemon.give_env()` | 放 `AOS_DAEMON_SOCKET`／`AOS_DAEMON_MQ_SOCKET`／`AOS_DAEMON_INST` |
| `aos_daemon._quit()` | 退出前刪兩個 socket 檔 |
| `aos_mq.main()`、`bin/aos-mq` | 小工具 |

- **取信只能取自己的信箱**（2026-10-01 第十四批）：`take` 不收 `<inst>`、只用 `AOS_DAEMON_INST`；`--from` 只取那個寄件人的、其他照順序留著。socket 不驗身分，這是 `aos-mq` 那一側擋的（第十五批：照「能連就能做」，daemon 不核對）。
- **`peek` 與多個寄件人**（2026-10-01 第十五批）：`peek` 跟 `take` 一樣但不取走。`--from a c d` 收到下一個 `--` 開頭的參數為止；`--from` 不接＝寄件人是 null 的信；可以重複寫、疊加。socket 上 `from` 是非空陣列（元素字串或 null）。

- **跨 daemon**（2026-10-01 第二十一批）：收件地址的前綴是對方 daemon 的訊息 socket 路徑。`send --socket <路徑>` 直接連對方寄（相對路徑以呼叫者 cwd 為準，有 `--socket` 就不需要 `AOS_DAEMON_MQ_SOCKET`）；信裡自動帶 `from_socket`（自己的 `AOS_DAEMON_MQ_SOCKET` 的絕對路徑），收件方回信 `send --socket <from_socket> <from>`。daemon 不轉送、只是多存一欄。`take`／`peek` 不收 `--socket`；`--from` 只比 `from`。`aos-ctl --socket <控制 socket>` 同理，但要明寫 `<inst>`。peers（暱稱→socket 路徑）先不做。

- **廣播與頻道**（2026-10-01 第二十二批）：`send --all` 寄給每一項、`send --channel <頻道>` 寄給設定裡 `"mq": {"subscribe": [...]}` 有它的項，都不寄給自己（`from` 是那一項、`from_socket` 是 null 或這個 daemon 的）；成功時 stdout 印一行收到的項數。信多 `to`（收件 inst／`*`／`#<頻道>`），`take`／`peek --to` 篩。socket 請求 `{"broadcast":true,…}`／`{"channel":"x",…}`，寄的回應多 `delivered`。重讀設定時訂閱照新的。

測試 `tests/test_mq_send.py`、`test_mq_broadcast.py`（原 `test_mq.py`，34 條，約 6 秒；`CrossDaemon` 三條開兩個 daemon、`Broadcast` 十一條）。
