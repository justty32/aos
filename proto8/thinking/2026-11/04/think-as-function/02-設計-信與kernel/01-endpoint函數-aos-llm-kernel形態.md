← [回入口 02-設計-信與kernel.md](../02-設計-信與kernel.md)｜段落：§ 4 endpoint 函數、§ 5 `aos-llm` 基礎工具、§ 6 kernel 當 loop／daemon、「包起來的」、跟現有 C++ kernel 的關係｜上一份：—｜下一份：—

## 4 endpoint 函數：`lib/base/llm_http/`

- lib 契約的資料夾程式（純標準庫 Python）：stdin `{"endpoint": {"url","model","key"?,"body"?}, "request": {...}}` → 送出的 body＝`endpoint.body` 疊上 `request`（信裡寫的蓋過預設）、再補 `model`（`request.model` 優先）→ POST `{url}/chat/completions`（`key` 有才帶 Bearer）→ stdout 一行 `{"message": 剪過的 choices[0].message, "usage", "model"}`、退 0。錯：stderr 與 stdout 各一行 `llm_http: 代號 原因`、退 1：`ArgumentsBad`、`EndpointFailed`、`ReplyBad`。沒有自己的逾時旗標（包它的單子守）。
- **假腦也是一個 endpoint 函數**：`lib/base/llm_fake/`（同一個契約，不碰網路：有工具就先叫第一個、再答一句「FAKE ANSWER to: …」）；`endpoints` 表登記一組 `"fake": {"exec": "../../lib/base/llm_fake"}`、信寫 `"endpoint": "fake"`（或設成預設）就是假腦。沒有「URL 沒設＝假腦」這種暗規則（C-56）。
- 它就是個工具：agent 也可以直接 `tools.json` 登記它、不經 kernel（沒額度、沒排隊，自己承擔）；要換家＝再寫一個資料夾、`exec` 換指。

## 5 `aos-llm`：寄單／收回信的基礎工具

`impls/aos-llm/`（C++，由 aos-llm-send 改名；連 kernel 公開標頭與 aos-post 庫；旗標在位置參數前，P-44）。改定義裡的腦設定不歸它（見 [03](../03-呼叫端.md) § 4）。

| 子命令 | 做什麼 | stdout／結束碼 |
|---|---|---|
| `aos-llm send [--priority P] --reply-to BOX < body.json` | 寄一封請求信進 `$AOS_KERNEL`，馬上回（不建 `sender.flock`；BOX 不在先建好） | 印信件名稱；0。`--reply-to` 必給（沒給＝`ArgumentsBad`） |
| `aos-llm recv BOX 信件名稱` | 到 BOX 的 `new/` 找 `in_reply_to`＝那個名字的回信（別人的不碰），認領、印 `body.message`、收掉 | 到了：一行 JSON、0；沒到：10；回信是 `error`：stderr `aos-llm: 代號 原因`、收掉、1；壞信：`ReplyBad`、1 |
| `aos-llm ask [--priority P] < body.json` | 同步：寄（回信信箱＝`$AOS_KERNEL/reply/`、建 `sender.flock`）、等（20 ms 輪詢、訊號＝撤信）、印 `body.message` | 0；`error` 回信＝stderr 一行、1 |
| `aos-llm regret 信件名稱` | 撤回還在 `new/` 的請求信（`aos-post regret`） | 0；已被認領＝`RegretFailed`、1 |

- stdin＝整份信 body（`{"endpoint"?, "request", "priority"?}`）；`--priority` 有給就蓋 body 的。不是物件或沒 `request.messages`＝`RequestBad`。`$AOS_KERNEL` 沒設＝`KernelMissing`。
- 跟 aos-post 的分工：aos-post 管一封信怎麼寄、怎麼認領；aos-llm 只多知道請求信的 body 長怎樣、回信怎麼認、錯怎麼印。agent 自己拿它們組。
- `aos-tools` 不動：它本來就是一份登記檔的 add／rm／ls／get／call、不認 agent。

## 6 kernel 當 loop、當 daemon 的 proc；「包起來的」

- **kernel＝一個資料夾程式** `demo/llm-kernel/`：`_entry`＝`["aos-loop", "loop.json"]`、`loop.json`＝`{"exec": {"argv": ["aos-llm-kernel", "kernel.json"]}, "interval_ms": 300}`（陣列形會被 aos-exec 當目標）、`kernel.json` 如 § 3。直接跑：`AOS_KERNEL=$PWD/.stack/mailbox aos-exec --ws . demo/llm-kernel`；當 daemon 的 proc：`aos-daemon-ctl add --name llm demo/llm-kernel` → 信箱在 `$AOS_DAEMON/procs/llm/mailbox/`，人把它 export 成 `AOS_KERNEL` 給 agent 用（或寫進 daemon 的環境讓所有 proc 繼承，N-63 ③）。
- **「包起來的」＝讀法 ②**（使用者 11-04 晚「我是希望走2」）：對外介面只有信箱＋`aos-llm`（寄請求、收回信）；kernel 裡面怎麼跑 endpoint 函數，呼叫端一概不知道（C-52）。呼叫端的契約只有 `$AOS_KERNEL`＋ § 1／§ 2 的信形狀。讀法 ①「端點呼叫包成 aos 函數由 aos-exec 跑」是裡面的做法，不是對外介面。
- **保留 C++ aos-llm-kernel、改它跑的東西**，不另寫 Python kernel：排隊、`slots`、`budget`、`recover`、`sweep`、`reply_to` 全留；排序依據是級數→deadline→等得久→先寄（沒有 `_metainfo` 兩條）。
- **串流不做**：request 寫 `stream: true`＝`RequestBad`。回信是一封信、一次到。以後要給人看即時字，是 endpoint 函數自己寫 `$AOS_STACK/stream.txt` 的事，介面不變。
