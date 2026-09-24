# agent 資料夾規範（第 2 版，2026-09-24 定稿（astra 三輪審查＋第 4 輪補 3 條）；程式未跟）

← [proto5 README](../README.md)｜指示詞：[directives.md](directives.md)｜用這個資料夾的程式：[aos-agent.md](aos-agent.md)（走一格、登記）、[aos-llm-call.md](aos-llm-call.md)（問模型）｜排程：[kernel.md](kernel.md)

> 2026-09-23 草稿；2026-09-24 照 [審查報告](../notes/2026-09-23-rearch/review-agent1-report.md)「定稿前必改」與使用者三件裁決改成第 2 輪；同日照 [第 2 輪審查](../notes/2026-09-23-rearch/review-agent2-report.md) E／D／B／C 改成第 3 輪；照 [第 3 輪審查](../notes/2026-09-23-rearch/review-agent3-report.md) D 節補 3 條（第 4 輪）後定稿。
> **程式還沒照這份改**：現行 `aos_agent_info.py`／`aos_agent.py` 仍是舊架構。
> 調度者裁決在下一節，已拍板的前提在 §7。

一句話：**agent 資料夾保存設定、對話記憶與跨次執行的進度，讓 aos-agent 每次被叫都能接著做。**
`info.json` 說它是誰、記憶在哪、有哪些工具、用哪個模型代號；`state.json` 記走到哪、輸入從哪來、
外人加的門，以及「手上這一批送出去的工作」（`batch`）。

## 調度者裁決（第 2～3 輪，實作層級）

1. 在途工作的身分只記在 `state.batch`（§4.3），`waits` 只剩外人的門；aos-agent 不再往 `waits` 加自己的條目。
2. `info.kernel`、`info.llm.config` 拿掉：K 由 `AOS_K` 給、送件時記進 `batch.kernel`；模型表在 llm cpu 那邊。
3. 新增 `info.tick`（`pool`、`interval_ms`）給 `aos-agent start` 登記用。
4. 四個工作資料夾併成一個 `work/`，檔名 `<工作名>.inst.json`／`.in`／`.out`，清檔一條規則。
5. `waits` 的選項只剩 `consume`；`exists`、`all` 可寫但就是預設（陣列＝全到才算）。
6. 程式自己寫的 `state` 各格（除了 `input`）必須是字面值，不吃指示詞。
7. 記憶的 message 驗證寫死在 §3.2，aos-llm-call 與 aos-agent 共用同一套。
8. （第 3 輪）**每次消費一個身分**：輸入與 consume 的檔先 rename 到唯一的封存名 `<原名>.<消費 id>.done`、再讀；state 記的是「原路徑→封存名」對，恢復只認封存名，不再碰原路徑上可能新投遞的檔（§4.4）。

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
- 相對路徑一律相對 agent 家。**只有** `input`、`tools` 的元素、`waits` 的路徑可以指到資料夾＝裡面所有 `*.json`（`.done` 結尾的不算）照檔名排序；
  `system`、`history` 必須是單一檔案（指到資料夾＝`FieldTypeMismatch`），因為記憶要整份寫回同一個檔。
- 慣例上 `info.json`、`prompts/system.json`、`tools/` 是人寫的，其餘是程式寫的；規範不管權限。
- 頂層都是嚴格的物件或陣列；不認得的 key 一律忽略。
- **寫檔的兩種做法**（別混）：agent 家自己的檔（`state.json`、記憶、`tick.json`、`work/` 的 inst 與 `.in`）用同目錄
  `.tmp` 再 `rename`；投進 kernel 家 `K/requests/` 的 request 與 ack 用 [cpu.md §3.1](cpu.md) 的唯一 `.tmp`＋`link`。
  `work/*.out` 是工作 inst 的 stdout 重導向產物，不保證原子，只在那件工作的回音到了之後才讀（aos-agent.md §6）。
- `work/` 由 aos-agent 建、由 aos-agent 清（清的條件在 aos-agent.md §10）。

## 2. 指示詞：`info.json`／`state.json` 解，被指到的檔不解

- `info.json` 每次讀都解指示詞（含 `_metainfo`），中心是 agent 家，`$env` 讀跑那支程式自己的環境。**頂層與 `llm` 那格必須是字面物件**（不是＝`FieldTypeMismatch`；各欄位的值可以是指示詞），
  這樣 aos-llm-call 才能只挑自己要的欄位解。
- `state.json` 只有 `input` 那格解指示詞；`waits` 每條照樣解（中心 agent 家），但 `waits` 本身在原始 JSON 要是字面單條或字面陣列；
  其他格（`state`、`errors`、`batch`、`intake`、`consuming`、`sweep`）必須是字面值，寫了指示詞＝`FieldTypeMismatch`。
  程式改寫 `state.json` 時只改自己那幾格，`input` 原樣抄回；頂層整份不能是指示詞。
- 人格、記憶、工具檔、輸入、回音檔、`work/` 的檔**原樣讀、不解**。
- 工具 `_meta` 裡的指示詞由 aos-agent 送件時解掉（[aos-agent.md §5.3](aos-agent.md)），用的是**跑 aos-agent 那顆 cpu** 的環境。
- **兩邊都讀的欄位**：aos-llm-call 只解驗 `_metainfo`、`system`、`history`、`tools`、`llm.model`、`llm.params` 這六格（[aos-llm-call.md §3](aos-llm-call.md)），
  其他格（`tick`、`tool_pool`、`llm.pool`、`llm.timeout_ms`…）它不碰，用 `$env` 只要 agent 那顆 cpu 有就行。
  這六格若用 `$env`，**兩顆 cpu 都得有那個變數、而且值相同**——少一邊就問不了模型，值不同會記憶寫一份、問模型讀另一份。建議這六格不用 `$env`。

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
| `system` | 檔案路徑 | `prompts/system.json` | 人格檔（§3.1）；檔不存在＝空字串 |
| `history` | 檔案路徑 | `prompts/history.json` | 記憶檔（§3.2）；檔不存在＝`[]`；aos-agent 整份原子重寫這個檔 |
| `tools` | 路徑陣列 | `[]` | 工具檔（§3.3），照順序合併；列到的檔或資料夾一定要在 |
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

- 每個元素必須：是物件；`type` 等於 `"function"`；`function` 是物件；`function.name` 是非空字串；`function.description` 有寫就要是字串、`function.parameters` 有寫就要是物件；
  `_meta` 是物件；`_timeout_ms` 有寫就要是非負整數（bool 不算）。頂層不是陣列、任一條不合、合併後同名——**工具檔的錯一律 `ToolInvalid`**（不用 `FieldTypeMismatch`）。
  其他 key 原樣送給模型（`_` 開頭的除外），不驗。
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
| `consuming` | 物件陣列 | `[]` | 已經從門劃掉、還沒搬到封存名的檔（§4.4） |
| `sweep` | 物件陣列 | `[]` | 等著清 `work/` 檔的工作名（§4.4） |

檔不存在＝全預設；存在但壞掉＝`ReadFailed`／`JsonSyntax`／`NotAnObject`。`state` 不是三個之一＝`StateInvalid`；其他型別錯＝`FieldTypeMismatch`。

### 4.1 `input`

指到的每個檔：字串→一則 user 訊息；一則訊息物件→原樣；訊息陣列→原樣一串（都照 §3.2 驗）。檔不存在或空陣列＝沒輸入。
收法：先把檔 rename 到唯一封存名 `<原名>.<消費 id>.done`、**再從封存名讀**（aos-agent.md §8）。所以原路徑一空出來，寫輸入的人就可以再投一份同名檔，
不會被上一次的恢復吞掉。仍要遵守的一條：**不要蓋掉還沒被收的檔**（原路徑還在就是還沒收）——蓋掉的那份本來就讀不到。
封存檔 agent 不清，人自己清——但**還被 `state.json` 的 `intake`／`consuming` 引用的封存檔不准清、不准搬**（它是「這次已經搬過」的憑據，清了恢復會把原路徑上的新檔當成舊的搬走）；
等那筆引用解除（`intake` 回 null、`consuming` 清空）之後才能清。

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
- 選項：`consume`（到了之後 rename 到唯一封存名 `<原名>.<消費 id>.done`）；`exists`、`all` 是預設、寫了也一樣；其他名字＝`UnknownOption`、重複＝`UnknownOption`。
- 「到了」：檔存在；資料夾裡有任何 `*.json`（`.done` 不算）。`$val` 是陣列＝全部到了才算這條到了。
- `consume` 指到資料夾＝到了那一刻把裡面所有 `*.json` 各自 rename 到自己的封存名。
- 加門的人要確定那個檔**現在不在**，不然門一加就開（agent 不替人分辨新舊訊號）。
- 這張表只給外人用（人要它暫停、別的程式要它等某個檔）；aos-agent 自己只會加一種條目：連敗暫停的 `continue-<批 id>.json`，每次名字都不同（aos-agent.md §9）。
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

- **消費 id**：`<epoch ns>-<pid>`，每次收輸入、每次門劃掉 consume 條目各取一個新的；封存名 `<原名>.<消費 id>.done` 因此永不重複。
- `intake`：`{"id": 消費 id, "base_len": 整數, "files": [{"src": 原路徑, "dst": 封存名}…]}`，都是絕對路徑。idle 收輸入時先記這筆、再搬檔、
  再從 `dst` 讀、再寫記憶；崩了下次照這筆做完（aos-agent.md §8）。
- `consuming`：`[{"src": 原路徑, "dst": 封存名}…]`。門的 `consume` 條目到了，先在同一次寫裡把它從 `waits` 劃掉、把這些對記到這裡，再搬（aos-agent.md §3）。
- 搬的規則（兩處共用）：`dst` 已在＝搬過了，**不碰 `src`**（那可能是新投的另一份）；`dst` 不在、`src` 在＝rename；兩個都不在＝略過。
  這條規則成立的前提：**被引用中的 `dst` 沒人動**（§4.1）。要放棄某一對（例如壞輸入），得先 `aos-agent stop`、等行程消失，**在 `state.json` 裡把那一對從 `intake.files`／`consuming` 拿掉**，
  之後才能動那個 `dst`；只刪 `dst` 不改 state，恢復會回頭去搬 `src`（aos-agent.md §8）。
- `sweep`：`[{"kernel": K, "name": 工作名}…]`。批結清時把這批的工作名放進來；確定那件工作在 K 裡結束了才刪它的 `work/` 檔（aos-agent.md §10）。

## 5. 錯誤代號

讀驗：`NotAnAgent`（沒有 `info.json` 或 `_type` 不對）、`ReadFailed`／`JsonSyntax`／`NotAnObject`／`NotAnArray`、
`MetainfoInvalid`／`UnsupportedVersion`、`FieldTypeMismatch`、`StateInvalid`、`LlmInvalid`；
內容：`MessageInvalid`、`ToolInvalid`；指示詞的代號照 [directives.md §6](directives.md)。
收回時記憶長度或尾巴跟當批對不上＝`HistoryChanged`（aos-agent.md §7；它不偵測前綴被等長改寫）。

## 6. 這份沒管的

程式做什麼：走一格、登記＝[aos-agent.md](aos-agent.md)；問模型＝[aos-llm-call.md](aos-llm-call.md)。
`aos-agent init <template>`、`pause`／`continue`、`tools`／`llms` 子命令、`say`、一個 agent 一顆專屬 cpu：這輪不做，
使用者的構想在 [thinking/aos-agent.md](../../thinking/aos-agent.md)、[thinking/2026-09-23.md](../../thinking/2026-09-23.md)。
記憶太長；明確的 `fail` 狀態（[backlog/agent-fail-state.md](../backlog/agent-fail-state.md)）。
**日常 CLI 還沒完**：照這三份做完，家要人手動建、回話要自己看記憶檔（aos-agent.md §13）。

## 7. 已拍板的前提（使用者定的，不重問）

1. **沒有同步工具**：問模型、跑工具都是往 kernel `add --once` 的普通工作，agent 只認識 kernel。
   取捨：最快也要等一格 tick 才跑得到；同一批的工具可能平行跑，有先後依賴的要合成一個工具或拆成兩輪讓模型分次叫。
2. **agent 先進現有的池**：登記＝`aos-kernel add` 一個反覆行程（aos-agent.md §11），池與間隔從 `info.tick` 拿；K 由 `AOS_K` 給。
3. **llm.json 放 llm cpu 那邊**（cpu 的環境＝工作的環境）：agent 的 `info.llm` 只剩 `model`、`params`、`pool`、`timeout_ms`。
