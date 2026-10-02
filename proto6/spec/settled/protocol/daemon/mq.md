# daemon 協議：訊息門與 aos-mq

← [daemon 協議](README.md)｜行為：[B-645](../../daemon/mq.md)｜[慣例](../../conventions.md)

## P-125：訊息 socket、環境變數與 aos-mq

多扇門：一扇門一個 socket。schema：`proto6/spec/protocol/schemas/daemon-mq.schema.json`（請求與回應分開驗）；範例：`proto6/spec/protocol/examples/daemon/mq_*`、`core-config.mq*`。程式：`aos_daemon_mq.py`、`aos_mq.py`。

### 設定

```json
{
  "modules": {"mq": {"SOCKET_1": "./mq-1.sock", "ALERTS": "/srv/aos/doors/alerts/s"}},
  "insts": {"inst-1": {"mq": ["SOCKET_1", "ALERTS"]}, "inst-2": {}}
}
```

| 位置 | 型別 | 意思 |
|---|---|---|
| `modules.mq` | 物件，至少一鍵 | 鍵＝門名，只能 `[A-Za-z0-9_]+`；值＝socket 路徑，非空字串，相對以起點為準 |
| 每項的 `mq` | 字串陣列，可省 | 訂哪幾扇門；省或 `[]`＝不訂；重複門名算一次 |

設定錯（開起來回 1、`aos-daemon: config: <說明>`；重讀時整份不套用）：`modules.mq` 不是物件或空、門名不合、值不是非空字串、兩扇門同路徑、跟控制 socket 同路徑、某項 `mq` 不是字串陣列或寫了沒有的門。重讀時每項的 `mq` 照開起來時的門核。沒掛模組時每項 `mq` 忽略。

### 請求（每扇門一樣）

一條連線一問一答、一行 JSON、1 秒內送完、不驗身分、socket 檔 chmod 666（權限看所在資料夾）。

```json
{"send":{"hi":1}}
{"send":null}
{"take":"b.json"}
{"peek":"b.json"}
```

| 欄位 | 型別 | 意思 |
|---|---|---|
| `send` | 任何 JSON 值（含 `null`） | 信本身，原樣放進訂了「這扇門」的每一項的信箱並叫醒它們 |
| `take`／`peek` | 字串＝inst 字面值 | 取走／看該項全部的信（連哪扇門都一樣）；`peek` 不取走 |

三個裡剛好出現一個；陌生欄位照收不理。socket 不驗身分，`take`／`peek` 指名任何一項都取得到（「只能取自己的」由 `aos-mq` 做）。跨 daemon 寄信就是直接連對方的門送 `send`，daemon 不轉送。

### 回應

| 情況 | 回應 |
|---|---|
| `send` 成功（沒人訂也算；寄給已停的項：信收下、不跑） | `{"ok":true}` |
| `take`／`peek` 成功 | `{"ok":true,"messages":[<信>,…]}`，先寄的在前，沒信是 `[]` |
| 失敗 | `{"ok":false,"error":"<代碼>","detail":"<字串>"}` |

| `error` | 什麼時候 |
|---|---|
| `unknown_inst` | `take`／`peek` 指名的 inst 不在 `insts`（`send` 不會） |
| `bad_request` | 不是 JSON／物件、`send`／`take`／`peek` 不是剛好一個、`take`／`peek` 的值不是字串、沒送完一行 |

### 環境變數

| 變數 | 值 |
|---|---|
| `AOS_DAEMON_MQ_<門名>` | **每一扇門**一個，值是該門絕對路徑，不管該項有沒有訂都給（`SOCKET_1` → `AOS_DAEMON_MQ_SOCKET_1`） |
| `AOS_DAEMON_INST` | 該項 inst 字面值（掛了控制或訊息任一個就放） |

### aos-mq

```sh
aos-mq send <socket 路徑> <JSON|->
aos-mq take <socket 路徑>
aos-mq peek <socket 路徑>
```

```sh
aos-mq send "$AOS_DAEMON_MQ_ALERTS" '{"level":"warn","text":"disk 90%"}'
aos-mq take "$AOS_DAEMON_MQ_SOCKET_1"
aos-mq send /srv/aos/B/doors/team-a/s -  < reply.json
```

`send` 的 `<JSON>` 給 `-` 就從 stdin 讀；`take`／`peek` 不收 inst 參數，一律用 `AOS_DAEMON_INST`；`--` 開頭的旗標一律不收；參數個數要剛好。成功時 `send` 不印，`take`／`peek` 每封信一行 JSON 印到 stdout。詳見 `aos-mq --help` 或 `aos_mq.py`。

結束碼：0＝daemon 回 `ok:true`；1＝其他，stderr 一行 `<代碼>: <說明>`，代碼為 `usage`（含 JSON 不合法）、`no_inst`、`connect`，或 daemon 回的 `unknown_inst`／`bad_request`。
