# agent 資料夾規範（第 1 版，**草稿**）

← [proto5 README](../README.md)｜跑工具與引擎靠 [inst-posix.md](inst-posix.md)；指示詞（[directives.md](directives.md)）只在明講的地方用

> **這是草稿，還在跟使用者一步一步改**；不記修訂記錄。原則（使用者定的）：**先規劃檔案架構、
> 分配好每個檔在幹嘛，最後真的有需要再用指示詞輔助**。所以這份規範裡的路徑就是**普通的路徑
> 字串**，不是 `$ref`；全文只有一個地方准用指示詞（§2.7 的 `api_key`）。
> 沒拍板的地方我先照自己的想法填滿，好讓使用者有東西可以改；每一節都獨立、好抽換。

一句話：**一個 agent 就是一個資料夾**；資料夾裡每個檔各管一件事——是 agent、走到哪
（`state.json`）、對模型說什麼（`prompt.json`＋`prompts/`）、能用什麼（`tools.json`＋`tools/`）、
用什麼想（`engine.json`）、跟外面怎麼通信（`inbox/`／`outbox/`）。前五塊就是 bot 模型：system
prompt、history、tools、thinking engine、agent state。

---

## 1. 資料夾長什麼樣

```
agent-bob/
  state.json           _metainfo（認出這是 agent）＋ 狀態機走到哪（agent 寫）
  prompt.json          對模型說的話從哪兩個檔來
  prompts/
    system.json        人格（system prompt）
    history.json       記憶（對話史，agent 寫）
  tools.json           工具清單：用哪幾份工具檔、關掉哪些
  tools/
    base.json          一份工具檔＝一組工具
    team.json
  engine.json          思考引擎的設定
  wait.json            引擎晚點才給的結果落在這（誰在等就等這個檔）
  inbox/<來源>/*.json  收到的信（沒讀的）
  inbox/<來源>/read/   讀過的信
  outbox/NNNN.json     它自己說的話（agent 寫）
  .aos/inst.json       放進 kernel 用的：叫 aos-agent 跑這個資料夾一格
```

- 只有 `state.json` 是**認出「這是 agent 資料夾」**的依據（有它、而且 `_metainfo._type` 是 `agent`）。
- 檔案裡寫的路徑，**一律相對於 agent 資料夾**（不是相對於寫它的那個檔）；絕對路徑照字面。
- **誰寫誰**：人寫 `prompt`／`prompts/system`／`tools`／`tools/*`／`engine`／`.aos/inst`；
  agent 只寫 `state.json`（只動 `state` 那格，`_metainfo` 原樣抄回）、`prompts/history.json`、
  `outbox/`、`wait.json`（讀完刪掉）、還有把信搬進 `inbox/*/read/`。這樣人的設定檔永遠不會被程式改掉。
- agent 寫檔一律先寫 `.tmp` 再 rename，別人永遠不會讀到寫一半的檔。
- 每個檔的頂層都是嚴格的物件或陣列（各節有寫）；**不認得的 key 一律忽略**。

## 2. 每個檔的形狀

### 2.1 `state.json`：是 agent、走到哪（agent 寫）

```json
{
  "_metainfo": {"_type": "agent", "_version": 1},
  "state": "idle"
}
```

| 鍵 | 型別 | 沒寫時 | 意思 |
|---|---|---|---|
| `_metainfo` | 物件 | **必填** | `_type` 只認 `"agent"`、`_version` 只認整數 `1`；規則同 [inst-posix.md §1](inst-posix.md)。跟 inst 不同的是必填：這是新格式、沒有舊檔要相容，而且這就是「這是 agent 資料夾」的記號 |
| `state` | `idle`／`think`／`wait`／`act` | `idle` | 四格之一（§3） |

- 就這兩個 key。名字＝資料夾名，不另外寫；上限、計數之類的都不放，需要再說。
- agent 每格結束改寫 `state`，`_metainfo` 原樣抄回。`state` 不是四格之一 → `StateInvalid`。

### 2.2 `prompt.json`：對模型說的話從哪來

```json
{
  "system":  "prompts/system.json",
  "history": "prompts/history.json"
}
```

- 兩個值都是**路徑字串**（相對於 agent 資料夾）。沒有 `prompt.json` ＝上面這份預設；只寫一個就另一個用預設。
- `system` 指的檔：人格。`history` 指的檔：記憶（agent 寫）。

### 2.3 `prompts/system.json`：人格

```json
{"content": "你是個簡潔、會用工具的助手。"}
```

- `content`：字串，就是 system prompt 本文；沒有這個檔＝空字串（不送 system 訊息）。
- 內容**原樣**，不解指示詞、不做模板；裡面的 `${x}` 就是字面。

### 2.4 `prompts/history.json`：記憶（agent 寫）

一個陣列，一則就是 OpenAI chat 的一則訊息：

```json
[
  {"role": "user",      "content": "看看資料夾裡有什麼"},
  {"role": "assistant", "content": null, "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "sh", "arguments": "{\"cmd\":\"ls\"}"}}]},
  {"role": "tool",      "tool_call_id": "c1", "content": "state.json\nprompt.json\n..."},
  {"role": "assistant", "content": "裡面有 state.json、prompt.json…"}
]
```

- `role` 只認 `user`／`assistant`／`tool`；`system` 不放這裡（每次組請求時從 `system.json` 補在最前面）。
- `user`／`tool` 的 `content` 要是字串；`tool` 一定要有 `tool_call_id`；`assistant` 至少有 `content` 或 `tool_calls` 其中一個。不合 → `MessageInvalid`。
- 沒有這個檔＝`[]`。
- 內容**原樣**，不解指示詞（模型回的 JSON 裡有 `$` 開頭的 key 也不會被誤認）。
- 整份讀、整份寫；記憶長了怎麼辦之後再說（先跟 proto4-7 一樣）。

### 2.5 `tools.json`：用哪幾份工具檔

```json
{
  "files": ["tools/base.json", "tools/team.json"],
  "disabled": ["sh"]
}
```

| 鍵 | 型別 | 沒寫時 | 意思 |
|---|---|---|---|
| `files` | 路徑陣列 | `[]` | 要載入的工具檔，順序＝送給模型的順序 |
| `disabled` | 名字陣列 | `[]` | 先關掉的工具：不送模型、模型叫了也當「沒這個工具」。關在這裡不關在工具檔，因為工具檔可能是共用／複製來的，人的取捨記在自己的清單 |

- 沒有 `tools.json` ＝沒有工具。
- 所有檔載完後**同名工具＝`ToolInvalid`**（不默默蓋掉，寫錯一眼看得到）。
- `aos-agent tools ls|add|remove|enable|disable`（[thinking/aos-agent.md](../../thinking/aos-agent.md)）改的就是這份檔。

### 2.6 `tools/*.json`：一份工具檔＝一組工具

一個陣列，一個元素一個工具：

```json
[
  {
    "name": "sh",
    "description": "在 agent 資料夾執行一句 shell 指令",
    "parameters": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]},
    "run": {"argv": ["tools/bin/sh-tool"], "stderr": "tools/log/sh.err"},
    "timeout_ms": 60000
  },
  {
    "name": "say",
    "description": "回一句話給對方（寫進 outbox）",
    "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}
  }
]
```

| 鍵 | 型別 | 沒寫時 | 意思 |
|---|---|---|---|
| `name` | 字串 | **必填** | 工具名，模型就用這個叫它。只准 `[A-Za-z0-9_-]` |
| `description`、`parameters` | 字串、物件 | `""`、`{"type":"object"}` | 照 OpenAI function 那套原樣送給模型；`parameters` 是 JSON schema，本文不驗它裡面 |
| `run` | 物件 | 不寫＝內建工具 | **一份 posix inst**（[inst-posix.md](inst-posix.md) 整體形狀，`_metainfo` 可省）。跑工具＝照它跑一次 |
| `timeout_ms` | 整數 | `60000` | 跑超過就砍（照 inst 的逾時規則），結果算工具錯誤 |

`run` 的約定：

- **參數 JSON 從 stdin 進去、結果從 stdout 出來**（結果是純文字，整段當 `tool` 訊息的 `content`）。
  所以 `run` 裡**不准寫 `stdin`／`stdout`**（寫了＝`ToolInvalid`），其他欄位（`stderr`／`exit`／`cwd`／`envs`）照 inst 規則。
- `run` 的 base（inst 的「家」）＝agent 資料夾；沒寫 `cwd` 就在 agent 資料夾跑。
- 退出碼非 0 ＝工具錯誤：`content` 是「工具 sh 失敗（exit 1）：」＋stdout 前段，模型自己看著辦；不算 agent 的錯。
- `run` 沒寫＝**內建工具**：agent 程式自己實作，名字對得上才算（第一版只有 `say`）；對不上＝`ToolInvalid`。

### 2.7 `engine.json`：用什麼想

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
| `posix` | `run`（必；一份 posix inst，規則同工具的 `run`：stdin 進、stdout 出、不准寫 `stdin`／`stdout`）、`timeout_ms`（預設 60000） | 引擎是外面一支程式。以後「規則」「別的 agent」「kernel 的 LLM 排程」都走這條，格式不用改 |

- **`api_key` 是全文唯一准用指示詞的地方**：不想把金鑰寫進檔就寫 `{"$env": "NAME"}`（只認 `$env`）。
  變數不在＝`EngineInvalid`（設定壞就不跑，不降級）。
- `posix` 引擎的 stdin／stdout 協定：
  - stdin 收一份請求：`{"messages": [system, ...history], "tools": [工具表]}`（跟 chat/completions 的 body 同形）。
  - stdout 回兩種之一：
    - `{"message": {"role": "assistant", ...}}`——當場想好了。
    - `{"wait": true}`——結果晚點才有：引擎（或它交代的別人）之後把 `{"message": {...}}`（或
      `{"error": "白話"}`）寫到 agent 資料夾的 **`wait.json`**；agent 進 `wait` 格等這個檔。檔名固定，
      所以 `state.json` 不用記「在等哪個檔」。
  - 兩種都不是、或退出碼非 0 → 這次「想」算錯（下一格重試，不是讀驗錯誤）。
- `kind` 不認得、必填欄位缺 → `EngineInvalid`。

### 2.8 `inbox/`／`outbox/`：信

一封信一個檔，`{"from": "user", "time": "2026-09-21T11:30:00", "content": "看看資料夾裡有什麼"}`：

- **來源就是 `inbox/` 底下的資料夾名**（`inbox/user/`、`inbox/alice/`）；沒讀的直接放在裡面，讀過搬進 `read/`。
- agent 一次只收**最舊的一封**（檔名排序），整封當一則 `user` 訊息接進記憶：`content` 前面加 `[來源] `（來源是 `user` 就不加）。
- `outbox/NNNN.json`（四位數遞增）＝它自己說的話：`{"time": "…", "content": "…"}`；內建工具 `say` 跟「沒有 `tool_calls` 的 assistant 回話」都寫這裡。
- `aos-user say|listen|talk` 就是對這兩個資料夾讀寫（[thinking/aos-user.md](../../thinking/aos-user.md)）；信的形狀跟 proto4-7 一樣。

### 2.9 `.aos/inst.json`：放進 kernel 用的

```json
{"argv": ["aos-agent", "."]}
```

一份普通的 posix inst，叫 aos-agent 跑這個資料夾**一格**；`cwd` 沒寫就是 agent 資料夾（inst 的家）。
`aos-agent start`＝把它交給 kernel 登記、`stop`＝撤掉（[thinking/aos-agent.md](../../thinking/aos-agent.md)）。

## 3. 四格

照 [24-agent.md §25](../../proto4/notes/24-agent.md) 使用者那組。每叫一次 aos-agent 只走一格：

| 格 | 只做什麼 | 下一格 |
|---|---|---|
| `idle` | 沒事。`inbox/` 有沒讀的信就收最舊的一封進記憶（搬進 `read/`） | 有信 `think`，沒信留 `idle`（退出碼 101） |
| `think` | 組請求交給 `engine`：當場拿到訊息→接進記憶；拿到 `wait`→去等 | 拿到 `act`，要等 `wait`，錯了留 `think`（下一格重試） |
| `wait` | 只認一個檔：`wait.json` 出現了就讀進來當引擎結果、刪掉它；沒出現就退出讓 CPU | 到了 `act`（`error` 就留 `think` 重試），沒到留 `wait`（退出碼 101） |
| `act` | 看記憶最後那則 assistant：有 `tool_calls` 就逐一跑工具（每個結果一則 `tool` 訊息）；沒有就把 `content` 寫進 outbox | 跑了工具 `think`，回了話 `idle` |

- 退出碼：這格做了事＝0；在等（`idle` 沒信、`wait` 沒到）＝101；讀驗錯誤（§4）＝1；用法錯＝2。
  100（收工）之後再說。
- 一題走幾格、連錯幾次要不要停：先不管；要管的時候再決定記在哪。

## 4. 錯誤代號（讀／驗階段）

`str(e)`＝「代號: 白話」，訊息裡一定說是哪個檔：

| 代號 | 什麼時候 |
|---|---|
| `NotAnAgent` | 沒有 `state.json`、或它的 `_metainfo._type` 不是 `agent` |
| `ReadFailed`／`JsonSyntax`／`NotAnObject`／`NotAnArray` | 某個檔讀不到／不是 JSON／頂層型別不對 |
| `MetainfoInvalid`／`UnsupportedType`／`UnsupportedVersion` | `state.json` 的 `_metainfo` 不合 §2.1 |
| `FieldTypeMismatch` | 某格型別不對 |
| `MessageInvalid` | `history.json` 裡某一則不合 §2.4 |
| `ToolInvalid` | 工具缺 `name`、名字不合法、同名、`run` 不是合法 inst、`run` 寫了 `stdin`／`stdout`、內建工具名字對不上 |
| `EngineInvalid` | `engine.json` 的 `kind` 不認得、必填欄位缺、`api_key` 的 `$env` 變數不在 |
| `StateInvalid` | `state.json` 的 `state` 不是四格之一 |
| `MailInvalid` | 信不是物件、缺 `content` |

讀驗錯誤＝這一格**根本沒走**，退出碼 1、`state.json` 不動。引擎回錯、工具炸掉這些是
**跑的時候的錯**，下一格重試，不是這張表的。

## 5. 這份規範沒管的事

- **怎麼被叫醒、多久走一格**：kernel／daemon 的事，這裡只放一份 `.aos/inst.json`。
- **aos-agent／aos-user 的命令列**：另寫（草案在 [thinking/](../../thinking/)）。
- **多個 agent 怎麼互相寫信**：`from` 跟 `inbox/<來源>/` 已經留了位置，怎麼找到對方的資料夾（通訊錄）之後再說。

## 我自己選的、使用者可以推翻的

1. `system.json` 用 `{"content": "…"}`，不用整則訊息——role 是固定的，沒必要寫。
2. 工具的 enable／disable 記在 `tools.json` 的 `disabled`，工具檔不動。
3. 同名工具直接報錯，不用「後面蓋前面」。
4. `engine.json` 兩種 `kind` 都寫進規範，程式第一版先做 `llm`；`posix` 的 `{"wait": true}`＋固定的
   `wait.json` 是為了讓 `wait` 格有東西可等、又不用在 `state.json` 記路徑（kernel 的 LLM 排程就包成這種）。
5. `llm` 引擎當場等 HTTP 回來——違反「一格不等網路」，第一版先接受，要嚴格就只用 `posix`。
6. 信箱寫進這份規範（§2.8），因為沒有它 bot 沒有輸入；形狀照 proto4-7。
7. 沒有任何上限與計數（一題幾格、連錯幾次、等多久）——使用者說先只剩 `state`，要管再說。
