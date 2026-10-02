← [daemon 協議：訊息 socket 與 aos-mq](../mq.md)（分檔 3/3）｜所在段落：P-125．訊息 socket、環境變數與 aos-mq〔使用者 2026-10-01 第十二批；欄位名照現行程式〕｜[上一份](02-P-125-回應與環境變數.md)

### aos-mq

```sh
aos-mq send [--urgent] [--socket <對方訊息 socket>] (<收件 inst> | --all | --channel <頻道>) <JSON|->
aos-mq take [--from [<寄件 inst>…]]… [--to [<收件地址>…]]…
aos-mq peek [--from [<寄件 inst>…]]… [--to [<收件地址>…]]…
```

給任務用；人在 shell 手打怎麼看信，aos 不管（第十五批）。

- 第一個參數是指令名；只有 `--` 開頭的算旗標（`-` 是從 stdin 讀、`-5` 是 JSON 負數），只有 `send` 收 `--urgent`、`--socket <路徑>`〔第二十一批〕、`--all`、`--channel <頻道>`〔第二十二批〕，只有 `take`、`peek` 收 `--from`、`--to`〔第二十二批〕，可以放在後面任何位置。`--to` 的寫法同 `--from`（接到下一個 `--` 開頭的參數為止、不接＝`null`、可重複疊加），送成 `to` 陣列。`--from` 後面接的參數到下一個 `--` 開頭的參數為止都是寄件 inst（`-x` 這種一個 `-` 開頭的也算寄件人）；一個都不接＝`null`；可以重複寫，全部疊起來送成一個 `from` 陣列〔第十五批〕。
- `send`：`<收件 inst>`、`--all`、`--channel <頻道>` 三選一〔第二十二批〕，單寄要剛好兩個位置參數、`--all`／`--channel` 要剛好一個（`<JSON>`），送成 `send`／`broadcast:true`／`channel` 請求；`from` 填 `AOS_DAEMON_INST`（沒有或空字串就 `null`），`from_socket` 填 `AOS_DAEMON_MQ_SOCKET` 轉成的絕對路徑（沒有或空字串就 `null`）。`take`、`peek` 不收位置參數，只對 `AOS_DAEMON_INST` 那一項的信箱〔第十四批〕；給了 `--from` 就在請求帶 `from` 陣列。
- socket 從 `AOS_DAEMON_MQ_SOCKET` 拿；`send` 給了 `--socket` 就連那個（相對路徑以呼叫者的 cwd 為準，送出前不轉換），這時不需要 `AOS_DAEMON_MQ_SOCKET`。`take`、`peek` 不收 `--socket`。
- 成功：`take`、`peek` 每封信一行 `{"from":…,"from_socket":…,"msg":…}`（不帶多餘空白）印到 stdout，沒信什麼都不印；單寄不印；`--all`／`--channel` 印一行 daemon 回的 `delivered`（例如 `2`，沒人收是 `0`）〔第二十二批〕。
- 不重試、不另設逾時。

**結束碼**（[C-08](../../../conventions.md)）：daemon 回 `ok:true` 回 0；其他一律回 1，stderr 一行 `<代碼>: <說明>`。

| 代碼 | 什麼時候 |
|---|---|
| `usage` | 沒給指令、指令名錯、不認得的旗標、`send` 的 `<收件 inst>`／`--all`／`--channel` 不是剛好一個、位置參數數目不對、`--channel` 後面沒接頻道名或給了兩次、`<JSON>` 不是 JSON、`take`／`peek` 給了位置參數（`--from` 前面的）、`take`／`peek` 帶 `--urgent`、`--socket`、`--all` 或 `--channel`、`--socket` 後面沒接路徑 |
| `no_daemon` | 沒給 `--socket`，也沒有 `AOS_DAEMON_MQ_SOCKET`（或是空字串） |
| `no_inst` | `take`、`peek` 時沒有 `AOS_DAEMON_INST`（或是空字串） |
| `connect` | 連不上 socket |
| `unknown_inst`、`bad_request` | daemon 回的錯，原樣轉出；說明是 daemon 回的 `detail` |

依據：使用者 2026-10-01 第十二批（M1～M4 照 plan 建議：`from` 自動填不核對、`AOS_DAEMON_INST` 掛任一個就放、取信不限自己、`aos-mq send`／`take`）；第十四批（取信只能取自己的信箱、可用 `--from` 只取某個寄件人的，推翻 M3）；第十五批（daemon 不核對取信的人、加 `peek`、`--from` 收多個、不接＝null、跨 daemon 不管）；第二十一批（跨 daemon 用 socket 路徑當前綴：`send --socket`、`from_socket`；peers 先不做）；第二十二批（廣播與頻道：「ab都做」「好，如你所建議」）；plan m3m 模組四。
