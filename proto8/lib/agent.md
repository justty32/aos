# agent（`aos_agent.py`＋真的腦 `aos_brain_openai.py`）

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
- **換腦**：agent.json 的 `brain` 換一個 inst TARGET，其他不動。

## 工具＝inst

```jsonc
// agent.json（跟 fsm 同一份；fsm 不認得這幾個 key、會忽略）
"brain": "brain/fake.json",
"tools": {"clock": "tools/clock.json"},     // 名字 → aos-inst TARGET（可接 #/位置，N-35）
"history": "work/history.json",             // 對話檔＝OpenAI messages 陣列；只有方法程式寫它（N-05）
"work": "work/"                             // 放 N-call.json（引數）、N-ret.json（工具的 stdout）

// tools/clock.json：工具自己的 inst，說明放 `_tool`（aos_inst 不認得的 key 一律忽略；不用 _metainfo）
{"argv": ["python3", "tools/clock.py"], "_tool": {"description": "查現在的時間", "parameters": {"type": "object", "properties": {}}}}
```

- 工具的 stdin＝`arguments` 解開的 JSON（寫成 `work/N-call.json`，N＝那時 history 幾則），stdout 最後一份＝結果。
- 回給模型：`{"role": "tool", "tool_call_id": …, "content": "<字串>"}`，content＝`{"code": 工具的結束碼, "result": stdout 最後一份}` 的 JSON 字串，截 8000 字。

## 兩格膠水（`aos_agent.py`）

```
python3 aos_agent.py think AGENT.json      python3 aos_agent.py tool AGENT.json
```

- **think**：讀 history、組請求（`tools` 從各工具 inst 的 `_tool` 來；沒工具就不帶）、蓋 stdin 跑腦（`aos_methods.run_cell`）、把 assistant 訊息接進 history，stdout `{"data": {"content", "tool_calls": [工具名]}}`。不吐 `next`：下一格寫在表上。history 最後已經是 assistant（上一拍接好才被殺）＝不再叫腦。腦結束碼非 0＝`BrainFailed`、回的不是 assistant 訊息＝`BadReply`，這格退出 1（fsm 記 `CellFailed`）。
- **tool**：找最後一則 assistant 還沒回的 `tool_calls`，跑一個、接 tool 訊息，stdout `{"data": {"tool", "result"}}`。

## 邊緣狀況（使用者 10-15 定）

| 情況 | 基礎實作 |
|---|---|
| 工具名不認得 | 回模型一則 tool 訊息「不認得這個工具：名」，不算 fsm 的錯 |
| 一次回好幾個 `tool_calls` | 只跑第一個；其餘各回「基礎實作一次只跑一個，這個沒跑」（OpenAI 要每個 id 都有回才能再問），stderr 警告 `ToolCallsSkipped` |
| 引數不合 schema | 不驗；工具自己報錯（code≠0），照樣回模型 |
| tool 格被殺一半（`prev.interrupted`，N-38） | 不重跑工具，還沒回的全回「被中斷」 |

動工時自己定的（等使用者看）：`arguments` 不是 JSON＝回 `{"code": null, "error": …}` 不跑；工具的 inst 起不來（aos_inst 出錯）同樣回 `{"code": null, "error": …}`；工具 inst 沒寫 `_tool`＝空說明、不收引數。
