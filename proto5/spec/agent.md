# agent 資料夾規範（第 2 版草稿（第 2 輪））

← [proto5 README](../README.md)｜指示詞：[directives.md](directives.md)｜用這個資料夾的程式：[aos-agent.md](aos-agent.md)（走一格、登記）、[aos-llm-call.md](aos-llm-call.md)（問模型）｜排程：[kernel.md](kernel.md)

> 2026-09-23 草稿；2026-09-24 照 [審查報告](../notes/2026-09-23-rearch/review-agent1-report.md)「定稿前必改」與使用者三件裁決改成第 2 輪。
> **程式還沒照這份改**：現行 `aos_agent_info.py`／`aos_agent.py` 仍是舊架構。
> 調度者裁決在下一節，已拍板的前提在 §7。

一句話：**agent 資料夾保存設定、對話記憶與跨次執行的進度，讓 aos-agent 每次被叫都能接著做。**
`info.json` 說它是誰、記憶在哪、有哪些工具、用哪個模型代號；`state.json` 記走到哪、輸入從哪來、
外人加的門，以及「手上這一批送出去的工作」（`batch`）。

## 調度者裁決（第 2 輪，實作層級）

1. 在途工作的身分只記在 `state.batch`（§4.3），`waits` 只剩外人的門；aos-agent 不再往 `waits` 加自己的條目。
2. `info.kernel`、`info.llm.config` 拿掉：K 由 `AOS_K` 給、送件時記進 `batch.kernel`；模型表在 llm cpu 那邊。
3. 新增 `info.tick`（`pool`、`interval_ms`）給 `aos-agent start` 登記用。
4. 四個工作資料夾併成一個 `work/`，檔名 `<工作名>.inst.json`／`.in`／`.out`，清檔一條規則。
5. `waits` 的選項只剩 `consume`；`exists`、`all` 可寫但就是預設（陣列＝全到才算）。
6. 程式自己寫的 `state` 各格（除了 `input`）必須是字面值，不吃指示詞。
7. 記憶的 message 驗證寫死在 §3.2，aos-llm-call 與 aos-agent 共用同一套。

## 0. 名詞（白話）

| 詞 | 意思 |
|---|---|
| agent 家 | 這個資料夾。檔案裡寫的相對路徑一律從這裡算 |
| 記憶 | `info.history` 指的那份 OpenAI chat 訊息陣列；問模型時整份送、收回時整份寫 |
| 工具 | OpenAI `tools` 陣列的一個元素，多一格 `_meta`（一份 inst）說被叫到時跑什麼 |
| 門（`waits`） | 外人要 agent 停下來等的表；表裡還有沒到的檔，這一格就不走 |
| 當批（`batch`） | 一次送出去、要一起收回的工作：`think` 是一則問模型，`act` 是同一則 assistant 的全部 tool_calls |
| 工作名 | 一件送去 kernel 的工作的名字，同時是 kernel 行程名、request 檔名（加 `.json`）、`work/` 裡的檔名開頭（[aos-agent.md §0](aos-agent.md)） |
| 池（`pool`） | kernel 的 cpu 分組標籤；工作派往標籤相同的某顆工作 cpu（[kernel.md §1.1](kernel.md)） |

## 1. 資料夾長什麼樣

```
agent-bob/
  info.json      人寫的設定（§3）
  state.json     程式寫的進度（§4）；檔不在＝全預設
  tick.json      aos-agent start 寫的：kernel 反覆跑的那份 inst（aos-agent.md §11）
  prompts/       慣例：人格、記憶
  tools/         慣例：工具檔
  input.json     慣例：輸入（§4.1）
  work/          aos-agent 的工作區：<工作名>.inst.json、.in、.out
  log/           llm.err、agent.err，以及工具自己指定的
```

- 只有 `info.json`（且 `_metainfo._type` 是 `llm_agent`）是「這是 agent 家」的依據。
- 相對路徑一律相對 agent 家；路徑指到資料夾＝裡面所有 `*.json`（`.done` 結尾的不算）照檔名排序。
- 慣例上 `info.json`、`prompts/system.json`、`tools/` 是人寫的，其餘是程式寫的；規範不管權限。
- 頂層都是嚴格的物件或陣列；不認得的 key 一律忽略。
- **寫檔的兩種做法**（別混）：agent 家自己的檔（`state.json`、記憶、`tick.json`、`work/` 的 inst 與 `.in`）用同目錄
  `.tmp` 再 `rename`；投進 kernel 家 `K/requests/` 的 request 與 ack 用 [cpu.md §3.1](cpu.md) 的唯一 `.tmp`＋`link`。
  `work/*.out` 是工作 inst 的 stdout 重導向產物，不保證原子，只在那件工作的回音到了之後才讀（aos-agent.md §6）。
- `work/` 由 aos-agent 建、由 aos-agent 清（清的條件在 aos-agent.md §10）。

## 2. 指示詞：`info.json`／`state.json` 解，被指到的檔不解

- `info.json` 每次讀都整份解指示詞（含 `_metainfo`），中心是 agent 家，`$env` 讀跑那支程式自己的環境。
- `state.json` 只有 `input` 那格解指示詞；`waits` 每條照樣解（中心 agent 家），但 `waits` 本身在原始 JSON 要是字面單條或字面陣列；
  其他格（`state`、`errors`、`batch`、`intake`、`consuming`、`sweep`）必須是字面值，寫了指示詞＝`FieldTypeMismatch`。
  程式改寫 `state.json` 時只改自己那幾格，`input` 原樣抄回；頂層整份不能是指示詞。
- 人格、記憶、工具檔、輸入、回音檔、`work/` 的檔**原樣讀、不解**。
- 工具 `_meta` 裡的指示詞由 aos-agent 送件時解掉（[aos-agent.md §5.3](aos-agent.md)），用的是**跑 aos-agent 那顆 cpu** 的環境。
- **info.json 裡 aos-llm-call 也會讀的欄位**（`system`、`history`、`tools`、`llm.model`、`llm.params`）不要用 `$env`：
  aos-agent 跟 aos-llm-call 跑在不同的 cpu、環境可能不同，會解成兩個值（例如記憶寫一份、問模型讀另一份）。規範不擋，後果自負。

## 3. `info.json`

```json
{
  "_metainfo": {"_type": "llm_agent", "_version": 1},
  "system": "prompts/system.json",
  "history": "prompts/history.json",
  "tools": ["tools/base.json"],
  "llm": {"model": "small", "params": {"temperature": 0.2}, "pool": "llm", "timeout_ms": 125000},
  "tool_pool": "default",
  "tick": {"pool": "default", "interval_ms": 1000}
}
```

| 鍵 | 型別 | 沒寫時 | 意思 |
|---|---|---|---|
| `_metainfo` | 物件 | 必填 | `_type` 只認 `llm_agent`（不合＝`NotAnAgent`）、`_version` 只認整數 1（bool 不算；不合＝`UnsupportedVersion`）；缺欄位＝`MetainfoInvalid` |
| `system` | 路徑 | `prompts/system.json` | 人格檔（§3.1）；檔不存在＝空字串 |
| `history` | 路徑 | `prompts/history.json` | 記憶檔（§3.2）；檔不存在＝`[]` |
| `tools` | 路徑陣列 | `[]` | 工具檔（§3.3），照順序合併；列到的檔一定要在 |
| `llm.model` | 非空字串 | 必填 | 模型**代號**；真名、endpoint、金鑰在 llm cpu 那邊的 llm.json（[aos-llm-call.md §2](aos-llm-call.md)） |
| `llm.params` | 物件 | `{}` | 組 body 用的模型參數 |
| `llm.pool` | 字串 | `llm` | 問模型的工作派去哪個池；K 的 `info.cpus` 裡要有這個池的 cpu，否則 kernel 退件 |
| `llm.timeout_ms` | 非負整數 | 125000 | 問模型那件工作的執行上限（kernel `add` 的 `timeout_ms`，0＝不限）；兩個逾時的分工見 [aos-llm-call.md §6](aos-llm-call.md) |
| `tool_pool` | 字串 | `default` | 工具的工作派去哪個池 |
| `tick.pool` | 字串 | `default` | `aos-agent start` 登記反覆行程用的池 |
| `tick.interval_ms` | 非負整數 | 沒寫＝不帶，用 kernel 的預設 | 同上，多久跑一格 |

- 整數欄一律不收 bool。型別不對＝`FieldTypeMismatch`（明寫 `null` 也不合法）；`llm` 缺或 `llm.model` 缺＝`LlmInvalid`。沒有欄位吃 `$opt`。
- 讀驗時只解路徑、驗型別，不看 K、不看 llm 池存不存在——真的送件時 kernel 才回。

### 3.1 人格

`{"content": 字串}`。頂層不是物件、`content` 不是字串＝`MessageInvalid`。空字串＝不送 system 訊息。

### 3.2 記憶與 message 驗證

記憶是陣列，元素只能是下面三種 role（`system` 不放記憶裡，在人格檔）。不合＝`MessageInvalid`：

| role | 必須 |
|---|---|
| `user` | `content` 是字串 |
| `tool` | `content` 是字串；`tool_call_id` 是非空字串 |
| `assistant` | `content` 是字串或 `null`；可有 `tool_calls`。`content` 是 `null` 時 `tool_calls` 必須非空 |

`tool_calls`（有寫時）：陣列；每項是物件，`id` 非空字串、`type` 是 `"function"`、`function.name` 非空字串、
`function.arguments` 是字串；同一則裡 `id` 不重複。空陣列＝當作沒寫。其他 key（例如模型多回的欄位）原樣留著、不驗。

**模型回的那一則**另外要求 `role` 是 `assistant`（aos-llm-call 印之前驗一次、aos-agent 收回時再驗一次，同一套規則）。
整份讀、整份寫；記憶太長怎麼辦之後再說。

### 3.3 工具檔：OpenAI tools 陣列 ＋ `_meta` ＋ `_timeout_ms`

```json
[{"type": "function",
  "function": {"name": "sh", "description": "在 agent 家跑一句 shell",
               "parameters": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}},
  "_meta": {"argv": ["tools/bin/sh-tool"], "stderr": {"$opt": "append", "$val": "log/sh.err"}},
  "_timeout_ms": 60000}]
```

- 頂層不是陣列、元素缺 `type`／`function`／`function.name`、`_meta` 缺或不是物件、合併後同名 → `ToolInvalid`。
- `_meta` 是一份 posix inst（[inst-posix](inst-posix.md)，`_metainfo` 可省），**不能寫 `stdin`／`stdout`**（寫了＝`ToolInvalid`）：
  arguments 走 stdin、結果走 stdout，由 aos-agent 接管。`stderr` 寫 `merge` 可以（跟著 stdout 進結果）。
- `_meta` 的路徑照 inst-posix §3.1 算：**base 是 agent 家**；`cwd` 先解（以 base 為中心，沒寫＝agent 家），
  之後 `stderr`／`exit`、`$ref` 以解出來的 `cwd` 為中心。`argv` 的元素不當路徑改寫（`argv[0]` 照 PATH 找）。
  讀驗 info 時不解 `_meta`；送件時才解，解不過只算那一個 call 跑不起來（aos-agent.md §5.3）。
- `_timeout_ms`：可省，非負整數（bool 不算），沒寫＝60000；這就是 kernel `add` 的 `timeout_ms`。
- 送模型前每個元素的 `_` 開頭 key 全拿掉。

## 4. `state.json`

```json
{"state": "act", "errors": 0, "input": "input.json", "waits": [],
 "batch": {"kind": "act", "kernel": "/abs/K", "base_len": 12, "sent": true,
           "calls": [{"name": "aw-bob-1790000000000000000-77-0", "tool_call_id": "call_a", "tool": "sh",
                      "done": null, "acked": false},
                     {"name": null, "tool_call_id": "call_b", "tool": "nope",
                      "done": {"content": "沒有這個工具：nope"}, "acked": true}]},
 "intake": null, "consuming": [], "sweep": [{"kernel": "/abs/K", "name": "aw-bob-1789999999000000000-70-0"}]}
```

| 鍵 | 型別 | 沒寫時 | 意思 |
|---|---|---|---|
| `state` | `idle`／`think`／`act` | `idle` | 走到哪。沒有 `wait` 這格——等是門或當批，不是狀態 |
| `errors` | 非負整數 | `0` | 問模型連敗次數（aos-agent.md §9） |
| `input` | 路徑或路徑陣列（可用指示詞） | `input.json` | 輸入從哪來（§4.1） |
| `waits` | 字面單條或字面陣列 | 沒寫＝不用等 | 外人的門（§4.2） |
| `batch` | 物件或 `null` | `null` | 當批（§4.3） |
| `intake` | 物件或 `null` | `null` | 收輸入做到一半的紀錄（§4.4） |
| `consuming` | 字串陣列 | `[]` | 已經從門劃掉、還沒 rename `.done` 的檔（§4.4） |
| `sweep` | 物件陣列 | `[]` | 等著清 `work/` 檔的工作名（§4.4） |

檔不存在＝全預設；存在但壞掉＝`ReadFailed`／`JsonSyntax`／`NotAnObject`。`state` 不是三個之一＝`StateInvalid`；其他型別錯＝`FieldTypeMismatch`。

### 4.1 `input`

指到的每個檔：字串→一則 user 訊息；一則訊息物件→原樣；訊息陣列→原樣一串（都照 §3.2 驗）。檔不存在或空陣列＝沒輸入。
收完＝rename 成 `<原名>.done`（已有同名 `.done` 就蓋掉）。**寫輸入的人不要蓋掉還沒被收的檔**：要連發就讓 `input`
指到資料夾、每則用新檔名，不然「讀了舊的、rename 掉新的」這個窗口擋不住。

### 4.2 `waits`

```json
"waits": [
  "continue.json",
  {"$opt": "consume", "$val": "continue.json"},
  {"$opt": "all", "$val": ["a.json", "b.json"]}
]
```

- 原始 JSON 裡是字面單條或字面陣列；讀進來一律當條目列表，程式寫回一律寫陣列。沒寫或 `[]`＝沒有門。
- 一條＝路徑字串，或選項物件 `{"$opt": 名字|[名字…], "$val": 路徑|[路徑…]}`（`$opt` 必寫：只有 `$val` 的物件在指示詞機制裡是 `UnknownDirective`）；`$val` 可再是指示詞，解完要是字串或非空字串陣列，否則 `FieldTypeMismatch`。
- 選項：`consume`（到了之後 rename `.done`）；`exists`、`all` 是預設、寫了也一樣；其他名字＝`UnknownOption`、重複＝`UnknownOption`。
- 「到了」：檔存在；資料夾裡有任何 `*.json`（`.done` 不算）。`$val` 是陣列＝全部到了才算這條到了。
- `consume` 指到資料夾＝到了那一刻把裡面所有 `*.json` 都 rename `.done`。
- 這張表只給外人用（人要它暫停、別的程式要它等某個檔）；aos-agent 自己只會加一種條目：連敗暫停的 `continue.json`（aos-agent.md §9）。
  kernel 家的回音**不要**寫進 `waits`，更不要開 `consume`：回音是 kernel 的家，只能 ack（[cpu.md §3.3](cpu.md)）。

### 4.3 `batch`：當批紀錄

在途工作的身分只記在這裡。`null`＝手上沒有送出去的工作。

| 鍵 | 型別 | 意思 |
|---|---|---|
| `kind` | `think`／`act` | 問模型／跑工具 |
| `kernel` | 絕對路徑 | 送去哪個 kernel 家；收回、ack、清檔都用這個 K，不看當下的 `AOS_K` |
| `base_len` | 非負整數 | 建批那一刻記憶的長度；收回時記憶寫成「前 `base_len` 則＋這批的訊息」（所以重做不會重複接） |
| `sent` | 布林 | `false`＝還在送（崩了要重跑送件步驟）；`true`＝該送的都送了 |
| `calls` | 陣列 | 每個 call 一筆，順序＝接回記憶的順序。`think` 恰好一筆 |
| `calls[].name` | 字串或 `null` | 工作名；`null`＝這個 call 本地就結束了、沒送 |
| `calls[].tool_call_id`、`tool` | 字串 | 只有 `act` 有：對應 assistant 的 `tool_calls[i].id` 與 `function.name` |
| `calls[].done` | 物件或 `null` | 這個 call 的結果，已讀驗完、持久了；`null`＝還沒收 |
| `calls[].acked` | 布林 | 回音已 ack（或本來就沒有回音） |

`done` 的形狀：`act` 是 `{"content": 給模型看的字串}`；`think` 是 `{"ok": true}`（答案留在 `work/<名>.out`）
或 `{"fail": 白話原因, "count": 布林}`（`count` 說算不算一次連敗）。怎麼算在 aos-agent.md §6。

### 4.4 `intake`、`consuming`、`sweep`

- `intake`：`{"base_len": 整數, "files": [路徑…], "messages": [訊息…]}`。idle 收輸入時先記這筆再動記憶與輸入檔，
  崩了下次照這筆做完（aos-agent.md §8）。`files` 是解好的絕對路徑。
- `consuming`：絕對路徑陣列。門的 `consume` 條目到了，先在同一次寫裡把它從 `waits` 劃掉、把要 rename 的檔記到這裡，再 rename（aos-agent.md §3）。
- `sweep`：`[{"kernel": K, "name": 工作名}…]`。批結清時把這批的工作名放進來；確定那件工作在 K 裡結束了才刪它的 `work/` 檔（aos-agent.md §10）。

## 5. 錯誤代號

讀驗：`NotAnAgent`（沒有 `info.json` 或 `_type` 不對）、`ReadFailed`／`JsonSyntax`／`NotAnObject`／`NotAnArray`、
`MetainfoInvalid`／`UnsupportedVersion`、`FieldTypeMismatch`、`StateInvalid`、`LlmInvalid`；
內容：`MessageInvalid`、`ToolInvalid`；指示詞的代號照 [directives.md §6](directives.md)。
收回時記憶跟當批對不上（例如人改了記憶）＝`HistoryChanged`（aos-agent.md §7）。

## 6. 這份沒管的

程式做什麼：走一格、登記＝[aos-agent.md](aos-agent.md)；問模型＝[aos-llm-call.md](aos-llm-call.md)。
`aos-agent init <template>`、`pause`／`continue`、`tools`／`llms` 子命令、`say`、一個 agent 一顆專屬 cpu：這輪不做，
使用者的構想在 [thinking/aos-agent.md](../../thinking/aos-agent.md)、[thinking/2026-09-23.md](../../thinking/2026-09-23.md)。
記憶太長；明確的 `fail` 狀態（[backlog/agent-fail-state.md](../backlog/agent-fail-state.md)）。

## 7. 已拍板的前提（使用者定的，不重問）

1. **沒有同步工具**：問模型、跑工具都是往 kernel `add --once` 的普通工作，agent 只認識 kernel。
   取捨：最快也要等一格 tick 才跑得到；同一批的工具可能平行跑，有先後依賴的要合成一個工具或拆成兩輪讓模型分次叫。
2. **agent 先進現有的池**：登記＝`aos-kernel add` 一個反覆行程（aos-agent.md §11），池與間隔從 `info.tick` 拿；K 由 `AOS_K` 給。
3. **llm.json 放 llm cpu 那邊**（cpu 的環境＝工作的環境）：agent 的 `info.llm` 只剩 `model`、`params`、`pool`、`timeout_ms`。
