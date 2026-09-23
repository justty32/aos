# agent 資料夾規範（第 2 版，**草稿**）

← [proto5 README](../README.md)｜指示詞：[directives.md](directives.md)｜用這個資料夾的程式：[aos-llm-call.md](aos-llm-call.md)（問模型）、[aos-agent.md](aos-agent.md)（走一格）｜排程：[kernel.md](kernel.md)

> 2026-09-23 草稿，取代第 1 版。**程式還沒照這份改**：現在的 `aos_agent_info.py`／`aos_agent.py` 仍照舊版。
> 跟第 1 版比砍掉的：`engine.cpu`、`tool_cpu`、工具的 `_run`、`waits` 的 `mtime`／`any`、`ask-result.json`、`tool-results/`。
> 加上的：`kernel`、`llm`、`tool_pool`。原因：問模型、跑工具全部變成往 kernel `add --once` 的普通工作
> （[kernel.md §2](kernel.md)），agent 不再認識任何 cpu。

一句話：**一個 agent 就是一個資料夾——`info.json` 說它是誰、記憶在哪、工具有哪些、要用哪個 kernel 跟哪個模型；
`state.json` 記走到哪、輸入從哪來、在等哪些回音。**

## 0. 名詞（白話）

| 詞 | 意思 |
|---|---|
| agent 家 | 這個資料夾。檔案裡寫的相對路徑一律從這裡算 |
| 記憶 | `history` 指的那份 OpenAI chat 訊息陣列；問模型時整份送、回來整份寫 |
| 工具 | OpenAI `tools` 陣列的一個元素，多一格 `_meta`（一份 inst）說被叫到時跑什麼 |
| 門（`waits`） | 一張等待表；還有沒到的檔就不走格。誰要 agent 等，誰往表尾加一條 |
| 回音檔 | kernel 家 `K/responses/<名>.json`，一份 once 工作跑完的執行結果（[kernel.md §2](kernel.md)）；agent 等的就是它 |
| 池（`pool`） | kernel 的 cpu 分組標籤（[kernel.md §1.1](kernel.md)）；問模型的工作派去 `llm` 那顆、工具派去一般的 |

## 1. 資料夾長什麼樣

```
agent-bob/
  info.json          _metainfo ＋ 設定（§3）
  state.json         state ＋ input ＋ waits ＋ errors（§4）
  prompts/           慣例：人格、記憶
  tools/             慣例：工具檔
  llm.json           慣例：模型連線設定（aos-llm-call.md §2），也可以指到別處共用
  insts/             aos-agent 產生的工作 inst（每則一檔）
  llm-out/           aos-llm-call 的 stdout（每次問一檔）
  tool-in/ tool-out/ 工具的 arguments 與 stdout（每個 call 一檔）
  log/               慣例：llm 與工具的 stderr
```

- 只有 `info.json`（且 `_metainfo._type` 是 `llm_agent`）是「這是 agent 家」的依據。`_metainfo` 也解指示詞。
- 相對路徑一律相對 agent 家；指到資料夾＝裡面所有 `*.json` 照檔名排序（`.done` 結尾的不算）。
- 誰能讀寫規範不管；慣例 `info.json`、`llm.json`、`prompts/system.json`、`tools/` 是人寫的，其餘是程式寫的。
- 程式寫檔一律 `.tmp` 再 rename；頂層都是嚴格的物件或陣列；不認得的 key 一律忽略。
- `insts/`、`llm-out/`、`tool-in/`、`tool-out/` 是 aos-agent 的工作區，它自己建、自己清（[aos-agent.md §3](aos-agent.md)）。

## 2. 指示詞：`info.json`／`state.json` 解，被指到的檔不解

跟第 1 版一樣：這兩份每一格都解（含 `_metainfo`），中心是 agent 家，`$env` 讀跑那支程式自己的環境；
人格、記憶、工具檔、輸入、回音檔**原樣讀，不解**。程式改寫 `state.json` 的某格時改的是原始 JSON 那一格、其他格原樣抄回，
所以 `state`／`errors`／`waits` 在原始 JSON 裡必須是字面值，頂層不能整份是指示詞。
工具 `_meta` 裡的指示詞是 aos-agent 產生工作 inst 時以 agent 家為中心解掉的（aos-agent.md §3.2）。

## 3. `info.json`

```json
{
  "_metainfo": {"_type": "llm_agent", "_version": 1},
  "system": "prompts/system.json",
  "history": "prompts/history.json",
  "tools": ["tools/base.json"],
  "kernel": "../K",
  "llm": {"config": "llm.json", "model": "small", "params": {"temperature": 0.2}, "pool": "llm"},
  "tool_pool": "default"
}
```

| 鍵 | 型別 | 沒寫時 | 意思 |
|---|---|---|---|
| `_metainfo` | 物件 | 必填 | `_type` 只認 `llm_agent`、`_version` 只認整數 1 |
| `system` | 路徑 | `prompts/system.json` | 人格檔：`{"content": "…"}`；檔不存在＝空字串 |
| `history` | 路徑 | `prompts/history.json` | 記憶檔：訊息陣列；檔不存在＝`[]` |
| `tools` | 路徑陣列 | `[]` | 工具檔，照順序合併；列到的檔一定要在 |
| `kernel` | 路徑 | 必填 | kernel 家 K；aos-agent 往 `K/requests/` 放單、等 `K/responses/` |
| `llm.config` | 路徑 | `llm.json` | 給 aos-llm-call 的連線設定（[aos-llm-call.md §2](aos-llm-call.md)） |
| `llm.model` | 非空字串 | 必填 | llm.json `models` 表裡的代號 |
| `llm.params` | 物件 | `{}` | 組 body 用的模型參數 |
| `llm.pool` | 字串 | `llm` | 問模型的工作派去哪個池 |
| `tool_pool` | 字串 | `default` | 工具的工作派去哪個池 |

型別不對＝`FieldTypeMismatch`（明寫 null 也不合法）；`llm` 缺或內部必填缺＝`LlmInvalid`。沒有欄位吃 `$opt`。
讀驗時只解路徑，不驗 K 是不是 kernel 家、llm.json 對不對——真的送件／真的問模型時才知道。

### 3.1 人格、3.2 記憶

跟第 1 版一字不改：人格 `{"content": 字串}`；記憶是 `user`／`assistant`／`tool` 三種 role 的陣列，
`user`／`tool` 的 `content` 要字串、`tool` 要有 `tool_call_id`、`assistant` 要有字串 `content` 或陣列 `tool_calls`，不合＝`MessageInvalid`。
整份讀、整份寫；記憶長了怎麼辦之後再說。

### 3.3 工具檔：OpenAI tools 陣列 ＋ `_meta` ＋ `_timeout_ms`

```json
[{"type": "function",
  "function": {"name": "sh", "description": "在 agent 家跑一句 shell", "parameters": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}},
  "_meta": {"argv": ["tools/bin/sh-tool"], "stderr": {"$opt": "append", "$val": "log/sh.err"}},
  "_timeout_ms": 60000}]
```

- 頂層不是陣列、元素缺 `type`／`function`／`function.name`、`_meta` 缺或不是物件、合併後同名 → `ToolInvalid`。
- `_meta` 是一份 posix inst（`_metainfo` 可省），**不能寫 `stdin`／`stdout`**（寫了＝`ToolInvalid`）：跑的時候 arguments 走 stdin、結果走 stdout，
  由 aos-agent 接管（aos-agent.md §3.2）。`_meta` 裡的指示詞、相對路徑，中心是 agent 家。
- `_timeout_ms`：可省，正整數，沒寫＝60000；這會變成 kernel `add` 的 `timeout_ms`。
- 送模型前每個元素的 `_` 開頭 key 全拿掉。沒有 `_run`：所有工具都經 kernel 跑，沒有同步模式。

## 4. `state.json`

```json
{"state": "think", "errors": 0, "input": "input.json",
 "waits": ["../K/responses/bob-1790000000000000000-77.json"]}
```

| 鍵 | 型別 | 沒寫時 | 意思 |
|---|---|---|---|
| `state` | `idle`／`think`／`act` | `idle` | 走到哪。沒有 `wait` 這格——等是門，不是狀態 |
| `errors` | 非負字面整數 | `0` | 引擎連敗次數（aos-agent.md §3.4） |
| `input` | 路徑或路徑陣列 | `input.json` | 輸入從哪來，接進記憶後 rename `.done` |
| `waits` | 一條或一條陣列 | 沒寫＝不用等 | 門（§4.2） |

檔不存在＝全預設；存在但壞掉＝`ReadFailed`／`JsonSyntax`。`state` 不是三個之一或不是字面＝`StateInvalid`；其他型別錯＝`FieldTypeMismatch`。

### 4.1 `input`

指到的每個檔：字串→一則 user 訊息；一則訊息物件→原樣；訊息陣列→原樣一串。檔不存在或空陣列＝沒輸入。
清掉＝rename 成 `<原名>.done`。

### 4.2 `waits`

```json
"waits": [
  "../K/responses/bob-1790000000000000000-77.json",
  {"$opt": "consume", "$val": "continue.json"},
  {"$opt": "all", "$val": ["../K/responses/bob-…-0.json", "../K/responses/bob-…-1.json"]}
]
```

- 一條＝路徑字串，或 `{"$opt": 名字|[名字…], "$val": 路徑|[路徑…]}`；不認得的選項＝`UnknownOption`。每一條照樣解指示詞，但整格在原始 JSON 要是字面陣列（aos-agent 按索引劃掉）。
- 只剩三個選項：`exists`（預設；資料夾＝裡面有任何 `*.json`）、`consume`（到了之後 rename `.done`）、`all`（`$val` 陣列全到才算，預設）。
  `mtime`、`any` 拿掉了：agent 等的都是「一個回音檔出現」，用不到。
- **等 kernel 回音的那幾條不要開 `consume`**：回音是 kernel 的家，agent 不准 rename 它，要用 ack（[cpu.md §3.3](cpu.md)）。aos-agent 自己加的條目都遵守這點。

## 5. 共用的錯誤代號

跟第 1 版一樣：`NotAnAgent`、`ReadFailed`／`JsonSyntax`／`NotAnObject`／`NotAnArray`、`MetainfoInvalid`／`UnsupportedVersion`、
`FieldTypeMismatch`、`StateInvalid`；內容的 `MessageInvalid`、`ToolInvalid`；新的 `LlmInvalid`（取代 `EngineInvalid`）。
指示詞的代號照 directives.md §6。

## 6. 這份沒管的

程式做什麼：問模型＝[aos-llm-call.md](aos-llm-call.md)；門、狀態機、送件收回＝[aos-agent.md](aos-agent.md)。
誰把輸入丟進 `input`、回話給誰、agent 自己怎麼被 kernel 反覆跑（就是一個反覆行程，target 指到跑 `aos-agent` 的 inst）：之後再說。

## 7. 我自己選的（等你確認）

1. **模型設定拆成 `llm.json`**，`info.llm.config` 指路徑，可共用。
2. **`llm.pool` 預設 `llm`、`tool_pool` 預設 `default`**——跟 kernel.md §1.1 的範例對得上。
3. **`waits` 砍到三個選項**，`mtime`／`any` 沒人用就拿掉。
4. **工作區四個資料夾**（`insts/`、`llm-out/`、`tool-in/`、`tool-out/`）由 aos-agent 建與清，不進 info。
5. **同步工具拿掉**：一律經 kernel。代價是最快也要等一格 tick 才跑得到。
