# agent（現成格庫 `aos_agent_lib.py`＋真的腦 `aos_brain_openai.py`／`aos_brain_ollama.py`）

← [proto8/lib](README.md)｜概念：[CONCEPTS agent](../CONCEPTS/05-agent.md)｜狀態機：[fsm.md](fsm.md)｜demo：[demo/fsm](../demo/fsm/README.md)｜決定：[thinking 10-15 §5](../thinking/2026-10-15-topics.md#5-agent-的工具與思考介面)

> **這是實作慣例，還不是規範。** 使用者 10-15 定了方向；等接過一次真的 endpoint、跑順了，再升成 NORMS 的條。

agent＝一份 fsm（idle → thinking → tool → thinking → … → idle）。這裡定兩件事：**思考介面**（換腦只換一個 TARGET）與**工具＝inst**。

## 思考介面（腦）

腦＝一支照 N-12 呼叫的 inst，stdin／stdout 是固定形狀（OpenAI chat completions 的那一塊）：

```jsonc
// stdin：請求
{"messages": [ /* OpenAI chat messages */ ],
 "tools": [{"type": "function", "function": {"name": "clock", "description": "…", "parameters": { /* JSON schema */ }}}]}   // 選填
// stdout 最後一份：OpenAI assistant 訊息
{"role": "assistant", "content": "…或 null", "tool_calls": [            // tool_calls 選填
  {"id": "call_1", "type": "function", "function": {"name": "clock", "arguments": "{}"}}]}   // arguments 是 JSON 字串
```

- 模型要用工具＝走 OpenAI 內建的 `tool_calls`（不是在文字裡吐 JSON）。
- 出錯：stderr 吐 `{"error": {"code", "msg"}}`（N-29）、結束碼非 0。
- 兩顆腦：demo 的假腦 `demo/fsm/brain/fake.py`（寫死的回覆）、真腦 `aos_brain_openai.py`（POST `<base_url>/chat/completions`，不串流；`base_url` 預設 LiteLLM `http://localhost:4000/v1`、`model` 必填、`api_key_env`＝放金鑰的環境變數名（沒寫＝不帶）、`timeout_ms` 預設 120000；設定從 CONFIG.json 或旗標來，stdin 是請求）。錯誤代號：`HttpError`、`ConnectFailed`、`BadResponse`、`NoApiKey`。
- 第三顆：`aos_brain_ollama.py`（ollama 原生 POST `<base_url>/api/chat`，`stream: false`）。**為什麼不走 ollama 的 `/v1`**：OpenAI 相容那條設不了 `num_ctx`，ollama 會用模型預設的 context、可能吃爆顯存；原生的帶 `options.num_ctx`（預設 4096）與 `keep_alive`（預設 `"30s"`）。旗標 `--base-url`（預設 `http://localhost:11434`，不含 `/api`）、`--model`（必填）、`--num-ctx`、`--keep-alive`、`--timeout-ms`。形狀互翻：送出時 assistant 的 `arguments` 字串→物件、`content: null`→`""`、tool 訊息補 `tool_name`；收回時 `arguments` 物件→字串、沒 id 就編 `call_<亂數>_<n>`。錯誤代號 `HttpError`（模型不支援 tools 時 ollama 回 400「does not support tools」也是這個）、`ConnectFailed`、`BadResponse`。
- **換腦**：agent.json 的 `brain` 換一個 inst TARGET，其他不動。
- **10-15 實測 146 ollama**（[thinking §7](../thinking/2026-10-15-topics.md#7-試-146-ollama小模型)）：gemma3:1b、deepseek-r1:8b 都回 400「does not support tools」，模型沒載進去；腦這層照規矩回 `HttpError`。要在 ollama 上跑工具得換有 tools 能力的模型。**同日試 qwen2.5:14b**（使用者准，[§8](../thinking/2026-10-15-topics.md#8-試-146-ollamaqwen2514b)）：整圈跑通、`tool_calls` 形狀對，但帶 tools 時回覆語言亂跳（泰文、韓文）。

## 工具＝inst

```jsonc
// agent.json（跟 fsm 同一份；fsm 不認得這幾個 key、會忽略，但會整份當 stdin 的 cfg 給格）
"brain": "brain/fake.json",
"tools": {"clock": "tools/clock.json"},     // 名字 → aos-inst TARGET（可接 #/位置，N-35）
"history": "work/history.json",             // 對話檔＝OpenAI messages 陣列；只有方法程式寫它（N-05）
"work": "work/"                             // 放 N-call.json（引數）、N-ret.json（工具的 stdout）

// tools/clock.json：工具自己的 inst，說明放 `_tool`（aos_inst 不認得的 key 一律忽略；不用 _metainfo）
{"argv": ["python3", "tools/clock.py"], "_tool": {"description": "查現在的時間", "parameters": {"type": "object", "properties": {}}}}
```

- 工具的 stdin＝`arguments` 解開的 JSON（寫成 `work/N-call.json`，N＝那時 history 幾則），stdout 最後一份＝結果。
- 回給模型：`{"role": "tool", "tool_call_id": …, "content": "<字串>"}`，content＝`{"code": 工具的結束碼, "result": stdout 最後一份}` 的 JSON 字串，截 8000 字。

## 現成格庫（`aos_agent_lib.py`）

```
python3 aos_agent_lib.py think      python3 aos_agent_lib.py tool
```

- 不是 agent 本體（agent＝fsm＋表，不變）；是表裡可以直接拿來用的兩格。檔名：使用者 10-15 說「aos-agent-lib.py」，proto8/lib 的模組一律底線（連字號 import 不了），所以叫 `aos_agent_lib.py`。
- **設定走 stdin**（10-15 使用者選乙）：fsm 給格的 stdin 是 `{"state", "step", "prev", "cfg"}`（N-37），`brain`、`tools`、`history`、`work` 從 `cfg` 拿，argv 不再指設定檔；沒 `cfg`＝`NoConfig`、退出 1。相對路徑從格的 cwd 算（沒寫 `cwd` 的格＝跟 fsm 同一個）。巢狀時 `cfg` 是內層 fsm 那份，四個 key 在內層設定裡 `$ref` 到外層（demo 的 `think/fsm.json` 就這樣寫，N-40）。

- **think**：讀 history、組請求（`tools` 從各工具 inst 的 `_tool` 來；沒工具就不帶）、蓋 stdin 跑腦（`aos_methods.run_cell`）、把 assistant 訊息接進 history，stdout `{"data": {"content", "tool_calls": [工具名]}}`。不吐 `next`：下一格寫在表上。history 最後已經是 assistant（上一拍接好才被殺）＝不再叫腦。腦結束碼非 0＝`BrainFailed`（白話＝腦 stderr 的錯誤 `代號: 白話`，腦沒吐才寫結束碼）、回的不是 assistant 訊息＝`BadReply`，這格退出 1；fsm 記 `CellFailed: BrainFailed: HttpError: …`，連錯 `max_fails` 次就停住不再叫腦（[fsm.md](fsm.md)）。
- **tool**：找最後一則 assistant 還沒回的 `tool_calls`，跑一個、接 tool 訊息，stdout `{"data": {"tool", "result"}}`。

## 邊緣狀況（使用者 10-15 定）

| 情況 | 基礎實作 |
|---|---|
| 工具名不認得 | 回模型一則 tool 訊息「不認得這個工具：名」，不算 fsm 的錯 |
| 一次回好幾個 `tool_calls` | 只跑第一個；其餘各回「基礎實作一次只跑一個，這個沒跑」（OpenAI 要每個 id 都有回才能再問），stderr 警告 `ToolCallsSkipped` |
| 引數不合 schema | 不驗；工具自己報錯（code≠0），照樣回模型 |
| tool 格被殺一半（`prev.interrupted`，N-38） | 不重跑工具，還沒回的全回「被中斷」 |

動工時自己定的（等使用者看）：`arguments` 不是 JSON＝回 `{"code": null, "error": …}` 不跑；工具的 inst 起不來（aos_inst 出錯）同樣回 `{"code": null, "error": …}`；工具 inst 沒寫 `_tool`＝空說明、不收引數。
