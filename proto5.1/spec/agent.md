# agent 資料夾規範（第 1 版，**草稿**）

← [proto5 README](../README.md)｜指示詞：[directives.md](directives.md)｜用這個資料夾的程式：[aos-llm-ask.md](aos-llm-ask.md)（問模型一次）、[aos-agent.md](aos-agent.md)（走一格）

> **這是草稿，還在跟使用者一步一步改**；不記修訂記錄。原則（使用者定的）：**先規劃檔案架構、
> 分配好每個檔在幹嘛，指示詞是輔助**。
>
> 這份講「什麼是一個 agent 資料夾」：兩份檔（`info.json`、`state.json`）長什麼樣、指示詞解不解、
> 共用的錯誤代號。`info.json` 裡 `_metainfo` 以外的欄位是給 aos-llm-ask 用的，形狀在
> [aos-llm-ask.md §2](aos-llm-ask.md)；程式拿這些檔**做什麼**在各程式的規範。

一句話：**一個 agent 就是一個資料夾**——`info.json` 說這是 agent、以及各程式要的設定；
`state.json` 記走到哪、輸入從哪來、在等什麼。

---

## 1. 資料夾長什麼樣

```
agent-bob/
  info.json            _metainfo ＋ 各程式要的設定（system／history／tools／engine…，見 aos-llm-ask.md）
  state.json           state ＋ input ＋ waits（§4）
  prompts/             慣例位置：人格、記憶
  tools/               慣例位置：工具檔
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
  字面值**（`state` 是字面字串、`waits` 是字面陣列），頂層也不能整份是指示詞（不然寫不回來）。

## 3. `info.json`

```json
{
  "_metainfo": {"_type": "llm_agent", "_version": 1},
  "...": "其他欄位由用它的程式定，見 aos-llm-ask.md §2"
}
```

| 鍵 | 型別 | 沒寫時 | 意思 |
|---|---|---|---|
| `_metainfo` | 物件 | **必填** | `_type` 只認 `"llm_agent"`、`_version` 只認整數 `1`；規則同 [inst-posix.md §1](inst-posix.md)。跟 inst 不同的是必填：這是新格式、沒有舊檔要相容，而且這就是「這是 agent 資料夾」的記號 |

其他欄位（`system`／`history`／`tools`／`engine`）與它們指到的檔長什麼樣：[aos-llm-ask.md §2](aos-llm-ask.md)。

## 4. `state.json`

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
| `input` | 路徑或路徑陣列 | `input.json` | 輸入從哪來：指到的東西接進記憶（§4.1），接完清掉 |
| `waits` | 一條或一條陣列（§4.2） | 沒寫＝不用等 | 門：還有沒到的就不走這一格（§4.2；怎麼判在 [aos-agent.md §2](aos-agent.md)） |

- **檔不存在＝全部預設**（`state` 是 `idle`），aos-agent 第一次動就會把它寫出來；存在但壞掉＝
  `ReadFailed`／`JsonSyntax`。
- `state` 不是三個之一、或在原始 JSON 裡不是字面字串 → `StateInvalid`；`input`／`waits` 型別不對、
  `waits` 在原始 JSON 裡不是字面陣列 → `FieldTypeMismatch`（§2 最後一條）。

### 4.1 `input`：輸入長什麼樣

指到的每個檔，內容是三種之一，都變成訊息接在記憶尾巴：

| 檔裡是 | 變成 |
|---|---|
| 字串 | 一則 `{"role": "user", "content": …}` |
| 一則訊息物件 | 原樣一則（`role` 照 [aos-llm-ask.md §2.2](aos-llm-ask.md) 驗，不合＝`MessageInvalid`） |
| 訊息陣列 | 原樣一串 |

- 檔不存在、或空陣列＝沒有輸入。
- **清掉**＝讀進去之後把檔 rename 成 `<原名>.done`（舊的蓋掉），不原地清空——別人在程式讀完到清掉
  之間又丟一則也不會被吃掉。

### 4.2 `waits`：等待表

一張**等待表**：一條或多條「等某個檔」。空的或沒寫＝不用等。誰要 agent 停下來等，誰就往表尾加一條；
aos-agent 到了就劃掉（怎麼判、劃掉之後怎樣在 [aos-agent.md §2](aos-agent.md)）。

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
[directives.md §6](directives.md)；各程式自己欄位的代號（`MessageInvalid`、`ToolInvalid`、
`EngineInvalid`…）在各程式的規範。

## 6. 這份規範沒管的事

- **程式做什麼**：問模型＝[aos-llm-ask.md](aos-llm-ask.md)；門怎麼判、狀態機、跑工具＝[aos-agent.md](aos-agent.md)。
- **輸入從哪來、回話回給誰**（信箱、aos-user、別的 agent）、**怎麼放進 kernel**：之後再說。

## 我自己選的、使用者可以推翻的

1. `_metainfo` 必填、也解指示詞。
2. `state.json` 沒檔＝全部預設。
3. `input` 沒寫＝`input.json`；檔裡可以是字串／一則／一串；清掉＝rename `.done`。
4. `waits` 的五個選項名與預設（`exists`、`all`）；`mtime` 對資料夾＝看裡面每個 `*.json`。
