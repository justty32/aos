# agent 資料夾規範（第 1 版，**草稿**）

← [proto5 README](../README.md)｜指示詞：[directives.md](directives.md)｜用這個資料夾的程式：[aos-llm-ask.md](aos-llm-ask.md)（組模型請求）、[aos-agent.md](aos-agent.md)（走一格）

> **這是草稿，還在跟使用者一步一步改**；不記修訂記錄。原則（使用者定的）：**先規劃檔案架構、
> 分配好每個檔在幹嘛，指示詞是輔助**。
>
> 這份講「什麼是一個 agent 資料夾」：兩份檔（`info.json`、`state.json`）長什麼樣、指示詞解不解、
> 共用的錯誤代號。`info.json` 的設定與它們指到的內容都在這份；程式拿這些檔**做什麼**在各程式的規範。

一句話：**一個 agent 就是一個資料夾**——`info.json` 說這是 agent、以及各程式要的設定；
`state.json` 記走到哪、輸入從哪來、在等什麼。

---

## 1. 資料夾長什麼樣

```
agent-bob/
  info.json            _metainfo ＋ 各程式要的設定（system／history／tools／engine…，見 §3）
  state.json           state ＋ input ＋ waits ＋ errors（§4）
  prompts/             慣例位置：人格、記憶
  tools/               慣例位置：工具檔
  tool-results/        CPU 工具結果 <call 索引>.json；收回改 .json.done
```

- 只有 `info.json` 是**認出「這是 agent 資料夾」**的依據（有它、而且 `_metainfo._type` 是 `llm_agent`）。
  `_metainfo` 也吃指示詞，所以「認不認」要先解完才知道；解不開就是指示詞的錯，不是 `NotAnAgent`。
- 檔案裡寫的路徑，**一律相對於 agent 資料夾**（不是相對於寫它的那個檔）；絕對路徑照字面。
  路徑指到**資料夾**＝裡面所有 `*.json` 照檔名排序（`.done` 結尾的不算）。
- **誰能讀、誰能寫，規範不管**：看程式自己怎麼做、看檔案的存取權限。慣例上 `info.json` 是人寫的、
  `state.json` 跟記憶是程式寫的，但那是慣例不是規則。
- 程式寫檔一律先寫 `.tmp` 再 rename，別人永遠不會讀到寫一半的檔。
- 每個檔的頂層都是嚴格的物件或陣列；**不認得的 key 一律忽略**。
- `prompts/`、`tools/` 只是慣例，`info.json` 裡指到哪就是哪；放哪都行。

## 2. 指示詞：`info.json`／`state.json` 解、被指到的檔不解

| 檔 | 解不解 | 為什麼 |
|---|---|---|
| `info.json`、`state.json` | **每一格都解**（含 `_metainfo`） | 這是設定，寫的人想 `$env`／`$fmt`／`$ref`／`$opt` 就用（哪一格吃哪些 `$opt` 由那一格的規範定） |
| 這兩份指到的檔 | **整份不解，原樣讀** | 那些是「內容」：人格文字、模型吐出來的對話、工具的 schema 與 inst、丟進來的輸入。內容裡什麼 `$` 都可能有，不能被當指示詞 |

怎麼解，照 [directives.md](directives.md)：

- **每一格都能放**：頂層整份、每個欄位、陣列的每個元素、物件的每個值；先解再驗型別。
  **`_metainfo` 也解**（這點跟 inst 不同：inst 的 `_metainfo` 不解）。
- **中心路徑（`$ref` 找檔的地方）＝agent 資料夾**。
- **`$ref:""`＝這個值所在的那份檔**；位置＝實體路徑（`info.json` 的 `/tools/0`…），相對 `$at`
  照 directives.md 3.2 算。
- **`$env` 讀的是執行那支程式（aos-llm-ask／aos-agent）自己的環境**。
- 解錯了（`UnknownDirective`、`ReferenceCycle`…）＝讀驗錯誤，代號照 directives.md §6。
- 指到別的檔的那一格（例如 `"history": {"$env": "BOB_HISTORY"}`）**會解**；解出路徑之後，
  **讀進來的東西不解**。工具的 `_meta` 是一份 inst，它裡面的指示詞是跑工具的時候由 inst 那套
  （base＝agent 資料夾）解的。
- 程式要改寫這兩份檔的某一格（aos-agent 改 `state`、劃掉 `waits` 的一條）時，改的是**原始 JSON**
  的那一格、其他格原樣抄回，不是把解完的結果寫回去——所以**被程式改寫的那一格在原始 JSON 裡必須是
  字面值**（`state` 是字面字串、`errors` 是字面整數、`waits` 是字面陣列或單條），頂層也不能整份是指示詞（不然寫不回來）。

## 3. `info.json`

```json
{
  "_metainfo": {"_type": "llm_agent", "_version": 1},
  "system": "prompts/system.json",
  "history": "prompts/history.json",
  "tools": ["tools/base.json"],
  "engine": {"cpu": "../llm", "model": "small", "params": {"temperature": 0.2}},
  "tool_cpu": "../tool"
}
```

| 鍵 | 型別 | 沒寫時 | 意思 |
|---|---|---|---|
| `_metainfo` | 物件 | **必填** | `_type` 只認 `"llm_agent"`、`_version` 只認整數 `1`，bool 不算 |
| `system` | 路徑字串 | `prompts/system.json` | 人格檔（§3.1） |
| `history` | 路徑字串 | `prompts/history.json` | 記憶檔（§3.2） |
| `tools` | 路徑字串陣列 | `[]` | 工具檔，照列表順序合併（§3.3） |
| `engine` | 物件 | **必填** | llm CPU 路徑、模型代號與參數（§3.4） |
| `tool_cpu` | 路徑字串 | 無；load 回 `None` | 工具 CPU 家；有 `_run: "cpu"` 的工具時必填 |

`system`／`history`／`tools`／`tool_cpu` 型別不對為 `FieldTypeMismatch`；明寫 null 不合法。
info 裡沒有欄位吃 `$opt`，出現為 `UnknownOption`。先解指示詞，再驗欄位；真正送件才驗 CPU 家。

### 3.1 人格（`system` 指到的檔，慣例放 `prompts/system.json`）

```json
{"content": "你是個簡潔、會用工具的助手。"}
```

- `content`：字串，就是 system prompt 本文；缺了或不是字串＝`FieldTypeMismatch`。**檔不存在＝空字串**（不送 system 訊息）；存在但讀不到／壞掉＝`ReadFailed`／`JsonSyntax`。
- **原樣讀、不解指示詞**（[agent.md §2](agent.md)）：`content` 就是字面，裡面的 `${x}`、`$` 開頭的東西都不會被動。

### 3.2 記憶（`history` 指到的檔，慣例放 `prompts/history.json`）

一個陣列，一則就是 OpenAI chat 的一則訊息：

```json
[
  {"role": "user",      "content": "看看資料夾裡有什麼"},
  {"role": "assistant", "content": null, "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "sh", "arguments": "{\"cmd\":\"ls\"}"}}]},
  {"role": "tool",      "tool_call_id": "c1", "content": "state.json\nprompts\ntools\n"},
  {"role": "assistant", "content": "裡面有 state.json、prompts、tools…"}
]
```

- `role` 只認 `user`／`assistant`／`tool`；`system` 不放這裡（每次組請求時從人格檔補在最前面）。
- `user`／`tool` 的 `content` 要是字串；`tool` 一定要有字串的 `tool_call_id`；`assistant` 要有「`content` 是字串」或「`tool_calls` 是陣列」至少一樣（`content: ""` 算有，`content: null` 又沒 `tool_calls` 不算）。不合 → `MessageInvalid`。
- **檔不存在＝`[]`**；存在但讀不到／壞掉＝`ReadFailed`／`JsonSyntax`。
- **原樣讀寫、不解指示詞**（[agent.md §2](agent.md)）：模型回的 JSON 裡有 `$` 開頭的 key 也不會被誤認。
- 整份讀、整份寫；記憶長了怎麼辦之後再說（先跟 proto4-7 一樣）。

### 3.3 工具檔（`tools` 指到的檔，慣例放 `tools/`）：OpenAI tools 陣列 ＋ `_meta`／`_timeout_ms`／`_run`

一份工具檔就是**一個 OpenAI chat/completions 的 `tools` 陣列**，一個元素一個工具、形狀照 OpenAI
原樣；每個元素多一個 **`_meta`**，說「這個工具真的被叫到時怎麼跑」——內容就是**一份
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
- `_timeout_ms`：可選，工具元素旁的正整數毫秒（bool 不算），沒寫＝`60000`；不解指示詞、型別不對＝`ToolInvalid`。保留在 `tools_raw`，送模型前跟其他 `_` key 一起拿掉。`_meta` 仍是純 inst。
- `_run`：可選，字面 `"sync"`（預設）或 `"cpu"`，其他值＝`ToolInvalid`；不解指示詞，送模型前移除。`sync` 由 agent 執行，`cpu` 交給 `info.json` 頂層 `tool_cpu` 指到的 CPU；有任何 CPU 工具卻未設定 `tool_cpu`＝`FieldTypeMismatch`。路徑相對 agent 家、可解指示詞；讀驗層只解路徑，真正送件才驗 CPU 家。詳見 [agent.md](agent.md) 與 [aos-agent.md](aos-agent.md)。
- 合併後 `function.name` 同名 → `ToolInvalid`（不默默蓋掉，寫錯一眼看得到）。
- 工具檔頂層不是陣列 → `ToolInvalid`（記憶檔不是陣列才是 `NotAnArray`）。
- 元素缺 `type`／`function`／`function.name` → `ToolInvalid`；`function` 裡其他東西（`description`、
  `parameters`、`strict`…）本文不驗，原樣送模型。
- **工具檔原樣讀、不解指示詞**（[agent.md §2](agent.md)）；`_meta` 裡的指示詞是跑的時候由 inst 那套解。

`_meta` 讀驗時**只驗不跑**（是物件、沒寫 `stdin`／`stdout`——寫了＝`ToolInvalid`，因為跑的時候參數走
stdin、結果走 stdout）；真的跑是 [aos-agent.md](aos-agent.md) 的事。要關掉一個工具就從 `info.json` 的
`tools` 拿掉那份檔、或從工具檔裡刪掉。

### 3.4 `engine`：用哪顆 CPU、哪個模型代號

```json
"engine": {"cpu": "../llm", "model": "small", "params": {"temperature": 0.2}}
```

| 鍵 | 型別 | 沒寫時 | 意思 |
|---|---|---|---|
| `cpu` | 路徑字串 | **必填** | llm CPU 家，相對 agent 家；解完回絕對路徑 |
| `model` | 非空字串 | **必填** | CPU 的 `models` 表中的代號 |
| `params` | 物件 | `{}` | 組 body 用的模型參數，例如 temperature |

engine 整格不是物件為 `FieldTypeMismatch`；缺 engine、內部必填欄位缺失或型別錯為 `EngineInvalid`。
cpu 空字串沿路徑規則指 agent 家自己；
讀驗只解路徑，送件時才驗 CPU 身分。整格與每格都可解指示詞。
endpoint、真實模型名稱、api_key、timeout_ms 由 [llm CPU 的 models 表](llm-cpu.md) 定義；
agent 的 engine 只保留上表三格。think 一律交 CPU，沒有同步模式。

## 4. `state.json`

工具 CPU 路徑 `tool_cpu` 是上節的 info 設定；state 仍只有以下四個已知欄位，不新增 `ask`／`calls`。act 的等待以 `waits` 一條 all 條目表達，值是所有 `<agent>/tool-results/<i>.json` 絕對路徑。

```json
{
  "state": "idle",
  "input": "input.json",
  "waits": ["tool_result.json"]
}
```

| 鍵 | 型別 | 沒寫時 | 意思 |
|---|---|---|---|
| `state` | `idle`／`think`／`act` | `idle` | 狀態機走到哪。各格做什麼是 [aos-agent.md §3](aos-agent.md) 的事；**沒有 `wait` 這一格**：等不是狀態，是門（`waits`） |
| `errors` | 非負字面整數 | `0` | 連續引擎失敗次數，由 aos-agent 寫；成功歸零、第三次失敗歸零並等 `continue.json`（見 [aos-agent.md §3](aos-agent.md)） |
| `input` | 路徑或路徑陣列 | `input.json` | 輸入從哪來：指到的東西接進記憶（§4.1），接完清掉 |
| `waits` | 一條或一條陣列（§4.2） | 沒寫＝不用等 | 門：還有沒到的就不走這一格（§4.2；怎麼判在 [aos-agent.md §2](aos-agent.md)） |

- **檔不存在＝全部預設**（`state` 是 `idle`），aos-agent 第一次動就會把它寫出來；存在但壞掉＝
  `ReadFailed`／`JsonSyntax`。
- `state` 不是三個之一、或在原始 JSON 裡不是字面字串 → `StateInvalid`；`input`／`waits` 型別不對、
  `waits` 在原始 JSON 裡不是字面陣列或單條、或 `errors` 不是非負字面整數（bool 不算） → `FieldTypeMismatch`（§2 最後一條）。

### 4.1 `input`：輸入長什麼樣

指到的每個檔，內容是三種之一，都變成訊息接在記憶尾巴：

| 檔裡是 | 變成 |
|---|---|
| 字串 | 一則 `{"role": "user", "content": …}` |
| 一則訊息物件 | 原樣一則（`role` 照 本份 §3.2 驗，不合＝`MessageInvalid`） |
| 訊息陣列 | 原樣一串 |

- 檔不存在、或空陣列＝沒有輸入。
- **清掉**＝讀進去之後把檔 rename 成 `<原名>.done`（舊的蓋掉），不原地清空——別人在程式讀完到清掉
  之間又丟一則也不會被吃掉。

### 4.2 `waits`：等待表

一張**等待表**：一條或多條「等某個檔」。空的或沒寫＝不用等。誰要 agent 停下來等，誰就往表尾加一條；
aos-agent 自己也會加條目（送出 LLM／工具請求、引擎連敗暫停），到了就劃掉（怎麼判、劃掉之後怎樣在 [aos-agent.md §2](aos-agent.md)）。

```json
"waits": [
  "tool_result.json",                                             路徑：檔存在就算到
  {"$opt": "consume", "$val": "tool_result.json"},                到了順便 rename 成 .done
  {"$opt": ["mtime", "consume"], "$val": "log.json", "since": 1758443000},
  {"$opt": "any", "$val": ["a.json", "b.json"]},                  a、b 任一個到就算這條到
  {"$opt": "exists", "$val": "inbox/"}                            資料夾：裡面有任何一個 *.json
]
```

- 一條＝路徑字串，或 `{"$opt": 名字|[名字…], "$val": 路徑|[路徑…]}`（`$opt` 慣例跟 inst 一樣；不認得
  ＝`UnknownOption`、互斥＝`OptionConflict`）。`$val` 陣列＝這一條同時盯好幾個檔。
- `waits` 整格在原始 JSON 裡要是字面陣列（或字面一條），因為 aos-agent 要按索引劃掉條目；陣列裡
  **每一條**照樣解指示詞（路徑用 `$fmt` 拼、一條 `$ref` 到別的檔都行）。`since` 這種不是 `$` 開頭的
  key 指示詞機制放著不動、程式自己讀，所以 `since` 要是字面數字。

| 選項 | 「到了」的意思 | 備註 |
|---|---|---|
| `exists` | 檔存在。資料夾＝裡面有任何一個 `*.json` | **預設** |
| `mtime` | 檔的修改時間 > 這條的 `since`（epoch 秒，整數或小數）。資料夾＝裡面任何一個 `*.json` 的修改時間 > `since` | 加這條的人寫 `since`；沒寫或不是數字＝`FieldTypeMismatch`。跟 `exists` 互斥 |
| `consume` | （不改「到了」的判斷）到了之後把檔 rename 成 `<原名>.done`，資料夾＝裡面當時在的 `*.json` 都 rename | 不然檔一直在，下次沒得等 |
| `any` | `$val` 陣列裡**任一個**到＝這條到 | 跟 `all` 互斥；`$val` 只有一個路徑時無差 |
| `all` | `$val` 陣列裡**全部**到＝這條到 | **預設** |

**容易踩的**：同一個檔同時列在 `waits` 跟 `input`（例如等 `tool_result.json` 出現、然後把它當輸入收）——
`waits` 那條**不要**開 `consume`，不然門一開檔就被 rename 成 `.done`，`input` 就收不到了；讓 `input`
那邊去清。

## 5. 共用的錯誤代號（讀／驗階段）

`str(e)`＝「代號: 白話」，訊息裡一定說是哪個檔：

| 代號 | 什麼時候 |
|---|---|
| `NotAnAgent` | 沒有 `info.json`、沒有 `_metainfo`、`_metainfo` 缺 `_type`、或 `_type`（解完）不是 `llm_agent` |
| `ReadFailed`／`JsonSyntax`／`NotAnObject`／`NotAnArray` | 某個檔讀不到／不是 JSON／頂層型別不對（各程式可以對自己的檔另訂更準的代號，例如工具檔不是陣列＝`ToolInvalid`） |
| `MetainfoInvalid`／`UnsupportedVersion` | `_metainfo` 不是物件、或缺 `_version`／`_version` 不是整數 `1` |
| `FieldTypeMismatch` | 某格型別不對、或該字面的格不是字面 |
| `StateInvalid` | `state.json` 的 `state` 不是三個之一、或在原始 JSON 裡不是字面字串（§4） |

指示詞的代號（`UnknownDirective`、`EnvironmentVariableMissing`、`ReferenceCycle`…）照
[directives.md §6](directives.md)；內容欄位的代號（`MessageInvalid`、`ToolInvalid`、
`EngineInvalid`）見 §3。

## 6. 這份規範沒管的事

- **程式做什麼**：組模型請求＝[aos-llm-ask.md](aos-llm-ask.md)；門怎麼判、狀態機、跑工具＝[aos-agent.md](aos-agent.md)。
- **輸入從哪來、回話回給誰**（信箱、aos-user、別的 agent）、**怎麼放進 kernel**：之後再說。

## 我自己選的、使用者可以推翻的

1. `_metainfo` 必填、也解指示詞。
2. `state.json` 沒檔＝全部預設。
3. `input` 沒寫＝`input.json`；檔裡可以是字串／一則／一串；清掉＝rename `.done`。
4. `waits` 的五個選項名與預設（`exists`、`all`）；`mtime` 對資料夾＝看裡面每個 `*.json`。
