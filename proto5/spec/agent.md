# agent 資料夾規範（第 1 版，**草稿**）

← [proto5 README](../README.md)｜跑工具與引擎靠 [inst-posix.md](inst-posix.md)；`info.json` 吃指示詞（[directives.md](directives.md)），其他檔原樣讀；程式怎麼用這些檔見 [aos-llm-ask.md](aos-llm-ask.md)／[aos-agent.md](aos-agent.md)

> **這是草稿，還在跟使用者一步一步改**；不記修訂記錄。原則（使用者定的）：**先規劃檔案架構、
> 分配好每個檔在幹嘛，指示詞是輔助**。所以規範裡寫的都是普通的路徑字串與字面值；人寫的那一份
> 設定檔（`info.json`）每一格都吃指示詞，**其他檔（狀態、人格、記憶、工具）原樣讀、不解**
> （規則在 §2.0）。
>
> 這份**只講資料夾跟檔案長什麼樣**；程式拿這些檔做什麼，各自的規範講：問模型一次＝
> [aos-llm-ask.md](aos-llm-ask.md)，走一格（狀態機、跑工具）＝[aos-agent.md](aos-agent.md)。

一句話：**一個 agent 就是一個資料夾**，`info.json` 是它的總表（人寫）——這是 agent、人格跟記憶
在哪兩個檔、用哪幾份工具檔、用什麼想；`state.json` 只記走到哪（agent 寫）。bot 模型的五塊
（system prompt、history、tools、thinking engine、agent state）全在這兩份裡或由 `info.json` 指出去。

---

## 1. 資料夾長什麼樣

```
agent-bob/
  info.json            總表（人寫）：_metainfo ＋ system／history／tools 三個指向 ＋ engine
  state.json           走到哪（agent 寫）：只有 state
  prompts/
    system.json        人格（system prompt）
    history.json       記憶（對話史，agent 寫）
  tools/
    base.json          一份工具檔＝一個 OpenAI tools 陣列（每個多一個 _meta 說怎麼跑）
    team.json
```

- 只有 `info.json` 是**認出「這是 agent 資料夾」**的依據（有它、而且 `_metainfo._type` 是 `llm_agent`）。
  `_metainfo` 也吃指示詞，所以「認不認」要先解完才知道；解不開就是指示詞的錯，不是 `NotAnAgent`。
- 檔案裡寫的路徑，**一律相對於 agent 資料夾**（不是相對於寫它的那個檔）；絕對路徑照字面。
- **誰寫誰**：人寫 `info.json`、`prompts/system.json`、`tools/*`；agent 只寫 `state.json` 跟
  `prompts/history.json`。人的檔跟 agent 的檔分開，人的設定永遠不會被程式改掉。
- agent 寫檔一律先寫 `.tmp` 再 rename，別人永遠不會讀到寫一半的檔。
- 每個檔的頂層都是嚴格的物件或陣列（各節有寫）；**不認得的 key 一律忽略**。
- `prompts/`、`tools/` 這兩個資料夾名只是慣例，`info.json` 裡指到哪就是哪；放哪都行。
- 指示詞：`info.json` 解；**其他檔不解**，規則在 §2.0。

## 2. 每個檔的形狀

### 2.0 指示詞：`info.json` 解、其他檔不解

分兩種：

| 檔 | 解不解 | 為什麼 |
|---|---|---|
| `info.json` | **每一格都解**（含 `_metainfo`、`engine`） | 這是人寫的設定，寫的人想 `$env`／`$fmt`／`$ref` 就用 |
| `state.json`、`system`／`history`／`tools` 指到的檔 | **整份不解，原樣讀** | `state.json` 是 agent 自己寫的、只有一格；其他是「內容」：人格文字、模型吐出來的對話、工具的 schema 與 inst。內容裡什麼 `$` 都可能有，不能被當指示詞 |

解的那一份，規則照 [directives.md](directives.md)：

- **每一格都能放**：頂層整份、每個欄位、陣列的每個元素、物件的每個值；先解再驗型別。
  **`_metainfo` 也解**（這點跟 inst 不同：inst 的 `_metainfo` 不解）。
- **中心路徑（`$ref` 找檔的地方）＝agent 資料夾**。
- **`$ref:""`＝這個值所在的那份檔**；位置＝實體路徑（`info.json` 的 `/tools/0`…），相對 `$at`
  照 directives.md 3.2 算。
- **`$env` 讀的是 aos-agent 自己的環境**。
- 解錯了（`UnknownDirective`、`ReferenceCycle`…）＝讀驗錯誤，代號照 directives.md §6，退出碼 1。

不解的那些：

- `system`／`history`／`tools` 的值（路徑）本身在 `info.json` 裡，**那一格會解**（例如
  `"history": {"$env": "BOB_HISTORY"}`）；解出路徑之後，**讀進來的東西不解**。
- 工具的 `_meta` 是一份 inst，它裡面的指示詞是**跑工具的時候**由 inst 那套（aos-exec／aos_inst，
  base＝agent 資料夾）解的，不是 agent 讀工具檔時解。
- agent 寫的檔（`state.json`、`history` 指到的檔）都是原樣讀寫，跟 `info.json` 沒關係；`info.json`
  agent 永遠不寫，所以人寫的 `$ref` 不會被展開後的值蓋掉。

### 2.1 `info.json`：總表（人寫）

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
| `_metainfo` | 物件 | **必填** | `_type` 只認 `"llm_agent"`、`_version` 只認整數 `1`；規則同 [inst-posix.md §1](inst-posix.md)。跟 inst 不同的是必填：這是新格式、沒有舊檔要相容，而且這就是「這是 agent 資料夾」的記號 |
| `system` | 路徑字串 | `prompts/system.json` | 人格在哪個檔（§2.2） |
| `history` | 路徑字串 | `prompts/history.json` | 記憶在哪個檔（§2.3；那個檔是 agent 寫的） |
| `tools` | 路徑陣列 | `[]` | 用哪幾份工具檔（§2.4），所有檔的陣列**接成一個**，順序＝檔的順序 |
| `engine` | 物件 | **必填** | 用什麼想（§2.5） |

- `system`／`history` 不是字串、`tools` 不是字串陣列、`engine` 不是物件 → `FieldTypeMismatch`。

### 2.1.1 `state.json`：走到哪（agent 寫）

```json
{"state": "idle"}
```

- `state`：`idle`／`think`／`wait`／`act` 之一（四格各做什麼是 [aos-agent.md](aos-agent.md) 的事）。就這一個 key。
- **檔不存在＝`{"state": "idle"}`**，agent 第一次動就會把它寫出來；存在但壞掉＝`ReadFailed`／`JsonSyntax`。
- 原樣讀寫、不解指示詞；`state` 不是四格之一 → `StateInvalid`。

### 2.2 人格（`system` 指到的檔，慣例放 `prompts/system.json`）

```json
{"content": "你是個簡潔、會用工具的助手。"}
```

- `content`：字串，就是 system prompt 本文；**檔不存在＝空字串**（不送 system 訊息）；存在但讀不到／壞掉＝`ReadFailed`／`JsonSyntax`。
- **原樣讀、不解指示詞**（§2.0）：`content` 就是字面，裡面的 `${x}`、`$` 開頭的東西都不會被動。

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
- **原樣讀寫、不解指示詞**（§2.0）：模型回的 JSON 裡有 `$` 開頭的 key 也不會被誤認。
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
- **工具檔原樣讀、不解指示詞**（§2.0）；`_meta` 裡的指示詞是跑的時候由 inst 那套解。

`_meta` 是給 aos-agent 跑工具用的：參數走 stdin、結果走 stdout，所以 **`_meta` 裡不准寫 `stdin`／
`stdout`**（寫了＝`ToolInvalid`）；base＝agent 資料夾。怎麼跑、結果怎麼接回記憶，見
[aos-agent.md](aos-agent.md)。要關掉一個工具就從 `info.json` 的 `tools` 拿掉那份檔、或從工具檔裡刪掉。

### 2.5 `engine`（在 `info.json` 裡）：用什麼想

這一版只有一種引擎：OpenAI 相容的 `chat/completions`。這裡只定欄位；請求怎麼組、怎麼打、回來怎麼
拿，見 [aos-llm-ask.md](aos-llm-ask.md)。

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

## 3. 錯誤代號（讀／驗階段）

`str(e)`＝「代號: 白話」，訊息裡一定說是哪個檔：

| 代號 | 什麼時候 |
|---|---|
| `NotAnAgent` | 沒有 `info.json`、沒有 `_metainfo`、或 `_metainfo._type`（解完）不是 `llm_agent` |
| `ReadFailed`／`JsonSyntax`／`NotAnObject`／`NotAnArray` | 某個檔讀不到／不是 JSON／頂層型別不對 |
| `MetainfoInvalid`／`UnsupportedVersion` | `_type` 對了但 `_metainfo` 形狀壞（不是物件、缺 `_version`）／`_version` 不是整數 `1` |
| `FieldTypeMismatch` | 某格型別不對 |
| `MessageInvalid` | `history.json` 裡某一則不合 §2.3 |
| `ToolInvalid` | 工具檔不是陣列、元素缺 `type`／`function`／`function.name`、合併後同名、缺 `_meta`、`_meta` 不是合法 inst、`_meta` 寫了 `stdin`／`stdout` |
| `EngineInvalid` | `engine` 缺 `endpoint`／`model`、型別不對 |
| `StateInvalid` | `state.json` 的 `state` 不是 `idle`／`think`／`wait`／`act` 之一（§2.1.1） |

指示詞的代號（`UnknownDirective`、`EnvironmentVariableMissing`、`ReferenceCycle`…）照
[directives.md §6](directives.md)。

這張表只管「檔案讀不讀得起來、形狀對不對」。引擎回錯、工具炸掉那些是程式跑的時候的事，
各程式的規範自己講。

## 4. 這份規範沒管的事

- **程式做什麼**：問模型＝[aos-llm-ask.md](aos-llm-ask.md)；狀態機、收 user 訊息、等檔案、逾時、
  跑工具＝[aos-agent.md](aos-agent.md)（使用者還在想）。
- **輸入從哪來、回話回給誰**（信箱、aos-user、別的 agent）、**怎麼放進 kernel**：之後再說。

## 我自己選的、使用者可以推翻的

1. `system.json` 用 `{"content": "…"}`，不用整則訊息——role 是固定的，沒必要寫。
2. `tools` 是路徑陣列，沒有 `disabled` 開關：要關就從陣列拿掉。
3. 合併後同名工具直接報錯，不用「後面蓋前面」。
4. `_meta` 放在工具元素的頂層（跟 `type`／`function` 平行），不放在 `function` 裡面。
5. `state.json` 不解指示詞、沒檔＝`idle`：它是 agent 自己的檔，只有一格，沒必要吃指示詞。
