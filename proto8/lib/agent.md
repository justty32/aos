# agent（定義資料夾＋現成格庫 `aos_agent_lib.py`＋真的腦 `aos_brain_openai.py`／`aos_brain_ollama.py`）

← [proto8/lib](README.md)｜概念：[CONCEPTS agent](../CONCEPTS/05-agent.md)｜狀態機：[fsm.md](fsm.md)｜demo：[demo/fsm](../demo/fsm/README.md)｜決定：[thinking 10-15 §5](../thinking/2026-10-15-topics/02-agent工具與試146.md#5-agent-的工具與思考介面)

> **這是實作慣例，還不是規範。** 使用者 10-15 定了方向；等接過一次真的 endpoint、跑順了，再升成 NORMS 的條。

agent＝一個定義資料夾：fsm 表＋各狀態跑的 inst（C-50；intake → thinking → route → tool → thinking → … → done）。這裡定三件事：**思考介面**（換腦只換一個 TARGET）、**工具＝inst**、**agent 當函數／當工具**（定義資料夾＋frame，C-46）。

葉子一律寫指令名（C-50）：PATH 前面接 `proto8/bin`，`aos agent think`、`aos brain openai`、`aos loop` 等就找得到（`proto8/bin/aos` 是薄入口，`aos <名>`＝`python3 lib/aos_<名>.py`；跟 C++ 的 aos 執行檔同名不相干，誰先在 PATH 上用誰）。demo 自己的腳本走 `demo/bin/aos-demo`（`aos-demo fsm/brains/fake.py`＝從 demo 資料夾算的路徑，跟 cwd 無關；其他指令照跑、環境多 `AOS_DEMO`＝demo 資料夾）。

## 思考介面（腦）

腦＝一支照 N-12 呼叫的 inst，stdin／stdout 是固定形狀（OpenAI chat completions 的那一塊；10-15 收工後使用者再確認「維持openai格式」）：

```jsonc
// stdin：請求
{"messages": [ /* OpenAI chat messages */ ],
 "tools": [{"type": "function", "function": {"name": "clock", "description": "…", "parameters": { /* JSON schema */ }}}]}   // 選填
// stdout 最後一份：OpenAI assistant 訊息
{"role": "assistant", "content": "…或 null", "tool_calls": [            // tool_calls 選填
  {"id": "call_1", "type": "function", "function": {"name": "clock", "arguments": "{}"}}]}   // arguments 是 JSON 字串
```

- 模型要用工具＝走 OpenAI 內建的 `tool_calls`（不是在文字裡吐 JSON）。
- **用量**（10-15）：腦可以在 assistant 訊息頂層多帶 `"usage": {"prompt_tokens", "completion_tokens", "total_tokens"}`，給 LLM kernel 記額度（[kernel_llm.md](kernel_llm.md)）；think 接進 history 前拿掉 `usage`，history 照舊是純 OpenAI 訊息。兩顆真腦都會帶（openai：端點回的 `usage` 照抄；ollama：`prompt_eval_count`＋`eval_count` 換成這個形狀），端點沒回就不帶。
- 出錯：stderr 吐 `{"error": {"code", "msg"}}`（N-29）、結束碼非 0。
- 兩顆腦：demo 的假腦 `demo/fsm/brains/fake.py`（寫死的回覆）、真腦 `aos_brain_openai.py`（POST `<base_url>/chat/completions`，不串流；`base_url` 預設 LiteLLM `http://localhost:4000/v1`、`model` 必填、`api_key_env`＝放金鑰的環境變數名（沒寫＝不帶）、`timeout_ms` 預設 120000；設定從 CONFIG.json 或旗標來，stdin 是請求）。錯誤代號：`HttpError`、`ConnectFailed`、`ResponseBad`、`ApiKeyMissing`。
- 第三顆：`aos_brain_ollama.py`（ollama 原生 POST `<base_url>/api/chat`，`stream: false`）。**為什麼不走 ollama 的 `/v1`**：OpenAI 相容那條設不了 `num_ctx`，ollama 會用模型預設的 context、可能吃爆顯存；原生的帶 `options.num_ctx`（預設 4096）與 `keep_alive`（預設 `"30s"`）。旗標 `--base-url`（預設 `http://localhost:11434`，不含 `/api`）、`--model`（必填）、`--num-ctx`、`--keep-alive`、`--timeout-ms`。形狀互翻：送出時 assistant 的 `arguments` 字串→物件、`content: null`→`""`、tool 訊息補 `tool_name`；收回時 `arguments` 物件→字串、沒 id 就編 `call_<亂數>_<n>`。錯誤代號 `HttpError`（模型不支援 tools 時 ollama 回 400「does not support tools」也是這個）、`ConnectFailed`、`ResponseBad`。
- **腦只留 `content`／`tool_calls`**（使用者 10-15「模型想的內容丟掉」）：`reasoning_content` 之類想的字一律不收、不存，真腦翻譯時只取這兩樣；不留旁檔。
- **aos 從不依賴模型的思考內容，只算最後的答案**（使用者 10-15：厲害模型的端點如 Claude／GPT 會把思考加密或乾脆不給，說是防蒸餾）：設計、解析、測試都只看 `content`／`tool_calls`。會想的小模型就叫它別想（例 Qwen3 在 system 開頭寫 `/no_think`，[agent 判官](kernel_general.md#agent-判官換一行-target)就這樣），免得想太久或把輸出長度耗光、`content` 空掉。
- **換腦**：換定義資料夾的 `brain.json`；只換這一次呼叫＝在 frame 放一份 `brain.json`（綁定，蓋過定義的）。
- **10-15 實測 146 ollama**（[thinking §7](../thinking/2026-10-15-topics/02-agent工具與試146.md#7-試-146-ollama小模型)）：gemma3:1b、deepseek-r1:8b 都回 400「does not support tools」，模型沒載進去；腦這層照規矩回 `HttpError`。要在 ollama 上跑工具得換有 tools 能力的模型。**同日試 qwen2.5:14b**（使用者准，[§8](../thinking/2026-10-15-topics/03-試146-qwen與LM-Studio.md#8-試-146-ollamaqwen2514b)）：整圈跑通、`tool_calls` 形狀對，但帶 tools 時回覆語言亂跳（泰文、韓文）。

## 工具＝inst

```
clerk/                         ← 定義資料夾（呼叫時不寫）
  brain.json                   ← 腦（一張 inst）
  system.md                    ← 選填：系統提示（文字／markdown）
  tools/clock.json             ← 工具：名字＝檔名去掉 .json，值＝一張 inst
frame/（＝cwd）
  history.json                 ← 對話檔＝OpenAI messages 陣列；只有方法程式寫它（N-05）
  work/<n>/                    ← 工具每次一個新號碼資料夾：args.json（引數）、stdout.json（工具的 stdout）
```

```jsonc
// tools/clock.json：工具自己的 inst，說明放 `_tool`（aos_inst 不認得的 key 一律忽略；不用 _metainfo）
{"argv": ["aos-demo", "fsm/clerk/tools/clock.py"], "_tool": {"description": "查現在的時間", "parameters": {"type": "object", "properties": {}}}}
```

- **system**：think 每次叫腦，都把檔內容當 `{"role":"system","content":…}` 插在送給腦的 messages 最前面；**不寫進 history**（history 只有 user／assistant／tool），所以改 system.md 下一拍就生效。沒寫 `system`＝不帶；寫了但檔不存在或讀不了＝think 格錯誤 `SystemUnreadable`（N-29）。路徑從格的 cwd 算。
- 工具每次在 `work/<n>/` 新資料夾跑（mkdir 搶號；C-46：工具呼叫的 frame 預設就是這裡；工具 inst 自己寫了 `cwd` 就照它的）：stdin＝`arguments` 解開的 JSON（寫成那裡的 `args.json`），stdout 接到那裡的 `stdout.json`，最後一份＝結果。
- 回給模型：`{"role": "tool", "tool_call_id": …, "content": "<字串>"}`，content＝aos_inst 的結果（N-30：`id`、`code`、`signal`、`timed_out`、`pid`、`ms`、`exit_file`）多一格 `result`（工具 stdout 最後一份）的 JSON 字串，截 8000 字；沒跑成（工具名不認得、引數不是 JSON、inst 起不來、沒輪到、被中斷）＝N-29 形狀 `{"error": {"code", "msg"}}`。（10-15 依 C-48 改，原本是 `{"code", "result"}`）

## 現成格庫（`aos_agent_lib.py`）

→ [agent_lib.md](agent_lib.md)：`aos agent think|tool|route|intake|done|fsm`、設定從哪來（stdin＋frame 的 `lookup()`）、各格做什麼。

## 邊緣狀況（使用者 10-15 定）

→ [agent_lib.md § 邊緣狀況](agent_lib.md#邊緣狀況使用者-10-15-定)：工具名不認得、一次好幾個 tool_calls、引數不合 schema、tool 格被殺一半。

## agent 當函數／當工具

→ [frame.md](frame.md)：定義資料夾、frame（`frame.json`／`args.json`／`ret.json`、同名檔＝綁定）、直接叫、當工具（`sh -c` 三步）。
