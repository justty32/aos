# daemon 協議：訊息 socket 與 aos-mq

← [daemon 協議](README.md)｜[共用約定](../../../protocol/README.md)｜行為正本：[B-645](../../daemon/mq.md)｜[慣例](../../conventions.md)

本篇只有 P-125，只寫格式。信箱、急件叫醒的規則以 [B-645](../../daemon/mq.md) 為正本。

依據：[verdicts 11 篇末「2026-10-01 第十二批：cgroup 與帳號」](../../../../notes/verdicts/11-tick-as-unit/14-1001-第十二批.md#2026-10-01-第十二批cgroup-與帳號)、[第十四批：aos-mq 取信](../../../../notes/verdicts/11-tick-as-unit/16-1001-第十四十五批.md#2026-10-01-第十四批aos-mq-取信)、[第二十一批：跨 daemon 用 socket 路徑當前綴](../../../../notes/verdicts/11-tick-as-unit/23-1001-第二十一批.md#2026-10-01-第二十一批跨-daemon-用-socket-路徑當前綴)、[第二十二批：廣播與頻道](../../../../notes/verdicts/11-tick-as-unit/24-1001-1002-第二十二二十三批.md#2026-10-01-第二十二批廣播與頻道)、[plan m3m 模組四](../../../../plan/m3m-daemon-modules/05-模組四-訊息.md#模組四訊息modulesmq)；現行程式 [訊息與 aos-mq](../../../../src/py/README.md#訊息與-aos-mqm3m-模組四)（有出入以程式為準）。

## P-125．訊息 socket、環境變數與 aos-mq〔使用者 2026-10-01 第十二批；欄位名照現行程式〕

### 設定

daemon 設定檔（[P-120](core.md)）頂層 `modules` 裡寫：

```json
{"modules": {"mq": {"socket": "./aos-mq.sock"}}}
```

`socket` 必填，字串；相對以起點為準，daemon 算成絕對路徑。範例：[掛控制與訊息](../../../protocol/examples/daemon/core-config.mq.valid.json)；反例：[沒寫 socket](../../../protocol/examples/daemon/core-config.mq-no-socket.invalid.json)。

〔第二十二批〕每一項可以寫 `"mq": {"subscribe": ["<頻道>", …]}`：這一項訂哪些頻道。`mq` 要是物件、`subscribe` 要是非空字串的陣列，可省（＝不訂）；格式不對算設定錯（開跑回 1、重讀照 [P-122](reload.md) 不套用）。沒掛訊息模組時每項的 `mq` 照不認得的鍵忽略。範例：[訂閱](../../../protocol/examples/daemon/core-config.mq-subscribe.valid.json)；反例：[subscribe 是字串](../../../protocol/examples/daemon/core-config.mq-subscribe-string.invalid.json)。

### socket 上的一來一回

跟控制 socket 一樣（[P-121](control.md)「socket 上的一來一回」）：Unix stream socket、一條連線只問一次、一行 JSON（UTF-8、LF 結尾）來回、每條連線 1 秒內要送完那一行、一條出錯不影響下一條、不驗身分。socket 檔的開與刪也照 P-121。

### 請求

```json
{"send":"b.json","msg":{"hi":1},"from":"a.json","from_socket":"/srv/aos/A/aos-mq.sock","urgent":true}
{"send":"b.json","msg":null}
{"take":"b.json"}
{"take":"b.json","from":["a.json","c.json"]}
{"peek":"b.json","from":[null]}
{"broadcast":true,"msg":{"hi":1},"from":"a.json","from_socket":"/srv/aos/A/aos-mq.sock"}
{"channel":"deploy","msg":"v2","from":"c.json"}
{"peek":"b.json","to":["*","#deploy"]}
```

| 欄位 | 型別 | 意思 |
|---|---|---|
| `send`／`broadcast`／`channel`／`take`／`peek` | 見右 | 五個裡剛好出現一個。`send`、`take`、`peek` 是字串＝inst 字面值（`send` 是收件人，`take`、`peek` 是哪一項的信箱），跟設定檔 `insts` 的鍵逐字比對。〔第二十二批〕`broadcast` 只能是 `true`＝寄給每一項；`channel` 是非空字串＝頻道名，寄給 `mq.subscribe` 有它的項；兩種都不寄給寄件人自己（`from` 等於那一項、而且 `from_socket` 是 null 或就是這個 daemon 的訊息 socket） |
| `msg` | 任何 JSON 值 | 寄（`send`／`broadcast`／`channel`，下同）必填（可以是 `null`）；daemon 不看內容 |
| `from` | `send`：字串或 null，可省，預設 null；`take`、`peek`：非空陣列，元素是字串或 null，可省 | `send`：寄件 inst，原樣存、不核對。`take`、`peek`〔第十四批；第十五批改陣列〕：只要寄件人在陣列裡的信（`null`＝寄件人是 null 的信），其他照順序留著；省略＝全部 |
| `from_socket` | 字串或 null，可省，預設 null | 〔第二十一批〕只有 `send` 看；寄件方 daemon 的訊息 socket 路徑（`aos-mq send` 填絕對路徑），原樣存、不核對，收件方回信用 |
| `urgent` | 布林，可省，預設 false | 只有寄的時候看；放進信箱後叫醒收件的每一項 |
| `to` | 非空陣列，元素是字串或 null，可省 | 〔第二十二批〕只有 `take`、`peek` 看：只要信的 `to` 在陣列裡的（信的 `to` 不會是 null，所以 null 比不到）；跟 `from` 一起給＝兩個都要符合；省略＝全部 |

不認得的欄位照收不理（同 P-121）；`take`、`peek` 帶了 `msg`、`from_socket`、`urgent` 也忽略；寄的時候帶了 `to` 也忽略（信的 `to` 由 daemon 填）。跨 daemon 寄信就是直接連對方 daemon 的這個 socket 送 `send`（第二十一批），格式一樣；daemon 不轉送。socket 不驗身分：`take`、`peek` 指名任何一項都取得到（「只能取／看自己」是 `aos-mq` 那一側做的，[B-645](../../daemon/mq.md)；使用者 2026-10-01 第十五批 1.a：照 POC「能連就能做」，daemon 不核對）。

### 回應

| 情況 | 回應 |
|---|---|
| 寄成功（含急件寄給已停的項：信收下、不跑） | `{"ok":true,"delivered":<放進了幾個信箱>}`〔第二十二批〕：`send` 一定是 1；`broadcast`／`channel` 沒人收是 0，也算成功 |
| `take`、`peek` 成功 | `{"ok":true,"messages":[{"from":…,"from_socket":…,"to":…,"msg":…},…]}`，先寄的在前（`from_socket` 沒帶的信是 `null`；`to` 是收件 inst、`"*"` 或 `"#<頻道>"`，第二十二批）；沒信是 `[]`。`peek` 不把信從信箱拿走 |
| 失敗 | `{"ok":false,"error":"<代碼>","detail":"<字串>"}` |

| `error` | 什麼時候 | `detail` |
|---|---|---|
| `unknown_inst` | `send`／`take`／`peek` 指名的 inst 不在 `insts` 裡（`broadcast`／`channel` 不會回這個） | 那個 inst 字面值 |
| `bad_request` | 不是 JSON、不是物件、`send`／`broadcast`／`channel`／`take`／`peek` 不是剛好一個、`send`／`take`／`peek` 的值不是字串、`broadcast` 不是 `true`、`channel` 不是非空字串、寄的時候沒有 `msg`、寄的時候 `from` 或 `from_socket` 不是字串或 null、`take`／`peek` 的 `from` 或 `to` 不是非空陣列或元素不是字串或 null、`urgent` 不是布林、沒送完一行 | 白話說明 |

回應一律是不帶多餘空白的一行 JSON，非 ASCII 字照原樣輸出。

schema：[daemon-mq](../../../protocol/schemas/daemon-mq.schema.json)，請求與回應分開驗（請求照 `$defs/Request`、回應照 `$defs/Reply`，同 P-121）。範例：請求 [send 全欄位](../../../protocol/examples/daemon/mq_request.send.valid.json)、[send 最少](../../../protocol/examples/daemon/mq_request.send-minimal.valid.json)、[take](../../../protocol/examples/daemon/mq_request.take.valid.json)、[take 帶 from](../../../protocol/examples/daemon/mq_request.take-from.valid.json)、[peek 帶 from（含 null）](../../../protocol/examples/daemon/mq_request.peek-from.valid.json)；反例 [take 的 from 是數字](../../../protocol/examples/daemon/mq_request.take-from-number.invalid.json)、[from 是空陣列](../../../protocol/examples/daemon/mq_request.take-from-empty.invalid.json)、[from 是字串不是陣列](../../../protocol/examples/daemon/mq_request.peek-from-string.invalid.json)、[send 沒有 msg](../../../protocol/examples/daemon/mq_request.send-no-msg.invalid.json)、[兩個都有](../../../protocol/examples/daemon/mq_request.both.invalid.json)、[urgent 不是布林](../../../protocol/examples/daemon/mq_request.urgent-not-bool.invalid.json)。回應 [成功](../../../protocol/examples/daemon/mq_reply.ok.valid.json)、[取到信](../../../protocol/examples/daemon/mq_reply.taken.valid.json)、[不認得的項](../../../protocol/examples/daemon/mq_reply.unknown-inst.valid.json)；反例 [錯誤代碼不認得](../../../protocol/examples/daemon/mq_reply.stopped.invalid.json)、[信多了欄位](../../../protocol/examples/daemon/mq_reply.message-extra.invalid.json)、[信沒有 from_socket](../../../protocol/examples/daemon/mq_reply.message-no-from-socket.invalid.json)；請求反例另有 [send 的 from_socket 是數字](../../../protocol/examples/daemon/mq_request.send-from-socket-number.invalid.json)〔第二十一批〕。〔第二十二批〕請求 [broadcast](../../../protocol/examples/daemon/mq_request.broadcast.valid.json)、[channel](../../../protocol/examples/daemon/mq_request.channel.valid.json)、[peek 帶 to](../../../protocol/examples/daemon/mq_request.peek-to.valid.json)；反例 [broadcast 是 false](../../../protocol/examples/daemon/mq_request.broadcast-false.invalid.json)、[channel 是空字串](../../../protocol/examples/daemon/mq_request.channel-empty.invalid.json)、[channel 沒有 msg](../../../protocol/examples/daemon/mq_request.channel-no-msg.invalid.json)、[send 與 broadcast 都有](../../../protocol/examples/daemon/mq_request.send-and-broadcast.invalid.json)、[take 的 to 是字串](../../../protocol/examples/daemon/mq_request.take-to-string.invalid.json)。回應 [沒人收](../../../protocol/examples/daemon/mq_reply.broadcast-none.valid.json)；反例 [信沒有 to](../../../protocol/examples/daemon/mq_reply.message-no-to.invalid.json)、[成功沒有 delivered](../../../protocol/examples/daemon/mq_reply.ok-no-delivered.invalid.json)。

### 環境變數

掛了訊息模組時，daemon 每次開 `aos-exec` 都在環境裡放（總表 [C-10](../../conventions.md)）：

| 變數 | 值 |
|---|---|
| `AOS_DAEMON_MQ_SOCKET` | 訊息 socket 的絕對路徑 |
| `AOS_DAEMON_INST` | 這一項的 inst 字面值（掛了控制或訊息任何一個就放，[P-121](control.md)） |

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

**結束碼**（[C-08](../../conventions.md)）：daemon 回 `ok:true` 回 0；其他一律回 1，stderr 一行 `<代碼>: <說明>`。

| 代碼 | 什麼時候 |
|---|---|
| `usage` | 沒給指令、指令名錯、不認得的旗標、`send` 的 `<收件 inst>`／`--all`／`--channel` 不是剛好一個、位置參數數目不對、`--channel` 後面沒接頻道名或給了兩次、`<JSON>` 不是 JSON、`take`／`peek` 給了位置參數（`--from` 前面的）、`take`／`peek` 帶 `--urgent`、`--socket`、`--all` 或 `--channel`、`--socket` 後面沒接路徑 |
| `no_daemon` | 沒給 `--socket`，也沒有 `AOS_DAEMON_MQ_SOCKET`（或是空字串） |
| `no_inst` | `take`、`peek` 時沒有 `AOS_DAEMON_INST`（或是空字串） |
| `connect` | 連不上 socket |
| `unknown_inst`、`bad_request` | daemon 回的錯，原樣轉出；說明是 daemon 回的 `detail` |

依據：使用者 2026-10-01 第十二批（M1～M4 照 plan 建議：`from` 自動填不核對、`AOS_DAEMON_INST` 掛任一個就放、取信不限自己、`aos-mq send`／`take`）；第十四批（取信只能取自己的信箱、可用 `--from` 只取某個寄件人的，推翻 M3）；第十五批（daemon 不核對取信的人、加 `peek`、`--from` 收多個、不接＝null、跨 daemon 不管）；第二十一批（跨 daemon 用 socket 路徑當前綴：`send --socket`、`from_socket`；peers 先不做）；第二十二批（廣播與頻道：「ab都做」「好，如你所建議」）；plan m3m 模組四。
