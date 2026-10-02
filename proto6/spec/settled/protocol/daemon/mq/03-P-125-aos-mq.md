← [daemon 協議：訊息 socket 與 aos-mq](../mq.md)（分檔 3/3）｜所在段落：P-125．訊息 socket、環境變數與 aos-mq〔使用者 2026-10-01 第十二批；2026-10-02 第二十五批改成多扇門；欄位名照現行程式〕｜[上一份](02-P-125-回應與環境變數.md)

### aos-mq

```sh
aos-mq send <socket 路徑> <JSON|->
aos-mq take <socket 路徑>
aos-mq peek <socket 路徑>
```

```sh
aos-mq send "$AOS_DAEMON_MQ_ALERTS" '{"level":"warn","text":"disk 90%"}'   # 任務裡寄
aos-mq take "$AOS_DAEMON_MQ_SOCKET_1"                                      # 任務裡取自己的信
aos-mq send /srv/aos/B/doors/team-a/s -  < reply.json                      # 寄到別的 daemon 的門，信從 stdin 讀
```

給任務用；人在 shell 手打怎麼看信，aos 不管（第十五批）。

- 第一個參數是指令名，第二個是門的 socket 路徑（相對以呼叫者的 cwd 為準，送出前不轉換）；`send` 還要第三個 `<JSON>`，給 `-` 就從 stdin 讀。參數個數一定要剛好（`send` 三個、`take`／`peek` 兩個）。
- 〔第二十五批〕只有 `--` 開頭的算旗標，**一律不收**（`--urgent`、`--socket`、`--all`、`--channel`、`--from`、`--to` 都拿掉了），給了就回 `usage`；`-` 是讀 stdin、`-5` 是 JSON 負數。
- `send`：送 `{"send":<JSON>}`；不需要任何環境變數。成功什麼都不印。
- `take`、`peek`：送 `{"take"|"peek":<AOS_DAEMON_INST>}`；不收 inst 參數，沒有 `AOS_DAEMON_INST`（或是空字串）回 `no_inst`。成功時每封信一行（信的 JSON 原樣、不帶多餘空白、非 ASCII 照原樣）印到 stdout，沒信什麼都不印。
- 檢查順序：先 `usage`，再 `no_inst`，再連線（AI 隊定）。
- 不重試、不另設逾時。

**結束碼**（[C-08](../../../conventions.md)）：daemon 回 `ok:true` 回 0；其他一律回 1，stderr 一行 `<代碼>: <說明>`。

| 代碼 | 什麼時候 |
|---|---|
| `usage` | 沒給指令、指令名錯、任何 `--` 開頭的旗標、參數個數不對（含沒給 socket 路徑、`take`／`peek` 多給了 inst）、`<JSON>` 不是 JSON |
| `no_inst` | `take`、`peek` 時沒有 `AOS_DAEMON_INST`（或是空字串） |
| `connect` | 連不上那個路徑的 socket |
| `unknown_inst`、`bad_request` | daemon 回的錯，原樣轉出；說明是 daemon 回的 `detail` |

舊代碼 `no_daemon`（沒有 `AOS_DAEMON_MQ_SOCKET`）在 `aos-mq` 用不到了：路徑一律明寫（`aos-ctl` 的 `no_daemon` 照留，[P-121](../control.md)）。

依據：使用者 2026-10-01 第十二批（M1～M4 照 plan 建議：`AOS_DAEMON_INST` 掛任一個就放、`aos-mq send`／`take`）；第十四、十五批（取信只能取自己的、daemon 不核對、加 `peek`）；**2026-10-02 第二十五批**（「aos-mq take <socket...>，然後不允許指定後面的inst，一律吃環境變數」「aos-mq peek可以保留」；多扇門、信原樣、合併叫醒、socket 一律 666；取代第十四、十五批的 `--from`、第二十一批的 `--socket`／`from_socket`、第二十二批的 `--all`／`--channel`／`--to`／`delivered`、`--urgent`）；plan m3m 模組四。
