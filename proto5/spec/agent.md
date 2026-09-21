# agent.json 規範：agent 狀態（第 1 版，**草稿**）

← [proto5 README](../README.md)｜建立在 [directives.md](directives.md)（指示詞）與 [inst-posix.md](inst-posix.md)（跑程式）之上

> **這是草稿。** 使用者要我先草擬一版，之後一步一步一起修。裡面每個決定都還沒拍板；
> 我自己拿不定、需要他決定的地方集中在最後的「待拍板」。已經定案的東西（bot 模型的
> 五塊、四個狀態）是從 [proto4/notes/24-agent.md](../../proto4/notes/24-agent.md) §25 與
> [proto2](../../proto2/README.md)／[proto4-7](../../proto4-7/README.md) 的實作整理來的。

一句話：**一個 agent 就是一個資料夾，資料夾裡一份 `agent.json`，把 bot 模型的五塊寫清楚**——
人格（`system`）、記憶（`history`）、工具（`tools`）、思考引擎（`engine`）、狀態機走到哪
（`state`）。每一塊都能用指示詞從別的檔拿（`$ref`），所以「一份檔」在磁碟上通常是好幾份：
設定的部份寫死在 `agent.json`，會一直變的部份（記憶、狀態）各自一個檔。

---

## 1. `_metainfo`

```json
{"_metainfo": {"_type": "agent", "_version": 1}, ...}
```

跟 inst 的規則一樣（[inst-posix.md §1](inst-posix.md)），只有一點不同：**`_metainfo` 必填**，
沒寫不會默認成 agent——這是新格式、沒有舊檔要相容，讓讀的人一眼分得出這份 JSON 是 inst 還是
agent。`_type` 只認 `"agent"`、`_version` 只認整數 `1`。

## 2. 整體形狀

```json
{
  "_metainfo": {"_type": "agent", "_version": 1},
  "name":    "bob",
  "system":  "你是個簡潔、會用工具的助手",
  "history": {"$ref": "history.json"},
  "tools":   [
    {"$ref": "tools/sh/tool.json"},
    {"$ref": "tools/say/tool.json"}
  ],
  "engine":  {"kind": "llm", "endpoint": "http://127.0.0.1:1234/v1", "model": "qwen/qwen3-1.7b"},
  "state":   {"$ref": "state.json"}
}
```

- 嚴格一個 JSON 物件；不認得的頂層 key 一律忽略（跟 inst 一樣）。
- 任何一格都可以是指示詞；指示詞機制照 [directives.md](directives.md)，本文不重講。
- **中心路徑（`$ref` 找檔的地方）＝agent 資料夾**（`agent.json` 所在的資料夾）。

## 3. 五塊 ＋ 名字

| 欄位 | 型別 | 沒寫時 | 誰寫它 | 意思 |
|---|---|---|---|---|
| `name` | 字串 | 資料夾名 | 人 | 這個 agent 叫什麼；給 LLM 請求命名、給信箱當 `from` 用 |
| `system` | 字串 | `""` | 人 | 人格／系統提示。整段字串；要放在別的檔就 `$ref` 一份 JSON（見待拍板 ①） |
| `history` | 訊息陣列 | `[]` | **agent** | 記憶：OpenAI messages 形狀的陣列（見 3.1）。`system` **不放這裡**，每次組請求時另外補在最前面 |
| `tools` | 工具陣列 | `[]` | 人 | 這個 agent 能用的工具（見 3.2） |
| `engine` | 物件 | **必填** | 人 | 思考引擎：拿「system＋history＋tools」進去、吐一則 assistant 訊息出來的東西（見 3.3） |
| `state` | 物件 | 初始狀態（見 3.4） | **agent** | 狀態機走到哪、在等什麼、錯了幾次 |

「誰寫它」那一欄是重點：**人寫的是設定，agent 寫的是進度**。agent 只會改寫 `history` 跟
`state`；`system`／`tools`／`engine` 它只讀。

### 3.1 `history`：訊息

一則訊息就是 OpenAI chat 的一則：

```json
{"role": "user",      "content": "看看資料夾裡有什麼"}
{"role": "assistant", "content": null, "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "sh", "arguments": "{\"cmd\":\"ls\"}"}}]}
{"role": "tool",      "tool_call_id": "c1", "content": "agent.json\nhistory.json\n..."}
{"role": "assistant", "content": "裡面有 agent.json、history.json…"}
```

- `role` 只認 `user`／`assistant`／`tool`；`system` 不准出現在這裡（人格在 `system` 欄）。
- 不合形狀（缺 `role`、`tool` 沒 `tool_call_id`…）→ `MessageInvalid`。
- 使用者來信怎麼變成一則 `user` 訊息（前面加不加 `[user]`、整封進還是只通知）是 agent
  程式的事，不是格式的事（見 §6）。

### 3.2 `tools`：工具

一個工具＝「給模型看的說明」＋「真的要跑時怎麼跑」：

```json
{
  "name": "sh",
  "description": "在 agent 資料夾執行一句 shell 指令",
  "parameters": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]},
  "run": {"argv": ["tools/sh/run"]}
}
```

- `name`／`description`／`parameters` 照 OpenAI function 那套原樣送給模型（`parameters` 是
  JSON schema，本文不驗它裡面）。
- **`run` 就是一份 posix inst**（[inst-posix.md](inst-posix.md) 的整體形狀，`_metainfo` 可省
  ＝posix v1）：跑工具＝照那份 inst 跑一次。約定：**參數 JSON 從 stdin 進去、結果從 stdout 出來**，
  所以 `run` 裡的 `stdin`／`stdout` 由 agent 程式接管（寫了也會被蓋掉，見待拍板 ③）；`stderr`／
  `exit`／`cwd`／`envs` 照 inst 規則。`run` 的 base（inst 的「家」）＝agent 資料夾。
- `run` 沒寫 → 這是**內建工具**（例如 `say`，由 agent 程式自己實作，名字對得上才算）。
- 同名工具兩個 → `ToolInvalid`；缺 `name` 也是。
- `enabled: false` 可以先關掉一個工具不送模型（對應 `aos-agent tools disable`）。

### 3.3 `engine`：思考引擎

「思考」＝拿目前的 system＋history＋tools 去換一則 assistant 訊息回來。誰來換，由 `kind` 決定：

| `kind` | 其他欄位 | 意思 |
|---|---|---|
| `llm` | `endpoint`、`model`、`params`（可省）、`api_key`（可省，通常寫 `{"$env": "…"}`） | 直接打 OpenAI 相容的 chat/completions。**這一版先只有這種**，agent 程式自己送 HTTP |
| `posix` | `run`（一份 posix inst） | 引擎是一支外面的程式：請求 JSON 從 stdin 進去、assistant 訊息 JSON 從 stdout 出來（跟工具同一個約定）。以後「引擎是規則」「引擎是另一個 agent」「引擎是 kernel 的 LLM 排程」都走這條，不用改格式 |

`kind` 不認得 → `EngineInvalid`；該 kind 必填的欄位缺了也是。

### 3.4 `state`：狀態機

```json
{
  "state": "idle",
  "epoch": 0,
  "question": 0,
  "step": 0,
  "wait": null,
  "errors": 0,
  "last_error": null
}
```

| 欄位 | 型別 | 意思 |
|---|---|---|
| `state` | `idle`／`think`／`wait`／`act` | 四格（下面） |
| `epoch` | 整數 | reset 幾次了；LLM 請求名靠它不撞舊單 |
| `question` | 整數 | 第幾題（每收到一封新的使用者信加一） |
| `step` | 整數 | 這一題走了幾格（`idle`／`wait` 的格不算） |
| `wait` | `null` 或 `{"path": "…", "since": step, "give_up": N}` | 現在在等哪個檔出現；`give_up` 格之後放棄 |
| `errors` | 整數 | 連續錯幾次 |
| `last_error` | `null` 或字串 | 最後一次錯的白話 |

四格照 [24-agent.md §25](../../proto4/notes/24-agent.md) 使用者那組：

| 格 | 只做什麼 | 下一格 |
|---|---|---|
| `idle` | 沒事。有新的事（一封信）就接進 `history` | 有事 `think`，沒事留 `idle` |
| `think` | 決定下一步：把 system＋history＋tools 交給 `engine`。引擎是同步的（HTTP）就當場拿到；是要等的（丟給 kernel）就登記 `wait` | 拿到 `act`，要等 `wait` |
| `wait` | 只認「等哪個檔」，不管是模型、工具、還是別人的信。檔到了拿結果；沒到就退出讓 CPU | 到了 `act`，沒到留 `wait`，放棄 `idle`（記一次錯） |
| `act` | 分派：assistant 訊息有 `tool_calls` 就跑工具（結果接進 `history`，`role: tool`）；沒有就當回話，寫 outbox | 跑了工具 `think`，回了話 `idle` |

`state` 不合（`state` 不是四個之一、`wait` 形狀不對…）→ `StateInvalid`。

## 4. 寫回去：agent 改 `history`／`state` 時寫到哪

`history` 跟 `state` 在 `agent.json` 裡多半是 `{"$ref": "xxx.json"}`。agent 要改它們時：

- 那一格是 **整份檔的 `$ref`**（沒有 `$at`、`$ref` 非空）→ 寫回那個檔（整份覆蓋）。
- 那一格是**字面寫在 `agent.json` 裡**（沒用指示詞）→ 寫回 `agent.json` 那一格，其他格原樣。
- 其他情況（`$ref` 帶 `$at`、`$fmt`、`$env`、巢狀 `$ref`）→ 讀得到、但**不能寫**：agent 一啟動就
  拒絕（`NotWritable`），不要跑到一半才發現寫不回去。
- 一律先寫 `.tmp` 再 rename，別人永遠不會讀到寫一半的檔。

## 5. 錯誤代號（讀／驗階段）

跟 inst 一樣，`str(e)`＝「代號: 白話」：

| 代號 | 什麼時候 |
|---|---|
| `ReadFailed`／`JsonSyntax`／`NotAnObject` | 同 inst |
| `MetainfoInvalid` | 沒有 `_metainfo`、不是物件、缺 `_type`／`_version` |
| `UnsupportedType`／`UnsupportedVersion` | `_type` 不是 `"agent"`／`_version` 不是 `1` |
| `FieldTypeMismatch` | 某格解完型別不對（`system` 要字串、`history` 要陣列、`tools` 要陣列、`engine`／`state` 要物件） |
| `MessageInvalid` | `history` 裡某一則不合 3.1 |
| `ToolInvalid` | 某個工具缺 `name`、重名、`run` 不是合法 inst（inst 自己的代號會包在訊息裡） |
| `EngineInvalid` | `kind` 不認得、或該 kind 必填的欄位缺了 |
| `StateInvalid` | `state` 不合 3.4 |
| `NotWritable` | `history`／`state` 那一格寫不回去（§4） |

指示詞的代號（`ReferenceCycle`…）照 [directives.md §6](directives.md)。

## 6. 這份規範沒管的事

- **信箱**（`inbox/`／`outbox/`、信的形狀、誰把信變成 `user` 訊息）：那是 agent 程式跟
  aos-user 之間的約定，`agent.json` 只描述 bot 本體。
- **怎麼被叫醒、多久走一格**：kernel／inst 的事。agent 資料夾裡放一份 inst.json 叫 aos-agent
  跑自己，跟 proto4-7 一樣。
- **退出碼的約定**（100／101）：agent 程式跟 kernel 的約定。

## 待拍板（我拿不定、要使用者決定）

1. **`system` 想放純文字檔怎麼辦？** `$ref` 只讀 JSON。現在得寫成 `{"$ref": "system.json", "$at": "/content"}`。
   要不要在指示詞機制加一個 `$text`（讀純文字檔、整檔當字串）？那是 directives.md 的修改。
2. **`_metainfo` 必填**（我的提議，跟 inst 不同）——還是也給預設？
3. **工具的 `run` 是一份 inst**，但 `stdin`／`stdout` 被 agent 接管。要不要乾脆規定 `run` 不准寫
   這兩格（寫了＝`ToolInvalid`），免得有人寫了以為有效？
4. **`engine` 這一版只做 `llm`（直接打 HTTP）**，`posix` 那條先寫在格式裡但程式不做——還是一開始
   就兩條都做？（proto4-7 走的是 kernel 的 LLM 排程，那條在這裡就是 `posix` 引擎包一層。）
5. **`history` 整份讀寫**：記憶長了每格都整檔重寫。現在先不管（proto4-7 也是這樣），要不要
   先留一個「`history` 可以是資料夾、一則一檔」的位置？
6. **`state.wait` 只認「等哪個檔」**——這是 24-agent.md 的方向。同步的 HTTP 引擎在 `think` 就當場
   拿到、不經過 `wait`，四格裡 `wait` 只有 `posix` 引擎與慢工具會用到。這樣可以嗎？
7. `tools` 裡工具**通常會 `$ref` 到 `tools/<名字>/tool.json`**，那 `run` 裡的相對路徑（`argv[0]`）
   以誰為中心——agent 資料夾（現在寫的）還是 `tool.json` 所在的資料夾？

我自己再讀一遍挖到的邊緣狀況（也要決定）：

8. **`history`／`state` 根本沒寫**時，agent 第一次寫回去要寫到哪？照 §4 的邏輯是「字面」那條
   ＝寫進 `agent.json` 本身；但這樣一個原本只有設定的 `agent.json` 會開始被 agent 改寫。要不要規定
   「沒寫＝預設寫到 `history.json`／`state.json`」，讓 `agent.json` 永遠是人的？
9. **`tools` 陣列裡每個元素是 `$ref`**（常態），改工具的 `enabled` 時（`aos-agent tools disable`）
   要寫回哪份檔——`tool.json` 還是 `agent.json` 那個元素？跟 §4 同一個問題，但 `tools` 是人寫的、
   不是 agent 寫的，所以改的人是 CLI 不是狀態機。
10. **`history` 的 `$ref` 讀的時候會經過指示詞解析**：如果 `history.json` 裡某則訊息的 `content`
    剛好是一個 `$` 開頭 key 的物件（模型回了 JSON），會被誤當指示詞。要不要規定 `history` 只解
    最外層那一格、裡面的訊息**不解指示詞**（原樣）？`system` 同理——人格文字裡有 `${x}` 不該被動。
11. **`engine.api_key` 用 `$env`**：agent 每格重讀 `agent.json`，環境變數不在＝`EnvironmentVariableMissing`
    ＝整個 agent 讀不起來。這是我們要的（設定壞就不跑）還是該降級成「引擎壞、其他照走」？
