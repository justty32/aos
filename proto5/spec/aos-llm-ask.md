# aos-llm-ask：把一個 agent 資料夾問模型一次（程式規範，**草稿**）

← [proto5 README](../README.md)｜資料夾長什麼樣在 [agent.md](agent.md)；aos-agent 的 `think` 格會
import 這支做同一件事，見 [aos-agent.md](aos-agent.md)

> **這一版只管「問一次」**：讀 [agent.md](agent.md) 那套以 `info.json` 開頭的體系（`system`／
> `history`／`tools`／`engine`），組請求、打出去、印回話。`state.json`、記憶怎麼接、要不要跑
> 工具，這份都不管——那是 aos-agent 的事。不記修訂記錄。

一句話：**`aos-llm-ask [dir]` 讀 `dir` 這個 agent 資料夾，組一份請求問模型一次，把模型的回話印到
stdout，然後退出**——不寫任何檔，問完就完事。

## 1. 用法

```
aos-llm-ask [dir] [--dry-run]
```

- `dir` 留空＝`.`（跟 aos-exec、aos-agent 一樣）。
- `--dry-run`：不送出去，只印組好的請求（§4）。
- 沒有別的旗標、沒有子命令。

## 2. 讀什麼：照 [agent.md](agent.md)，但只碰用得到的幾格

讀驗規則整套照 [agent.md §2](agent.md#2-每個檔的形狀)：`info.json` 每一格解指示詞
（[directives.md](directives.md)）、`_metainfo._type` 要是 `llm_agent`（不是＝`NotAnAgent`）；
`system`／`history`／`tools` 指到的檔原樣讀、不解指示詞；`tools` 列的每份檔合併成一個陣列、送
模型前把每個元素所有 `_` 開頭的 key 拿掉。

這份只用得到 `info.json` 裡的四格：

| 格 | 用來幹嘛 |
|---|---|
| `system` | 組 `messages` 的第一則（§3） |
| `history` | 組 `messages` 剩下的部分（§3） |
| `tools` | 合併成請求的 `tools`（§3） |
| `engine` | 打去哪（`endpoint`／`model`／`params`／`api_key`／`timeout_ms`，§3） |

**`state.json` 不看**：不讀、不驗、不管它有沒有這個檔、寫了什麼。這份規範不是走 agent 的四格
之一，是被 `think` 格拿去用的一支工具，跟 `state` 沒關係。

讀驗錯誤（缺檔、JSON 壞、型別不對、指示詞解不開、工具重名…）代號跟 [agent.md §4](agent.md#4-錯誤代號讀驗階段)
一樣（`StateInvalid` 除外，因為不碰 `state.json`），退出碼 1（§6）。

## 3. 請求長什麼樣

組一份 OpenAI chat/completions 的請求 body：

```json
{
  "model": "qwen/qwen3-1.7b",
  "messages": [
    {"role": "system", "content": "你是個簡潔、會用工具的助手。"},
    {"role": "user", "content": "看看資料夾裡有什麼"}
  ],
  "tools": [
    {"type": "function", "function": {"name": "sh", "description": "…", "parameters": {"...": "..."}}}
  ],
  "temperature": 0.2
}
```

- `model`：`engine.model` 原樣。
- `messages`：`system.json` 的 `content` **有內容才加一則** `{"role": "system", "content": …}`
  放最前面（`content` 是空字串就不加，照 [agent.md §2.2](agent.md#22-人格system-指到的檔慣例放-promptssystemjson)）；
  後面接 `history.json` 那個陣列，**原樣接上去**，一則不動。
- `tools`：`info.json` 的 `tools` 列到的每份檔（各是一個陣列）**接成一個**、照檔的順序；送出去
  之前把每個元素**所有 `_` 開頭的 key 拿掉**（`_meta` 首當其衝）。**合併後是空陣列就不送 `tools`
  這個欄位**（跟沒有工具是兩回事：沒有工具就別讓模型以為它能叫工具）。
- 其餘欄位：`engine.params`（物件，沒寫就是 `{}`）**原樣併進 body**，跟 `model`／`messages`／
  `tools` 同一層（例如 `params: {"temperature": 0.2}` 就會多一個 `"temperature": 0.2`）。
  `params` 裡若也寫了 `model`／`messages`／`tools`／`stream`，**忽略**——這四個是這支程式自己決定的。
- `api_key`：**有值才送** `Authorization: Bearer <api_key>` 這個 HTTP header；沒寫就不送這個
  header（不是送空字串）。
- URL：`engine.endpoint` 去掉結尾多餘的 `/` 之後接上 `/chat/completions`（`http://x/v1` 跟
  `http://x/v1/` 都變 `http://x/v1/chat/completions`）。
- `timeout_ms`：這次 HTTP 呼叫等多久，沒寫用 `engine` 的預設（120000，見 [agent.md §2.5](agent.md#25-engine在-infojson-裡用什麼想)）。

## 4. `--dry-run`：不送出去，只印請求

加了 `--dry-run` 就**不打 HTTP**，把 §3 組好的請求 body 印成一行 JSON 到 stdout，然後退出碼 0。
沒有模型也能測「組得對不對」；讀驗照樣先做，讀驗錯誤照樣是退出碼 1（§6），不會因為多了
`--dry-run` 就跳過。

```sh
aos-llm-ask ./agent-bob --dry-run
# {"model":"qwen/qwen3-1.7b","messages":[...],"tools":[...],"temperature":0.2}
```

## 5. 輸出：一行 JSON，就是那則 assistant 訊息

沒給 `--dry-run`，成功的話 stdout **只印一行**：`choices[0].message` 這個 JSON 物件，原樣印出來
（有 `tool_calls` 就帶著 `tool_calls`，`content` 是 `null` 就是 `null`）。

```sh
aos-llm-ask ./agent-bob
# {"role":"assistant","content":"裡面有 state.json、prompts、tools…"}
```

**別的東西一律不印到 stdout**——不管是 `--dry-run` 那行還是 message 那行，一次只印一行、只印
那一件事；讀驗錯誤、引擎失敗、進度訊息都是 stderr 的事（§6）。

## 6. 退出碼與 stderr

| 碼 | 什麼時候 |
|---|---|
| 0 | 成功：印了請求（`--dry-run`）或印了 message |
| 1 | 讀驗錯誤（§2）：stderr 一行 `aos-llm-ask: <代號>: <白話>` |
| 2 | 用法錯：旗標不認得、`dir` 不存在 |
| **3** | **引擎失敗**：連不上、HTTP 回非 2xx、逾時、回來的不是合法 JSON、或沒有 `choices[0].message`；stderr 一行 `aos-llm-ask: engine: <白話>` |

1 跟 3 分開：1 是「東西根本沒送出去，設定就壞了」（跟 aos-exec 的 125、aos-agent 的 1 是同一種
精神）；3 是「送出去了，但這次網路或模型本身出包」——看 stderr 就知道要去修設定檔還是等一下
再試。

## 7. 給程式用

aos-agent 的 `think` 格 import 這支的函式庫做同一件事，不是開子進程跑 `aos-llm-ask`（跟
[aos-agent.md §4](aos-agent.md#4-跑一個工具) 說工具要 import aos_exec／aos_inst 同一個理由）。
大概的簽名（實作時可調）：

```python
import aos_llm_ask

body = aos_llm_ask.build_request(dir)   # 讀驗 + 組請求，回 §3 那個 dict；不碰網路
message = aos_llm_ask.ask(dir)          # build_request 再打 engine，回 choices[0].message 那個 dict
```

- `build_request(dir)` 對應 `--dry-run`：只做讀驗與組請求，不打 HTTP，讀驗錯誤丟跟命令列同一種
  例外（含代號）。
- `ask(dir)` 對應沒給 `--dry-run` 的路：多做一次 HTTP 呼叫，引擎失敗丟另一種例外（§6 的「3」那
  一類），成功回 `message`。
- 兩個函式都不寫檔、不碰 `state.json`、不跑工具；接不接進記憶、要不要跑 `tool_calls`，都是呼叫
  它的人（aos-agent）自己做。

## 8. 沒管的事

- **不寫記憶、不寫 `state.json`**：問完就完事，記憶怎麼接是 aos-agent 的事。
- **不跑工具**：模型回的 `tool_calls` 原樣印出來，誰跑、怎麼跑不在這份規範。
- **不重試**：引擎失敗一次就是失敗一次（退出碼 3），要不要重試是呼叫的人決定。
- **串流不支援**：這一版永遠 `stream` 不送（或送 `false`），當場等整段回來。

## 我自己選的、使用者可以推翻的

1. `--dry-run` 這個旗標：沒有模型也想測「組得對不對」，所以留一條不碰網路的路。
2. 退出碼 3 專門留給引擎失敗，跟讀驗錯誤（1）分開：一個是「設定壞了」、一個是「這次連線／模型
   出包」，看 stderr 的人不用猜。
3. `params` 撞到 `model`／`messages`／`tools`／`stream` 就忽略、`endpoint` 結尾 `/` 自動去掉——兩條小規則
   是為了少一種寫壞的方式。
4. stdout 只印 `choices[0].message` 那一行：不印整個 HTTP response、不印 debug 訊息，讓這支
   程式的輸出好被別的程式接（管線、`aos-agent` 之後 import 它）。
