# agent（現成格庫 `aos_agent_lib.py`＋當函數 `aos_agent_call.py`＋真的腦 `aos_brain_openai.py`／`aos_brain_ollama.py`）

← [proto8/lib](README.md)｜概念：[CONCEPTS agent](../CONCEPTS/05-agent.md)｜狀態機：[fsm.md](fsm.md)｜demo：[demo/fsm](../demo/fsm/README.md)｜決定：[thinking 10-15 §5](../thinking/2026-10-15-topics/02-agent工具與試146.md#5-agent-的工具與思考介面)

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
- **用量**（10-15）：腦可以在 assistant 訊息頂層多帶 `"usage": {"prompt_tokens", "completion_tokens", "total_tokens"}`，給 LLM kernel 記額度（[kernel.md](kernel.md)）；think 接進 history 前拿掉 `usage`，history 照舊是純 OpenAI 訊息。兩顆真腦都會帶（openai：端點回的 `usage` 照抄；ollama：`prompt_eval_count`＋`eval_count` 換成這個形狀），端點沒回就不帶。
- 出錯：stderr 吐 `{"error": {"code", "msg"}}`（N-29）、結束碼非 0。
- 兩顆腦：demo 的假腦 `demo/fsm/brain/fake.py`（寫死的回覆）、真腦 `aos_brain_openai.py`（POST `<base_url>/chat/completions`，不串流；`base_url` 預設 LiteLLM `http://localhost:4000/v1`、`model` 必填、`api_key_env`＝放金鑰的環境變數名（沒寫＝不帶）、`timeout_ms` 預設 120000；設定從 CONFIG.json 或旗標來，stdin 是請求）。錯誤代號：`HttpError`、`ConnectFailed`、`BadResponse`、`NoApiKey`。
- 第三顆：`aos_brain_ollama.py`（ollama 原生 POST `<base_url>/api/chat`，`stream: false`）。**為什麼不走 ollama 的 `/v1`**：OpenAI 相容那條設不了 `num_ctx`，ollama 會用模型預設的 context、可能吃爆顯存；原生的帶 `options.num_ctx`（預設 4096）與 `keep_alive`（預設 `"30s"`）。旗標 `--base-url`（預設 `http://localhost:11434`，不含 `/api`）、`--model`（必填）、`--num-ctx`、`--keep-alive`、`--timeout-ms`。形狀互翻：送出時 assistant 的 `arguments` 字串→物件、`content: null`→`""`、tool 訊息補 `tool_name`；收回時 `arguments` 物件→字串、沒 id 就編 `call_<亂數>_<n>`。錯誤代號 `HttpError`（模型不支援 tools 時 ollama 回 400「does not support tools」也是這個）、`ConnectFailed`、`BadResponse`。
- **腦只留 `content`／`tool_calls`**（使用者 10-15「模型想的內容丟掉」）：`reasoning_content` 之類想的字一律不收、不存，真腦翻譯時只取這兩樣；不留旁檔。
- **aos 從不依賴模型的思考內容，只算最後的答案**（使用者 10-15：厲害模型的端點如 Claude／GPT 會把思考加密或乾脆不給，說是防蒸餾）：設計、解析、測試都只看 `content`／`tool_calls`。會想的小模型就叫它別想（例 Qwen3 在 system 開頭寫 `/no_think`，[agent 判官](kernel2.md#agent-判官換一行-target)就這樣），免得想太久或把輸出長度耗光、`content` 空掉。
- **換腦**：agent.json 的 `brain` 換一個 inst TARGET，其他不動。
- **10-15 實測 146 ollama**（[thinking §7](../thinking/2026-10-15-topics/02-agent工具與試146.md#7-試-146-ollama小模型)）：gemma3:1b、deepseek-r1:8b 都回 400「does not support tools」，模型沒載進去；腦這層照規矩回 `HttpError`。要在 ollama 上跑工具得換有 tools 能力的模型。**同日試 qwen2.5:14b**（使用者准，[§8](../thinking/2026-10-15-topics/03-試146-qwen與LM-Studio.md#8-試-146-ollamaqwen2514b)）：整圈跑通、`tool_calls` 形狀對，但帶 tools 時回覆語言亂跳（泰文、韓文）。

## 工具＝inst

```jsonc
// agent.json（跟 fsm 同一份；fsm 不認得這幾個 key、會忽略，但會整份當格的 stdin）
"brain": "brain/fake.json",
"tools": {"clock": "tools/clock.json"},     // 名字 → aos-inst TARGET（可接 #/位置，N-35）
"system": "system.md",                      // 選填：系統提示檔（文字／markdown）
"history": "work/history.json",             // 對話檔＝OpenAI messages 陣列；只有方法程式寫它（N-05）
"work": "work/"                             // 放 N-call.json（引數）、N-ret.json（工具的 stdout）

// tools/clock.json：工具自己的 inst，說明放 `_tool`（aos_inst 不認得的 key 一律忽略；不用 _metainfo）
{"argv": ["python3", "tools/clock.py"], "_tool": {"description": "查現在的時間", "parameters": {"type": "object", "properties": {}}}}
```

- **system**：think 每次叫腦，都把檔內容當 `{"role":"system","content":…}` 插在送給腦的 messages 最前面；**不寫進 history**（history 只有 user／assistant／tool），所以改 system.md 下一拍就生效。沒寫 `system`＝不帶；寫了但檔不存在或讀不了＝think 格錯誤 `SystemUnreadable`（N-29）。路徑從格的 cwd 算；內層 fsm 沒寫就從外層 cfg 來（N-40）。
- 工具的 stdin＝`arguments` 解開的 JSON（寫成 `work/N-call.json`，N＝那時 history 幾則），stdout 最後一份＝結果。
- 回給模型：`{"role": "tool", "tool_call_id": …, "content": "<字串>"}`，content＝aos_inst 的結果（N-30：`id`、`code`、`signal`、`timed_out`、`pid`、`ms`、`exit_file`）多一格 `result`（工具 stdout 最後一份）的 JSON 字串，截 8000 字；沒跑成（工具名不認得、引數不是 JSON、inst 起不來、沒輪到、被中斷）＝N-29 形狀 `{"error": {"code", "msg"}}`。（10-15 依 C-48 改，原本是 `{"code", "result"}`）

## 現成格庫（`aos_agent_lib.py`）

```
python3 aos_agent_lib.py think      python3 aos_agent_lib.py tool
```

- 不是 agent 本體（agent＝fsm＋表，不變）；是表裡可以直接拿來用的兩格。檔名：使用者 10-15 說「aos-agent-lib.py」，proto8/lib 的模組一律底線（連字號 import 不了），所以叫 `aos_agent_lib.py`。
- **設定走 stdin**（10-15 使用者選乙；同日依 C-48 改形狀）：fsm 給格的 stdin＝fsm 設定本身多一個 key `fsm_state`（state 窗整份，N-37），`brain`、`tools`、`history`、`work`（與選填的 `system`）就從這份拿，argv 不再指設定檔；stdin 不是物件＝`NoConfig`、退出 1。`fsm_state.running` 為 true＝上一拍被殺一半。相對路徑從格的 cwd 算（沒寫 `cwd` 的格＝跟 fsm 同一個）。巢狀時是內層 fsm 那份，內層沒寫的 key 從外層 cfg 來（N-40：外層 cfg 當預設），所以 demo 的 `think/fsm.json` 只寫表。

- **think**：讀 history、組請求（`tools` 從各工具 inst 的 `_tool` 來；沒工具就不帶）、蓋 stdin 跑腦（`aos_methods.run_cell`）、把 assistant 訊息（拿掉頂層 `usage`）接進 history，stdout `{"data": {"content", "tool_calls": [工具名]}}`。不吐 `next`：下一格寫在表上。history 最後已經是 assistant（上一拍接好才被殺）＝不再叫腦。腦結束碼非 0＝`BrainFailed`（白話＝腦 stderr 的錯誤 `代號: 白話`，腦沒吐才寫結束碼）、回的不是 assistant 訊息＝`BadReply`，這格退出 1；fsm 記 `CellFailed: BrainFailed: HttpError: …`，連錯 `max_fails` 次就停住不再叫腦（[fsm.md](fsm.md)）。
- **tool**：找最後一則 assistant 還沒回的 `tool_calls`，跑一個、接 tool 訊息，stdout `{"data": {"tool", "result"}}`。工具的環境多一個 `AOS_WORK`＝這個 agent 的 work（給 `ask` 放子 agent 的 frame）。
- **route**：看最後一則 assistant，有 `tool_calls`＝`{"next": "tool"}`，否則 `{"next": "idle", "data": {"reply"}}`。單層表用（demo 的 `clerk/`）；名字寫死 tool／idle。
- `brain`、`tools` 的值除了 TARGET，也可以是內嵌一張 inst（`aos_agent_call` 攤開定義時就給這種）。

## 邊緣狀況（使用者 10-15 定）

| 情況 | 基礎實作 |
|---|---|
| 工具名不認得 | 回模型一則 tool 訊息 `{"error": {"code": "UnknownTool", "msg": "不認得這個工具：名"}}`，不算 fsm 的錯 |
| 一次回好幾個 `tool_calls` | 只跑第一個；其餘各回 `{"error": {"code": "Skipped", "msg": "基礎實作一次只跑一個，這個沒跑"}}`（OpenAI 要每個 id 都有回才能再問），stderr 警告 `ToolCallsSkipped` |
| 引數不合 schema | 不驗；工具自己報錯（code≠0），照樣回模型 |
| tool 格被殺一半（`fsm_state.running` 為 true，N-38） | 不重跑工具，還沒回的全回 `{"error": {"code": "Interrupted", …}}` |

動工時自己定的（等使用者看）：`arguments` 不是 JSON＝回 `{"error": {"code": "BadArguments", …}}` 不跑；工具的 inst 起不來（aos_inst 出錯）＝回 aos_inst 的錯（同形狀、原代號）；工具 inst 沒寫 `_tool`＝空說明、不收引數。

## agent 當函數／當工具

程式：`aos_agent_call.py`（10-15）。

概念：[CONCEPTS C-46](../CONCEPTS/05-agent.md)（使用者 10-15 定，概念層；規範慢慢來）｜決定：[thinking 10-15 §11](../thinking/2026-10-15-topics/04-agent當函數.md#11-agent-當函數binding當工具)

三個地方分開：**定義**（`bob/`：agent.json＝fsm 表＋brain、tools、system；呼叫時不寫）、**frame**（像 stack：`history.json`、`state.json`、`work/`、`lock/`；每次呼叫／每個實例一個）、**cwd**（呼叫者在哪）。

```python
bob = aos_agent_call.Agent("bob/agent.json")          # binding
bob.call(frame, history=None, engine_args=None, tools=None, tools_append=None, cwd=None, max_ticks=20)
# → {"reply": 最後一則 assistant 的字, "ticks": 敲了幾拍}；錯丟 CallError
```

- **怎麼做到的**（動工自定，不動 inst／loop 的通則）：前端把定義攤開——表上的格、brain、tools、system（有用指示詞的話也一樣）一律從 bob/ 算，讀成內嵌 inst；這些 inst 沒寫 `cwd` 就在 bob/ 跑（argv 裡的相對路徑也照 bob/ 算）。state、history、work 指進 frame；lock 是 `frame/lock/`，前端拿著整趟（fsm 不開 lock、ctl）。然後在本行程一拍一拍 `aos_fsm.run()`，fsm 吐出 `next` 在 `end` 裡的那份＝做完。
- **history**：給了＝frame 的 history 換成它、刪 frame 的 state（從 start 來）；沒給＝接著 frame 裡的（沒有＝`NoHistory`）。
- **engine_args**：list＝接在腦 inst 的 argv 後（例 `["--model", "x"]`）；dict＝蓋過腦 inst 的 key。
- **tools**（呼叫時的工具＝一等參數，像高階函數傳進去的函數）：給了 `tools`＝整份取代 bob 綁的預設；`tools_append`＝再加；都沒給＝用 bob 綁的。呼叫時給的工具，相對路徑從 cwd 算、沒寫 cwd 就在 cwd 跑。
- **限制**：只攤開最上層的表；格若是內層 fsm（`aos_fsm.py 內層.json`），它在 bob/ 跑，但它自己的 state 不會被指進 frame——當函數用的定義寫成單層表（`think → route → tool`）。

### 當工具：`aos_agent_lib.py ask`

```
python3 aos_agent_lib.py ask [--frame DIR] [--max-ticks N] bob/agent.json      # stdin {"question"} 或 {"history"}
```

- 寫成一張工具 inst（說明照舊放 `_tool`），父 agent 的 tools 放它。每次呼叫＝新對話（history＝`[user 問題]`），除非 stdin 給 `history`。
- frame：`--frame`；沒給＝`$AOS_WORK/ask-<n>/`（父 agent 的 work，tool 格給的；n＝第一個還沒有的號碼，mkdir 搶），再沒有＝`./ask-<n>/`。完整對話留在 frame 給人看，父 agent 只拿到最後一句。
- stdout 一份：成功 `{"reply", "ticks"}` 退 0；失敗 N-29 形狀 `{"error": {"code", "msg"}}`（`MaxTicks` 旁邊多 `partial`）退 1——吐在 stdout，父 agent 的 tool 訊息 `result` 裡看得到。（10-15 依 C-48 改，原本是 `{"error": 代號, "msg"}`）

| 情況 | 結果 |
|---|---|
| 同一個 frame 有人在用（`lock/` 在） | `Busy`；不同 frame 可以同時跑 |
| 敲到 `--max-ticks`（預設 20）還沒到 end | `MaxTicks`，多 `partial`＝最後一則有字的 assistant |
| 子 agent 的格出錯、停住、`max_steps` 到了 | `SubAgentFailed`，msg＝它的 last_error；不重試 |
| 遞迴太深（環境變數 `AOS_ASK_DEPTH` 每層 +1，超過 3） | `TooDeep`，不建 frame |

三道上限：`--max-ticks`、子 agent 自己的 `max_steps`、那張工具 inst 的 `timeout_ms`（demo 的 `tools/clerk.json` 120000；父 agent 的 tool 格 `timeout_ms` 要更大，demo 改 150000）。
