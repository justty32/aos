# agent 資料夾規範（第 1 版，**草稿**）

← [proto5 README](../README.md)｜指示詞：[directives.md](directives.md)｜用這個資料夾的程式：[aos-llm-ask.md](aos-llm-ask.md)（問模型一次）、[aos-agent.md](aos-agent.md)（走一格；使用者還在想）

> **這是草稿，還在跟使用者一步一步改**；不記修訂記錄。原則（使用者定的）：**先規劃檔案架構、
> 分配好每個檔在幹嘛，指示詞是輔助**。
>
> 這份**只講「什麼是一個 agent 資料夾」**：兩份檔（`info.json`、`state.json`）、指示詞解不解、
> 共用的錯誤代號。兩份檔裡各程式自己的欄位、它們指到的檔長什麼樣，**由用它的程式的規範定**
> （`info.json` 的 `system`／`history`／`tools`／`engine`＝[aos-llm-ask.md §2](aos-llm-ask.md)；
> `state.json` 的 `input`／`returns`／`waits`＝[aos-agent.md §2](aos-agent.md)）。

一句話：**一個 agent 就是一個資料夾**——`info.json` 說這是 agent、以及各程式要的設定；
`state.json` 記走到哪、以及走的時候要看哪些外面的檔。

---

## 1. 資料夾長什麼樣

```
agent-bob/
  info.json            _metainfo ＋ 各程式要的設定（system／history／tools／engine…，見 aos-llm-ask.md）
  state.json           state ＋ aos-agent 的三個入口（input／returns／waits，見 aos-agent.md）
  prompts/             慣例位置：人格、記憶
  tools/               慣例位置：工具檔
```

- 只有 `info.json` 是**認出「這是 agent 資料夾」**的依據（有它、而且 `_metainfo._type` 是 `llm_agent`）。
  `_metainfo` 也吃指示詞，所以「認不認」要先解完才知道；解不開就是指示詞的錯，不是 `NotAnAgent`。
- 檔案裡寫的路徑，**一律相對於 agent 資料夾**（不是相對於寫它的那個檔）；絕對路徑照字面。
- **誰能讀、誰能寫，規範不管**：看程式自己怎麼做、看檔案的存取權限。慣例上 `info.json` 是人寫的、
  `state.json` 跟記憶是程式寫的，但那是慣例不是規則。
- 程式寫檔一律先寫 `.tmp` 再 rename，別人永遠不會讀到寫一半的檔。
- 每個檔的頂層都是嚴格的物件或陣列；**不認得的 key 一律忽略**。
- `prompts/`、`tools/` 只是慣例，`info.json` 裡指到哪就是哪；放哪都行。

## 2. 指示詞：`info.json`／`state.json` 解、被指到的檔不解

| 檔 | 解不解 | 為什麼 |
|---|---|---|
| `info.json`、`state.json` | **每一格都解**（含 `_metainfo`） | 這是設定，寫的人想 `$env`／`$fmt`／`$ref`／`$opt` 就用（哪一格吃哪些 `$opt` 由各程式的規範定） |
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
- 程式要改寫這兩份檔的某一格（例如 aos-agent 改 `state`）時，改的是**原始 JSON** 的那一格、其他格
  原樣抄回，不是把解完的結果寫回去——所以被程式改寫的那一格在原始 JSON 裡必須是字面值，頂層也不能
  整份是指示詞（不然寫不回來）。

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
  "...": "其他欄位由用它的程式定，見 aos-agent.md §2（input／waits）"
}
```

- `state`：`idle`／`think`／`act` 之一（各格做什麼是 [aos-agent.md](aos-agent.md) 的事；「等」不是狀態，是門，也在那份）。
  程式改寫它時只動這一格、其他格原樣抄回（§2），所以 `state` 在原始 JSON 裡要是字面字串。
- **檔不存在＝`{"state": "idle"}`**，aos-agent 第一次動就會把它寫出來；存在但壞掉＝`ReadFailed`／`JsonSyntax`。
- 每一格解指示詞（§2）；`state` 不是三個之一、或不是字面字串 → `StateInvalid`。

## 5. 共用的錯誤代號（讀／驗階段）

`str(e)`＝「代號: 白話」，訊息裡一定說是哪個檔：

| 代號 | 什麼時候 |
|---|---|
| `NotAnAgent` | 沒有 `info.json`、沒有 `_metainfo`、`_metainfo` 缺 `_type`、或 `_type`（解完）不是 `llm_agent` |
| `ReadFailed`／`JsonSyntax`／`NotAnObject`／`NotAnArray` | 某個檔讀不到／不是 JSON／頂層型別不對（各程式可以對自己的檔另訂更準的代號，例如工具檔不是陣列＝`ToolInvalid`） |
| `MetainfoInvalid`／`UnsupportedVersion` | `_metainfo` 不是物件、或缺 `_version`／`_version` 不是整數 `1` |
| `FieldTypeMismatch` | 某格型別不對 |
| `StateInvalid` | `state.json` 的 `state` 不是三個之一、或在原始 JSON 裡不是字面字串（§4） |

指示詞的代號（`UnknownDirective`、`EnvironmentVariableMissing`、`ReferenceCycle`…）照
[directives.md §6](directives.md)；各程式自己欄位的代號（`MessageInvalid`、`ToolInvalid`、
`EngineInvalid`…）在各程式的規範。

## 6. 這份規範沒管的事

- **程式做什麼**：問模型＝[aos-llm-ask.md](aos-llm-ask.md)；狀態機、收 user 訊息、等檔案、逾時、
  跑工具＝[aos-agent.md](aos-agent.md)（使用者還在想）。
- **輸入從哪來、回話回給誰**（信箱、aos-user、別的 agent）、**怎麼放進 kernel**：之後再說。

## 我自己選的、使用者可以推翻的

1. `_metainfo` 必填、也解指示詞。
2. `state.json` 沒檔＝`idle`。
