# agent 資料夾規範（第 1 版，**草稿**）

← [proto5 README](../README.md)｜跑工具與引擎靠 [inst-posix.md](inst-posix.md)；`info.json` 吃指示詞（[directives.md](directives.md)），其他檔原樣讀

> **這是草稿，還在跟使用者一步一步改**；不記修訂記錄。原則（使用者定的）：**先規劃檔案架構、
> 分配好每個檔在幹嘛，指示詞是輔助**。所以規範裡寫的都是普通的路徑字串與字面值；人寫的那一份
> 設定檔（`info.json`）每一格都吃指示詞，**其他檔（狀態、人格、記憶、工具）原樣讀、不解**
> （規則在 §2.0）。
> 沒拍板的地方我先照自己的想法填，好讓使用者有東西可以改；每一節都獨立、好抽換。

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

- `state`：`idle`／`think`／`wait`／`act` 四格之一（§3）。就這一個 key。
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

`_meta`（inst）跑起來的約定：

- **參數 JSON 從 stdin 進去、結果從 stdout 出來**（結果是純文字，整段當 `tool` 訊息的 `content`）。
  進 stdin 的就是模型給的 `tool_calls[i].function.arguments` **那個字串原樣**，agent 不解析、不重排；
  它不是合法 JSON 也照塞，工具自己驗。
  所以 `_meta` 裡**不准寫 `stdin`／`stdout`**（寫了＝`ToolInvalid`），其他欄位（`stderr`／`exit`／
  `cwd`／`envs`）照 inst 規則。
- 模型叫了一個**合併表裡沒有的名字** → 不跑，回一則 `tool` 訊息 `content`＝「沒有這個工具：xxx」，
  讓模型自己改；不算 agent 的錯。
- base（inst 的「家」）＝agent 資料夾；沒寫 `cwd` 就在 agent 資料夾跑。
- 退出碼非 0 ＝工具錯誤：`content` 是「工具 sh 失敗（exit 1）：」＋stdout 前段，模型自己看著辦；不算 agent 的錯。
- 要關掉一個工具就從 `info.json` 的 `tools` 拿掉那份檔、或從工具檔裡刪掉；沒有 enable／disable 開關。

### 2.5 `engine`（在 `info.json` 裡）：用什麼想

「想」＝把 system＋history＋工具表交出去、換一則 assistant 訊息回來。這一版只有一種：agent 程式
自己打 OpenAI 相容的 `chat/completions`，**當場等回來**（這一格會卡住等網路；第一版接受）。

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

- 請求 body：`{"model", "messages": [system, ...history], "tools": [合併後、去掉 _meta 的工具表], ...params}`。
  沒有工具就不送 `tools`。
- 回來拿 `choices[0].message` 當 assistant 訊息接進記憶；HTTP 錯、逾時、形狀不對 → 這次「想」算錯
  （下一格重試，不是讀驗錯誤）。
- 必填欄位缺、型別不對 → `EngineInvalid`。
- `engine` 整格在 `info.json` 裡，所以跟別格一樣吃指示詞：整包 `{"$ref": "engines/lmstudio.json"}`
  從別的檔拿也行。
- 「引擎是外面一支程式」「引擎晚點才給結果、agent 先去等一個檔」**之後再說**。

## 3. 四格

照 [24-agent.md §25](../../proto4/notes/24-agent.md) 使用者那組。每叫一次 aos-agent 只走一格：

| 格 | 只做什麼 | 下一格 |
|---|---|---|
| `idle` | 沒事。有新的輸入（一則 `user` 訊息）就接進記憶——輸入從哪來不在這份規範（§5） | 有事 `think`，沒事留 `idle`（退出碼 101） |
| `think` | 組請求交給 `engine`，拿到的 assistant 訊息接進記憶 | 拿到 `act`，錯了留 `think`（下一格重試） |
| `wait` | 等外面的東西回來。**這一版沒東西可等**（引擎都當場回），格子先留著，等檔案機制定了再填 | — |
| `act` | 看記憶最後那則 assistant：有 `tool_calls` 就逐一跑工具（每個結果一則 `tool` 訊息，順序照 `tool_calls`）；沒有就是回話（`content` 空也算回了話）——回給誰、怎麼回不在這份規範（§5） | 跑了工具 `think`，回了話 `idle` |

- 退出碼：這格做了事＝0；在等（`idle` 沒事）＝101；讀驗錯誤（§4）＝1；用法錯＝2。100（收工）之後再說。
- 一題走幾格、連錯幾次要不要停：先不管；要管的時候再決定記在哪。

## 4. 錯誤代號（讀／驗階段）

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
| `StateInvalid` | `state.json` 的 `state` 不是四格之一（§2.1.1） |

指示詞的代號（`UnknownDirective`、`EnvironmentVariableMissing`、`ReferenceCycle`…）照
[directives.md §6](directives.md)。

讀驗錯誤＝這一格**根本沒走**，退出碼 1、`state.json` 不動。引擎回錯、工具炸掉這些是
**跑的時候的錯**，下一格重試，不是這張表的。

## 5. 這份規範沒管的事

- **輸入從哪來、回話回給誰**（信箱、aos-user、別的 agent）：不在這份，之後另寫；這裡只知道
  `idle` 會拿到一則 `user` 訊息、`act` 會產出一則回話。
- **等檔案**（引擎或工具晚點才給結果）、**引擎是外面一支程式**：之後再說；`wait` 格先留著。
- **怎麼被叫醒、多久走一格、怎麼放進 kernel**：kernel／daemon 的事。
- **aos-agent 的命令列**：另寫（草案在 [thinking/](../../thinking/)）。

## 我自己選的、使用者可以推翻的

1. `system.json` 用 `{"content": "…"}`，不用整則訊息——role 是固定的，沒必要寫。
2. `tools` 是路徑陣列，沒有 `disabled` 開關：要關就從陣列拿掉。
3. 合併後同名工具直接報錯，不用「後面蓋前面」。
4. `_meta` 放在工具元素的頂層（跟 `type`／`function` 平行），不放在 `function` 裡面。
5. 工具沒有逾時設定（inst 本身沒有逾時欄位）；要的話之後加。
6. `engine` 只剩 OpenAI 相容 HTTP、當場等回來——違反「一格不等網路」，第一版先接受。
7. 沒有任何上限與計數（一題幾格、連錯幾次、等多久）——使用者說先只剩 `state`，要管再說。
8. `state.json` 不解指示詞、沒檔＝`idle`：它是 agent 自己的檔，只有一格，沒必要吃指示詞。
