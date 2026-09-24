← [agent](README.md)｜[spec 總導航](../README.md)

# 3. `info.json`

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
| `tools` | 路徑陣列 | `[]` | 工具檔（§3.3），照順序合併；列到的檔或資料夾一定要在；元素可寫成 `$opt` 選項物件改名或只挑幾支（[§3.4](tools-opt.md)） |
| `llm.model` | 非空字串 | 必填 | 模型**代號**；真名、endpoint、金鑰在 llm cpu 那邊的 llm.json（[aos-llm.md §2](../aos-llm/config.md)） |
| `llm.params` | 物件 | `{}` | 組 body 用的模型參數 |
| `llm.pool` | 字串 | `llm` | 問模型的工作派去哪個池；K 的 `info.cpus` 裡要有這個池的 cpu，否則 kernel 退件 |
| `llm.timeout_ms` | 非負整數 | 125000 | 問模型那件工作的執行上限（kernel `add` 的 `timeout_ms`，0＝不限）；兩個逾時的分工見 [aos-llm.md §6](../aos-llm/timeouts.md) |
| `tool_pool` | 字串 | `default` | 工具的工作派去哪個池 |
| `tick.pool` | 字串 | `default` | `aos-agent start` 登記反覆行程用的池 |
| `tick.interval_ms` | 非負整數 | 沒寫＝不帶，用 kernel 的預設 | 同上，多久跑一格 |
| `access` | 路徑字串（可用指示詞） | `access.json` | 權限牆檔（[§3.5](access.md)），相對 agent 家；檔不在＝要關牢的工具都不送（`NoAccess`），但**明寫了**卻不在＝`AccessInvalid`（09-24 access round2） |

- 整數欄一律不收 bool。型別不對＝`FieldTypeMismatch`（明寫 `null` 也不合法）；`llm` 缺或 `llm.model` 缺＝`LlmInvalid`。只有 `tools` 的元素吃 `$opt`（[§3.4](tools-opt.md)，09-24 access-impl）；其他位置寫 `$opt`＝`UnknownOption`。
- 讀驗時只解路徑、驗型別，不看 K、不看 llm 池存不存在——真的送件時 kernel 才回。

## 3.1 人格

`{"content": 字串}`。頂層不是物件、`content` 不是字串＝`MessageInvalid`。空字串＝不送 system 訊息。

## 3.2 記憶與 message 驗證

記憶是陣列，元素只能是下面三種 role（`system` 不放記憶裡，在人格檔）。不合＝`MessageInvalid`：

| role | 必須 |
|---|---|
| `user` | `content` 是字串 |
| `tool` | `content` 是字串；`tool_call_id` 是非空字串 |
| `assistant` | `content` 是字串或 `null`；可有 `tool_calls`。`content` 是 `null` 時 `tool_calls` 必須非空 |

`tool_calls`（有寫時）：陣列；每項是物件，`id` 非空字串、`type` 是 `"function"`、`function.name` 非空字串、
`function.arguments` 是字串；同一則裡 `id` 不重複。空陣列＝當作沒寫。其他 key（例如模型多回的欄位）原樣留著、不驗。

**模型回的那一則**另外要求 `role` 是 `assistant`（`aos-llm call` 印之前驗一次、aos-agent 收回時再驗一次，同一套規則）。
整份讀、整份寫；記憶太長怎麼辦之後再說。

## 3.3 工具檔：OpenAI tools 陣列 ＋ `_meta` ＋ `_timeout_ms`

```json
[{"type": "function",
  "function": {"name": "sh", "description": "在 agent 家跑一句 shell",
               "parameters": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}},
  "_meta": {"argv": ["tools/bin/sh-tool"], "stderr": {"$opt": "append", "$val": "log/sh.err"}},
  "_timeout_ms": 60000}]
```

- 每個元素必須：是物件；`type` 等於 `"function"`；`function` 是物件；`function.name` 是非空字串；`function.description` 有寫就要是字串、`function.parameters` 有寫就要是物件；
  `_meta` 是物件；`_timeout_ms` 有寫就要是非負整數（bool 不算）。頂層不是陣列、任一條不合、合併後同名——**工具檔的錯一律 `ToolInvalid`**（不用 `FieldTypeMismatch`；（09-24 試玩 r2 補）檔讀不到或根本不是 JSON 則是更前面的 `ReadFailed`／`JsonSyntax`）。
  （09-24 試玩 r1 補）訊息帶檔的絕對路徑與第幾個元素（從 0 起）；同名則列出兩邊的檔與位置。
  其他 key 原樣送給模型（`_` 開頭的除外），不驗。
- `_meta` 是一份 posix inst（[inst-posix](../inst-posix/README.md)，`_metainfo` 可省），**不能寫 `stdin`／`stdout`**（寫了＝`ToolInvalid`）：
  arguments 走 stdin、結果走 stdout，由 aos-agent 接管。`stderr` 寫 `merge` 可以（跟著 stdout 進結果）。
- `_meta` 的路徑照 inst-posix §3.1 算：**base 是 agent 家**；`cwd` 先解（以 base 為中心，沒寫＝agent 家），
  之後 `stderr`／`exit`、`$ref` 以解出來的 `cwd` 為中心。`argv` 的元素不當路徑改寫（`argv[0]` 照 PATH 找）。
  讀驗 info 時不解 `_meta`；送件時才解，解不過只算那一個 call 跑不起來（aos-agent.md §5.3）。
- `_timeout_ms`：可省，非負整數（bool 不算），沒寫＝60000；這就是 kernel `add` 的 `timeout_ms`。
- （09-24 access-impl）`_jail`：可省，只收 `true`／`false`（別的＝`ToolInvalid`）；`false`＝這支不關牢（[access.md](access.md)）。
- （09-24 access-impl）`tools` 元素的 `as` 改過名的，`function.name` 就是新名字；讀出來每條另帶內部鍵 `_source`（[§3.4](tools-opt.md)）。
- 送模型前每個元素的 `_` 開頭 key 全拿掉。
