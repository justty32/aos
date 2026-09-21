# agent 資料夾規範（第 1 版，**草稿**）

← [proto5 README](../README.md)｜跑工具與引擎靠 [inst-posix.md](inst-posix.md)；每份 JSON 都吃指示詞（[directives.md](directives.md)）

> **這是草稿，還在跟使用者一步一步改**；不記修訂記錄。原則（使用者定的）：**先規劃檔案架構、
> 分配好每個檔在幹嘛，指示詞是輔助**。所以規範裡寫的都是普通的路徑字串與字面值；但**每一份
> JSON 的每一格都吃指示詞**（規則在 §2.0），要 `$env`／`$fmt`／`$ref` 的人自己用。
> 沒拍板的地方我先照自己的想法填，好讓使用者有東西可以改；每一節都獨立、好抽換。

一句話：**一個 agent 就是一個資料夾**，`state.json` 是它的總表——這是 agent、走到哪、人格跟記憶
在哪兩個檔、用哪幾份工具檔；引擎另外一份 `engine.json`。bot 模型的五塊（system prompt、history、
tools、thinking engine、agent state）都從 `state.json` 找得到。

---

## 1. 資料夾長什麼樣

```
agent-bob/
  state.json           總表：_metainfo ＋ state ＋ system／history／tools 三個指向
  prompts/
    system.json        人格（system prompt）
    history.json       記憶（對話史，agent 寫）
  tools/
    base.json          一份工具檔＝一組工具
    team.json
  engine.json          思考引擎的設定
```

- 只有 `state.json` 是**認出「這是 agent 資料夾」**的依據（有它、而且 `_metainfo._type` 是 `agent`）。
- 檔案裡寫的路徑，**一律相對於 agent 資料夾**（不是相對於寫它的那個檔）；絕對路徑照字面。
- **誰寫誰**：人寫 `state.json` 裡 `state` 以外的東西、`prompts/system.json`、`tools/*`、`engine.json`；
  agent 只寫 `state.json` 的 `state` 那一格（其他 key 原樣抄回）跟 `prompts/history.json`。
  這樣人的設定永遠不會被程式改掉。
- agent 寫檔一律先寫 `.tmp` 再 rename，別人永遠不會讀到寫一半的檔。
- 每個檔的頂層都是嚴格的物件或陣列（各節有寫）；**不認得的 key 一律忽略**。
- **每份 JSON 都解指示詞**，規則統一在 §2.0。
- `prompts/`、`tools/` 這兩個資料夾名只是慣例，`state.json` 裡指到哪就是哪。

## 2. 每個檔的形狀

### 2.0 指示詞：每份 JSON 都一樣

agent 自己讀的 `.json`（`state.json`、`prompts/*.json`、`engine.json`）都照
[directives.md](directives.md) 解，規則對每份檔都一樣；**只有 `tools/` 裡的工具檔不解**（下面說）：

- **每一格都能放**：頂層整份、每個欄位、陣列的每個元素、物件的每個值；先解再驗型別。
  **`_metainfo` 也解**（這點跟 inst 不同：inst 的 `_metainfo` 不解，agent 的全部都解）。
- **中心路徑（`$ref` 找檔的地方）＝agent 資料夾**，不管指示詞寫在哪一份檔裡。
- **`$ref:""`＝這個值所在的那份檔**；位置＝那份檔裡的實體路徑（`state.json` 的 `/tools/0`、
  `tools/base.json` 的 `/0/run/argv`…），相對 `$at` 照 directives.md 3.2 算。
- **`$env` 讀的是 aos-agent 自己的環境**。
- **agent 寫回去的檔**（`state.json` 的 `state`、`prompts/history.json`）：寫回時**寫的是原始 JSON**
  （沒解過的）改了那一格，不是把解完的結果寫回去——不然人寫的 `$ref` 會被展開後的值蓋掉。
  `history.json` 整份是 agent 產的，一般不會有指示詞；有的話讀的時候照樣解。
- **`tools/*.json` 整份不解**：工具檔是原樣讀的。理由：`parameters` 是 JSON schema，裡面的
  `$ref`／`$schema` 是 schema 自己的字，不能被當指示詞；`run` 是一份 inst，它裡面的指示詞
  是**跑工具的時候**由 inst 那套（aos-exec／aos_inst，base＝agent 資料夾）解的，不是 agent 讀
  工具檔時解。所以工具檔裡除了 `run` 以外的地方寫 `$env`／`$ref` 沒用，就是字面。
- 代價（機制天生的）：agent 讀的那幾份檔裡，內容出現 `$` 開頭 key 的物件會被當指示詞。
  `history.json` 的 `content` 是字串所以沒事。
- 解錯了（`UnknownDirective`、`ReferenceCycle`…）＝讀驗錯誤，代號照 directives.md §6，退出碼 1。

### 2.1 `state.json`：總表

```json
{
  "_metainfo": {"_type": "agent", "_version": 1},
  "state":   "idle",
  "system":  "prompts/system.json",
  "history": "prompts/history.json",
  "tools":   ["tools/base.json", "tools/team.json"]
}
```

| 鍵 | 型別 | 沒寫時 | 誰寫 | 意思 |
|---|---|---|---|---|
| `_metainfo` | 物件 | **必填** | 人 | `_type` 只認 `"agent"`、`_version` 只認整數 `1`；規則同 [inst-posix.md §1](inst-posix.md)。跟 inst 不同的是必填：這是新格式、沒有舊檔要相容，而且這就是「這是 agent 資料夾」的記號 |
| `state` | `idle`／`think`／`wait`／`act` | `idle` | **agent** | 四格之一（§3） |
| `system` | 路徑字串 | `prompts/system.json` | 人 | 人格在哪個檔（§2.2） |
| `history` | 路徑字串 | `prompts/history.json` | 人 | 記憶在哪個檔（§2.3；那個檔是 agent 寫的） |
| `tools` | 路徑陣列 | `[]` | 人 | 用哪幾份工具檔（§2.4），順序＝送給模型的順序 |

- agent 每格結束只改寫 `state`，其他 key 原樣抄回。
- `state` 不是四格之一 → `StateInvalid`；`system`／`history` 不是字串、`tools` 不是字串陣列 → `FieldTypeMismatch`。

### 2.2 `prompts/system.json`：人格

```json
{"content": "你是個簡潔、會用工具的助手。"}
```

- `content`：字串，就是 system prompt 本文；沒有這個檔＝空字串（不送 system 訊息）。
- `content` 那一格跟別格一樣吃指示詞（想拼字串就 `{"$fmt": …}`、想從別的檔拿就 `$ref`）；
  解出來要是字串。字面字串裡的 `${x}` 就是字面，不會被動。

### 2.3 `prompts/history.json`：記憶（agent 寫）

一個陣列，一則就是 OpenAI chat 的一則訊息：

```json
[
  {"role": "user",      "content": "看看資料夾裡有什麼"},
  {"role": "assistant", "content": null, "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "sh", "arguments": "{\"cmd\":\"ls\"}"}}]},
  {"role": "tool",      "tool_call_id": "c1", "content": "state.json\nengine.json\n..."},
  {"role": "assistant", "content": "裡面有 state.json、engine.json…"}
]
```

- `role` 只認 `user`／`assistant`／`tool`；`system` 不放這裡（每次組請求時從 `system.json` 補在最前面）。
- `user`／`tool` 的 `content` 要是字串；`tool` 一定要有 `tool_call_id`；`assistant` 至少有 `content` 或 `tool_calls` 其中一個。不合 → `MessageInvalid`。
- 沒有這個檔＝`[]`。
- 整份讀、整份寫；記憶長了怎麼辦之後再說（先跟 proto4-7 一樣）。

### 2.4 `tools/*.json`：一份工具檔＝一組工具

一個陣列，一個元素一個工具：

```json
[
  {
    "name": "sh",
    "description": "在 agent 資料夾執行一句 shell 指令",
    "parameters": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]},
    "run": {"argv": ["tools/bin/sh-tool"], "stderr": "tools/log/sh.err"},
    "timeout_ms": 60000
  }
]
```

| 鍵 | 型別 | 沒寫時 | 意思 |
|---|---|---|---|
| `name` | 字串 | **必填** | 工具名，模型就用這個叫它。只准 `[A-Za-z0-9_-]` |
| `description`、`parameters` | 字串、物件 | `""`、`{"type":"object"}` | 照 OpenAI function 那套原樣送給模型；`parameters` 是 JSON schema，本文不驗它裡面 |
| `run` | 物件 | **必填** | **一份 posix inst**（[inst-posix.md](inst-posix.md) 整體形狀，`_metainfo` 可省）。跑工具＝照它跑一次 |
| `timeout_ms` | 整數 | `60000` | 跑超過就砍（照 inst 的逾時規則），結果算工具錯誤 |

- **工具檔整份不解指示詞**（§2.0）；`run` 裡的指示詞是跑的時候由 inst 那套解。
- 所有工具檔載完後**同名工具＝`ToolInvalid`**（不默默蓋掉，寫錯一眼看得到）。
- 要關掉一個工具就從 `state.json` 的 `tools` 拿掉那份檔、或從工具檔裡刪掉；沒有 enable／disable 開關。

`run` 的約定：

- **參數 JSON 從 stdin 進去、結果從 stdout 出來**（結果是純文字，整段當 `tool` 訊息的 `content`）。
  所以 `run` 裡**不准寫 `stdin`／`stdout`**（寫了＝`ToolInvalid`），其他欄位（`stderr`／`exit`／`cwd`／`envs`）照 inst 規則。
- `run` 的 base（inst 的「家」）＝agent 資料夾；沒寫 `cwd` 就在 agent 資料夾跑。
- 退出碼非 0 ＝工具錯誤：`content` 是「工具 sh 失敗（exit 1）：」＋stdout 前段，模型自己看著辦；不算 agent 的錯。

### 2.5 `engine.json`：用什麼想

「想」＝把 system＋history＋工具表交出去、換一則 assistant 訊息回來。誰來換，`kind` 決定：

```json
{"kind": "llm", "endpoint": "http://127.0.0.1:1234/v1", "model": "qwen/qwen3-1.7b",
 "params": {"temperature": 0.2}, "api_key": {"$env": "LMSTUDIO_KEY"}, "timeout_ms": 120000}
```

```json
{"kind": "posix", "run": {"argv": ["engines/kernel-llm", "K"]}}
```

| `kind` | 欄位 | 意思 |
|---|---|---|
| `llm` | `endpoint`（必）、`model`（必）、`params`（可省）、`api_key`（可省）、`timeout_ms`（預設 120000） | agent 程式自己打 OpenAI 相容的 `chat/completions`，**當場等回來**（這一格會卡住等網路；第一版接受） |
| `posix` | `run`（必；一份 posix inst，規則同工具的 `run`：stdin 進、stdout 出、不准寫 `stdin`／`stdout`）、`timeout_ms`（預設 60000） | 引擎是外面一支程式，一樣**當場等它跑完**。以後「規則」「別的 agent」都走這條，格式不用改 |

- `api_key` 不想寫進檔就寫 `{"$env": "NAME"}`（跟別格一樣，任何指示詞都行）；變數不在＝
  `EnvironmentVariableMissing`（設定壞就不跑，不降級）。
- `posix` 引擎的 stdin／stdout 協定：
  - stdin 收一份請求：`{"messages": [system, ...history], "tools": [工具表]}`（跟 chat/completions 的 body 同形）。
  - stdout 回 `{"message": {"role": "assistant", ...}}`。
  - 形狀不對、或退出碼非 0 → 這次「想」算錯（下一格重試，不是讀驗錯誤）。
- `kind` 不認得、必填欄位缺 → `EngineInvalid`。
- 「引擎晚點才給結果、agent 先去等一個檔」這套機制**之後再說**（使用者說的）；所以這一版兩種引擎
  都是當場等。

## 3. 四格

照 [24-agent.md §25](../../proto4/notes/24-agent.md) 使用者那組。每叫一次 aos-agent 只走一格：

| 格 | 只做什麼 | 下一格 |
|---|---|---|
| `idle` | 沒事。有新的輸入（一則 `user` 訊息）就接進記憶——輸入從哪來不在這份規範（§5） | 有事 `think`，沒事留 `idle`（退出碼 101） |
| `think` | 組請求交給 `engine`，拿到的 assistant 訊息接進記憶 | 拿到 `act`，錯了留 `think`（下一格重試） |
| `wait` | 等外面的東西回來。**這一版沒東西可等**（引擎都當場回），格子先留著，等檔案機制定了再填 | — |
| `act` | 看記憶最後那則 assistant：有 `tool_calls` 就逐一跑工具（每個結果一則 `tool` 訊息）；沒有就是回話——回給誰、怎麼回不在這份規範（§5） | 跑了工具 `think`，回了話 `idle` |

- 退出碼：這格做了事＝0；在等（`idle` 沒事）＝101；讀驗錯誤（§4）＝1；用法錯＝2。100（收工）之後再說。
- 一題走幾格、連錯幾次要不要停：先不管；要管的時候再決定記在哪。

## 4. 錯誤代號（讀／驗階段）

`str(e)`＝「代號: 白話」，訊息裡一定說是哪個檔：

| 代號 | 什麼時候 |
|---|---|
| `NotAnAgent` | 沒有 `state.json`、或它的 `_metainfo._type` 不是 `agent` |
| `ReadFailed`／`JsonSyntax`／`NotAnObject`／`NotAnArray` | 某個檔讀不到／不是 JSON／頂層型別不對 |
| `MetainfoInvalid`／`UnsupportedType`／`UnsupportedVersion` | `state.json` 的 `_metainfo` 不合 §2.1 |
| `FieldTypeMismatch` | 某格型別不對 |
| `MessageInvalid` | `history.json` 裡某一則不合 §2.3 |
| `ToolInvalid` | 工具缺 `name`、名字不合法、同名、缺 `run`、`run` 不是合法 inst、`run` 寫了 `stdin`／`stdout` |
| `EngineInvalid` | `engine.json` 的 `kind` 不認得、必填欄位缺 |
| `StateInvalid` | `state.json` 的 `state` 不是四格之一 |

指示詞的代號（`UnknownDirective`、`EnvironmentVariableMissing`、`ReferenceCycle`…）照
[directives.md §6](directives.md)。

讀驗錯誤＝這一格**根本沒走**，退出碼 1、`state.json` 不動。引擎回錯、工具炸掉這些是
**跑的時候的錯**，下一格重試，不是這張表的。

## 5. 這份規範沒管的事

- **輸入從哪來、回話回給誰**（信箱、aos-user、別的 agent）：不在這份，之後另寫；這裡只知道
  `idle` 會拿到一則 `user` 訊息、`act` 會產出一則回話。
- **等檔案**（引擎或工具晚點才給結果）：之後再說；`wait` 格先留著。
- **怎麼被叫醒、多久走一格、怎麼放進 kernel**：kernel／daemon 的事。
- **aos-agent 的命令列**：另寫（草案在 [thinking/](../../thinking/)）。

## 我自己選的、使用者可以推翻的

1. `system.json` 用 `{"content": "…"}`，不用整則訊息——role 是固定的，沒必要寫。
2. `tools` 併進 `state.json` 後就是一個路徑陣列，沒有 `disabled` 開關：要關就從陣列拿掉。
3. 同名工具直接報錯，不用「後面蓋前面」。
4. `engine.json` 兩種 `kind` 都寫進規範，程式第一版先做 `llm`；兩種都當場等。
5. `llm` 引擎當場等 HTTP 回來——違反「一格不等網路」，第一版先接受。
6. 沒有任何上限與計數（一題幾格、連錯幾次、等多久）——使用者說先只剩 `state`，要管再說。
7. agent 寫回時改的是原始 JSON，不是解完的結果。
8. `engine.json` 還是獨立一份、沒併進 `state.json`——使用者沒叫我併；要併也是一句話的事。
