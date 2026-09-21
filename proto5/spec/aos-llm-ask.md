# aos-llm-ask：把一個 agent 資料夾問模型一次（程式規範，**草稿**）

← [proto5 README](../README.md)｜什麼是 agent 資料夾在 [agent.md](agent.md)；aos-agent 的 `think` 格會
import 這支做同一件事，見 [aos-agent.md](aos-agent.md)

> **這一版只管「問一次」**：讀以 `info.json` 開頭的體系（`system`／`history`／`tools`／`engine`，
> 形狀在 §2），組請求、打出去、印回話。`state.json`、記憶怎麼接、要不要跑
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

## 2. 讀什麼：`info.json` 的四格＋它們指到的檔

資料夾本身（`info.json` 的 `_metainfo`、`state.json`、指示詞解不解、共用的錯誤代號）照
[agent.md](agent.md)。這一節定的是 **`info.json` 裡 aos-llm-ask 用的四格**跟**它們指到的檔長什麼樣**：

```json
{
  "_metainfo": {"_type": "llm_agent", "_version": 1},
  "system":  "prompts/system.json",
  "history": "prompts/history.json",
  "tools":   ["tools/base.json", "tools/team.json"],
  "engine":  {"endpoint": "http://127.0.0.1:1234/v1", "model": "qwen/qwen3-1.7b"}
}
```

| 鍵 | 型別 | 沒寫時 | 意思 |
|---|---|---|---|
| `system` | 路徑字串 | `prompts/system.json` | 人格在哪個檔（§2.2），組 `messages` 的第一則 |
| `history` | 路徑字串 | `prompts/history.json` | 記憶在哪個檔（§2.3；那個檔是 agent 寫的），組 `messages` 剩下的部分 |
| `tools` | 路徑陣列 | `[]` | 用哪幾份工具檔（§2.4），所有檔的陣列**接成一個**、順序＝檔的順序，成為請求的 `tools` |
| `engine` | 物件 | **必填** | 打去哪（§2.5） |

- `system`／`history` 不是字串、`tools` 不是字串陣列、`engine` 不是物件 → `FieldTypeMismatch`。
- `info.json` 每一格解指示詞、指到的檔原樣讀——規則在 [agent.md §2](agent.md)。
- **`state.json` 不看**：不讀、不驗、不管它有沒有這個檔、寫了什麼。

讀驗錯誤（缺檔、JSON 壞、型別不對、指示詞解不開、工具重名…）＝退出碼 1（§6）；共用代號在
[agent.md §5](agent.md)，這支自己的三個（`MessageInvalid`／`ToolInvalid`／`EngineInvalid`）在下面各節。

### 2.2 人格（`system` 指到的檔，慣例放 `prompts/system.json`）

```json
{"content": "你是個簡潔、會用工具的助手。"}
```

- `content`：字串，就是 system prompt 本文；**檔不存在＝空字串**（不送 system 訊息）；存在但讀不到／壞掉＝`ReadFailed`／`JsonSyntax`。
- **原樣讀、不解指示詞**（[agent.md §2](agent.md)）：`content` 就是字面，裡面的 `${x}`、`$` 開頭的東西都不會被動。

### 2.3 記憶（`history` 指到的檔，慣例放 `prompts/history.json`；agent 寫）

一個陣列，一則就是 OpenAI chat 的一則訊息：

```json
[
  {"role": "user",      "content": "看看資料夾裡有什麼"},
  {"role": "assistant", "content": null, "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "sh", "arguments": "{\"cmd\":\"ls\"}"}}]},
  {"role": "tool",      "tool_call_id": "c1", "content": "state.json\nprompts\ntools\n"},
  {"role": "assistant", "content": "裡面有 state.json、prompts、tools…"}
]
```

- `role` 只認 `user`／`assistant`／`tool`；`system` 不放這裡（每次組請求時從 `system.json` 補在最前面）。
- `user`／`tool` 的 `content` 要是字串；`tool` 一定要有 `tool_call_id`；`assistant` 至少有 `content` 或 `tool_calls` 其中一個。不合 → `MessageInvalid`。
- **檔不存在＝`[]`**；存在但讀不到／壞掉＝`ReadFailed`／`JsonSyntax`。
- **原樣讀寫、不解指示詞**（[agent.md §2](agent.md)）：模型回的 JSON 裡有 `$` 開頭的 key 也不會被誤認。
- 整份讀、整份寫；記憶長了怎麼辦之後再說（先跟 proto4-7 一樣）。

### 2.4 工具檔（`tools` 指到的檔，慣例放 `tools/`）：OpenAI tools 陣列 ＋ `_meta`

一份工具檔就是**一個 OpenAI chat/completions 的 `tools` 陣列**，一個元素一個工具、形狀照 OpenAI
原樣；唯一的修改是每個元素多一個 **`_meta`**，說「這個工具真的被叫到時怎麼跑」——內容就是**一份
posix inst**（[inst-posix.md](inst-posix.md) 整體形狀）：

```json
[
  {
    "type": "function",
    "function": {
      "name": "sh",
      "description": "在 agent 資料夾執行一句 shell 指令",
      "parameters": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}
    },
    "_meta": {"argv": ["tools/bin/sh-tool"], "stderr": "tools/log/sh.err"}
  }
]
```

- `tools` 列到的檔**一定要在**：不存在＝`ReadFailed`（跟人格、記憶不同——那兩個沒檔有預設，工具檔是明列的）。
- **合併**：`info.json` 的 `tools` 列的每份檔各是一個陣列，agent 把它們**接成一個陣列**（照檔的順序）；
  送給模型之前把每個元素**所有 `_` 開頭的 key 拿掉**（`_meta`、`_note`…），剩下的原樣送——所以想加
  註解就用 `_` 開頭，不會漏給模型。
- `_meta`：**必填**，一份 posix inst（`_metainfo` 可省＝posix v1）。缺了、或不是物件 → `ToolInvalid`。
- 合併後 `function.name` 同名 → `ToolInvalid`（不默默蓋掉，寫錯一眼看得到）。
- 元素缺 `type`／`function`／`function.name` → `ToolInvalid`；`function` 裡其他東西（`description`、
  `parameters`、`strict`…）本文不驗，原樣送模型。
- **工具檔原樣讀、不解指示詞**（[agent.md §2](agent.md)）；`_meta` 裡的指示詞是跑的時候由 inst 那套解。

`_meta` 這支程式**只驗不跑**（是物件、沒寫 `stdin`／`stdout`——寫了＝`ToolInvalid`，因為跑的時候參數走
stdin、結果走 stdout）；真的跑是 [aos-agent.md](aos-agent.md) 的事。要關掉一個工具就從 `info.json` 的
`tools` 拿掉那份檔、或從工具檔裡刪掉。

### 2.5 `engine`（在 `info.json` 裡）：用什麼想

這一版只有一種引擎：OpenAI 相容的 `chat/completions`。這裡定欄位；請求怎麼組、怎麼打、回來怎麼拿
在 §3～§5。

```json
"engine": {"endpoint": "http://127.0.0.1:1234/v1", "model": "qwen/qwen3-1.7b",
           "params": {"temperature": 0.2}, "api_key": {"$env": "LMSTUDIO_KEY"}, "timeout_ms": 120000}
```

| 鍵 | 型別 | 沒寫時 | 意思 |
|---|---|---|---|
| `endpoint` | 字串 | **必填** | base URL，agent 自己接 `/chat/completions` |
| `model` | 字串 | **必填** | 送出去的 `model` |
| `params` | 物件 | `{}` | 原樣併進請求 body（`temperature`、`max_tokens`…） |
| `api_key` | 字串 | 不送 Authorization | 有值才送 `Authorization: Bearer`；不想寫進檔就 `{"$env": "NAME"}`，變數不在＝`EnvironmentVariableMissing`（設定壞就不跑，不降級） |
| `timeout_ms` | 整數 | `120000` | HTTP 等多久 |

- 必填欄位缺、型別不對 → `EngineInvalid`。
- `engine` 整格在 `info.json` 裡，所以跟別格一樣吃指示詞：整包 `{"$ref": "engines/lmstudio.json"}`
  從別的檔拿也行。

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
  放最前面（`content` 是空字串就不加，照 §2.2）；
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
- `timeout_ms`：這次 HTTP 呼叫等多久，沒寫用 `engine` 的預設（120000，見 §2.5）。

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
