# daemon 協議：訊息 socket 與 aos-mq

← [daemon 協議](README.md)｜[共用約定](../../../protocol/README.md)｜行為正本：[B-645](../../daemon/mq.md)｜[慣例](../../conventions.md)

本篇只有 P-125，只寫格式。信箱、急件叫醒的規則以 [B-645](../../daemon/mq.md) 為正本。

依據：[verdicts 11 篇末「2026-10-01 第十二批：cgroup 與帳號」](../../../../notes/verdicts/11-tick-as-unit.md#2026-10-01-第十二批cgroup-與帳號)、[第十四批：aos-mq 取信](../../../../notes/verdicts/11-tick-as-unit.md#2026-10-01-第十四批aos-mq-取信)、[plan m3m 模組四](../../../../plan/m3m-daemon-modules.md#模組四訊息modulesmq)；現行程式 [訊息與 aos-mq](../../../../src/py/README.md#訊息與-aos-mqm3m-模組四)（有出入以程式為準）。

## P-125．訊息 socket、環境變數與 aos-mq〔使用者 2026-10-01 第十二批；欄位名照現行程式〕

### 設定

daemon 設定檔（[P-120](core.md)）頂層 `modules` 裡寫：

```json
{"modules": {"mq": {"socket": "./aos-mq.sock"}}}
```

`socket` 必填，字串；相對以起點為準，daemon 算成絕對路徑。範例：[掛控制與訊息](../../../protocol/examples/daemon/core-config.mq.valid.json)；反例：[沒寫 socket](../../../protocol/examples/daemon/core-config.mq-no-socket.invalid.json)。

### socket 上的一來一回

跟控制 socket 一樣（[P-121](control.md)「socket 上的一來一回」）：Unix stream socket、一條連線只問一次、一行 JSON（UTF-8、LF 結尾）來回、每條連線 1 秒內要送完那一行、一條出錯不影響下一條、不驗身分。socket 檔的開與刪也照 P-121。

### 請求

```json
{"send":"b.json","msg":{"hi":1},"from":"a.json","urgent":true}
{"send":"b.json","msg":null}
{"take":"b.json"}
{"take":"b.json","from":["a.json","c.json"]}
{"peek":"b.json","from":[null]}
```

| 欄位 | 型別 | 意思 |
|---|---|---|
| `send`／`take`／`peek` | 字串 | 三個裡剛好出現一個；值是 inst 字面值（`send` 是收件人，`take`、`peek` 是哪一項的信箱），跟設定檔 `insts` 的鍵逐字比對 |
| `msg` | 任何 JSON 值 | `send` 必填（可以是 `null`）；daemon 不看內容 |
| `from` | `send`：字串或 null，可省，預設 null；`take`、`peek`：非空陣列，元素是字串或 null，可省 | `send`：寄件 inst，原樣存、不核對。`take`、`peek`〔第十四批；第十五批改陣列〕：只要寄件人在陣列裡的信（`null`＝寄件人是 null 的信），其他照順序留著；省略＝全部 |
| `urgent` | 布林，可省，預設 false | 只有 `send` 看；放進信箱後叫醒收件那一項 |

不認得的欄位照收不理（同 P-121）；`take`、`peek` 帶了 `msg`、`urgent` 也忽略。socket 不驗身分：`take`、`peek` 指名任何一項都取得到（「只能取／看自己」是 `aos-mq` 那一側做的，[B-645](../../daemon/mq.md)；使用者 2026-10-01 第十五批 1.a：照 POC「能連就能做」，daemon 不核對）。

### 回應

| 情況 | 回應 |
|---|---|
| `send` 成功（含急件寄給已停的項：信收下、不跑） | `{"ok":true}` |
| `take`、`peek` 成功 | `{"ok":true,"messages":[{"from":…,"msg":…},…]}`，先寄的在前；沒信是 `[]`。`peek` 不把信從信箱拿走 |
| 失敗 | `{"ok":false,"error":"<代碼>","detail":"<字串>"}` |

| `error` | 什麼時候 | `detail` |
|---|---|---|
| `unknown_inst` | 指名的 inst 不在 `insts` 裡 | 那個 inst 字面值 |
| `bad_request` | 不是 JSON、不是物件、`send`／`take`／`peek` 不是剛好一個、值不是字串、`send` 沒有 `msg`、`send` 的 `from` 不是字串或 null、`take`／`peek` 的 `from` 不是非空陣列或元素不是字串或 null、`urgent` 不是布林、沒送完一行 | 白話說明 |

回應一律是不帶多餘空白的一行 JSON，非 ASCII 字照原樣輸出。

schema：[daemon-mq](../../../protocol/schemas/daemon-mq.schema.json)，請求與回應分開驗（請求照 `$defs/Request`、回應照 `$defs/Reply`，同 P-121）。範例：請求 [send 全欄位](../../../protocol/examples/daemon/mq_request.send.valid.json)、[send 最少](../../../protocol/examples/daemon/mq_request.send-minimal.valid.json)、[take](../../../protocol/examples/daemon/mq_request.take.valid.json)、[take 帶 from](../../../protocol/examples/daemon/mq_request.take-from.valid.json)、[peek 帶 from（含 null）](../../../protocol/examples/daemon/mq_request.peek-from.valid.json)；反例 [take 的 from 是數字](../../../protocol/examples/daemon/mq_request.take-from-number.invalid.json)、[from 是空陣列](../../../protocol/examples/daemon/mq_request.take-from-empty.invalid.json)、[from 是字串不是陣列](../../../protocol/examples/daemon/mq_request.peek-from-string.invalid.json)、[send 沒有 msg](../../../protocol/examples/daemon/mq_request.send-no-msg.invalid.json)、[兩個都有](../../../protocol/examples/daemon/mq_request.both.invalid.json)、[urgent 不是布林](../../../protocol/examples/daemon/mq_request.urgent-not-bool.invalid.json)。回應 [成功](../../../protocol/examples/daemon/mq_reply.ok.valid.json)、[取到信](../../../protocol/examples/daemon/mq_reply.taken.valid.json)、[不認得的項](../../../protocol/examples/daemon/mq_reply.unknown-inst.valid.json)；反例 [錯誤代碼不認得](../../../protocol/examples/daemon/mq_reply.stopped.invalid.json)、[信多了欄位](../../../protocol/examples/daemon/mq_reply.message-extra.invalid.json)。

### 環境變數

掛了訊息模組時，daemon 每次開 `aos-exec` 都在環境裡放（總表 [C-10](../../conventions.md)）：

| 變數 | 值 |
|---|---|
| `AOS_DAEMON_MQ_SOCKET` | 訊息 socket 的絕對路徑 |
| `AOS_DAEMON_INST` | 這一項的 inst 字面值（掛了控制或訊息任何一個就放，[P-121](control.md)） |

### aos-mq

```sh
aos-mq send [--urgent] <收件 inst> <JSON|->
aos-mq take [--from [<寄件 inst>…]]…
aos-mq peek [--from [<寄件 inst>…]]…
```

給任務用；人在 shell 手打怎麼看信，aos 不管（第十五批）。

- 第一個參數是指令名；只有 `--` 開頭的算旗標（`-` 是從 stdin 讀、`-5` 是 JSON 負數），只有 `send` 收 `--urgent`、只有 `take`、`peek` 收 `--from`，可以放在後面任何位置。`--from` 後面接的參數到下一個 `--` 開頭的參數為止都是寄件 inst（`-x` 這種一個 `-` 開頭的也算寄件人）；一個都不接＝`null`；可以重複寫，全部疊起來送成一個 `from` 陣列〔第十五批〕。
- `send` 要剛好兩個位置參數；`from` 填 `AOS_DAEMON_INST`（沒有或空字串就 `null`）。`take`、`peek` 不收位置參數，只對 `AOS_DAEMON_INST` 那一項的信箱〔第十四批〕；給了 `--from` 就在請求帶 `from` 陣列。
- socket 只從 `AOS_DAEMON_MQ_SOCKET` 拿。
- 成功：`take`、`peek` 每封信一行 `{"from":…,"msg":…}`（不帶多餘空白）印到 stdout，沒信什麼都不印；`send` 不印。
- 不重試、不另設逾時。

**結束碼**（[C-08](../../conventions.md)）：daemon 回 `ok:true` 回 0；其他一律回 1，stderr 一行 `<代碼>: <說明>`。

| 代碼 | 什麼時候 |
|---|---|
| `usage` | 沒給指令、指令名錯、不認得的旗標、`send` 的位置參數不是兩個、`<JSON>` 不是 JSON、`take`／`peek` 給了位置參數（`--from` 前面的）、`take`／`peek` 帶 `--urgent` |
| `no_daemon` | 沒有 `AOS_DAEMON_MQ_SOCKET`（或是空字串） |
| `no_inst` | `take`、`peek` 時沒有 `AOS_DAEMON_INST`（或是空字串） |
| `connect` | 連不上 socket |
| `unknown_inst`、`bad_request` | daemon 回的錯，原樣轉出；說明是 daemon 回的 `detail` |

依據：使用者 2026-10-01 第十二批（M1～M4 照 plan 建議：`from` 自動填不核對、`AOS_DAEMON_INST` 掛任一個就放、取信不限自己、`aos-mq send`／`take`）；第十四批（取信只能取自己的信箱、可用 `--from` 只取某個寄件人的，推翻 M3）；第十五批（daemon 不核對取信的人、加 `peek`、`--from` 收多個、不接＝null、跨 daemon 不管）；plan m3m 模組四。
