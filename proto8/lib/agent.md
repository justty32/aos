# agent（定義資料夾＋現成格庫 `aos_agent_lib.py`＋真的腦 `aos_brain_openai.py`／`aos_brain_ollama.py`）

← [proto8/lib](README.md)｜概念：[CONCEPTS agent](../CONCEPTS/05-agent.md)｜狀態機：[fsm.md](fsm.md)｜demo：[demo/fsm](../demo/fsm/README.md)｜決定：[thinking 10-15 §5](../thinking/2026-10-15-topics/02-agent工具與試146.md#5-agent-的工具與思考介面)

> **這是實作慣例，還不是規範。** 使用者 10-15 定了方向；等接過一次真的 endpoint、跑順了，再升成 NORMS 的條。

agent＝一個定義資料夾：fsm 表＋各狀態跑的 inst（C-50；intake → thinking → route → tool → thinking → … → done）。這裡定三件事：**思考介面**（換腦只換一個 TARGET）、**工具＝inst**、**agent 當函數／當工具**（定義資料夾＋frame，C-46）。

葉子一律寫指令名（C-50）：PATH 前面接 `proto8/bin`，`aos agent think`、`aos brain openai`、`aos loop` 等就找得到（`proto8/bin/aos` 是薄入口，`aos <名>`＝`python3 lib/aos_<名>.py`；跟 C++ 的 aos 執行檔同名不相干，誰先在 PATH 上用誰）。demo 自己的腳本走 `demo/bin/aos-demo`（`aos-demo fsm/brain/fake.py`＝從 demo 資料夾算的路徑，跟 cwd 無關；其他指令照跑、環境多 `AOS_DEMO`＝demo 資料夾）。

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
- **用量**（10-15）：腦可以在 assistant 訊息頂層多帶 `"usage": {"prompt_tokens", "completion_tokens", "total_tokens"}`，給 LLM kernel 記額度（[kernel.md](kernel.md)）；think 接進 history 前拿掉 `usage`，history 照舊是純 OpenAI 訊息。兩顆真腦都會帶（openai：端點回的 `usage` 照抄；ollama：`prompt_eval_count`＋`eval_count` 換成這個形狀），端點沒回就不帶。
- 出錯：stderr 吐 `{"error": {"code", "msg"}}`（N-29）、結束碼非 0。
- 兩顆腦：demo 的假腦 `demo/fsm/brain/fake.py`（寫死的回覆）、真腦 `aos_brain_openai.py`（POST `<base_url>/chat/completions`，不串流；`base_url` 預設 LiteLLM `http://localhost:4000/v1`、`model` 必填、`api_key_env`＝放金鑰的環境變數名（沒寫＝不帶）、`timeout_ms` 預設 120000；設定從 CONFIG.json 或旗標來，stdin 是請求）。錯誤代號：`HttpError`、`ConnectFailed`、`BadResponse`、`NoApiKey`。
- 第三顆：`aos_brain_ollama.py`（ollama 原生 POST `<base_url>/api/chat`，`stream: false`）。**為什麼不走 ollama 的 `/v1`**：OpenAI 相容那條設不了 `num_ctx`，ollama 會用模型預設的 context、可能吃爆顯存；原生的帶 `options.num_ctx`（預設 4096）與 `keep_alive`（預設 `"30s"`）。旗標 `--base-url`（預設 `http://localhost:11434`，不含 `/api`）、`--model`（必填）、`--num-ctx`、`--keep-alive`、`--timeout-ms`。形狀互翻：送出時 assistant 的 `arguments` 字串→物件、`content: null`→`""`、tool 訊息補 `tool_name`；收回時 `arguments` 物件→字串、沒 id 就編 `call_<亂數>_<n>`。錯誤代號 `HttpError`（模型不支援 tools 時 ollama 回 400「does not support tools」也是這個）、`ConnectFailed`、`BadResponse`。
- **腦只留 `content`／`tool_calls`**（使用者 10-15「模型想的內容丟掉」）：`reasoning_content` 之類想的字一律不收、不存，真腦翻譯時只取這兩樣；不留旁檔。
- **aos 從不依賴模型的思考內容，只算最後的答案**（使用者 10-15：厲害模型的端點如 Claude／GPT 會把思考加密或乾脆不給，說是防蒸餾）：設計、解析、測試都只看 `content`／`tool_calls`。會想的小模型就叫它別想（例 Qwen3 在 system 開頭寫 `/no_think`，[agent 判官](kernel2.md#agent-判官換一行-target)就這樣），免得想太久或把輸出長度耗光、`content` 空掉。
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

```
aos agent think|tool|route [--done 名]|intake|done|fsm [NAME]      （＝python3 aos_agent_lib.py …）
```

- 不是 agent 本體（agent＝fsm＋表，不變）；是表裡可以直接拿來用的兩格。檔名：使用者 10-15 說「aos-agent-lib.py」，proto8/lib 的模組一律底線（連字號 import 不了），所以叫 `aos_agent_lib.py`。
- **設定從哪來**（10-15 收工後改：fsm 不再餵格 stdin，N-37）：stdin＝那張格 inst 自己 `stdin` 指的檔（沒寫＝空）；那份的 key 優先，沒寫的照 frame（＝cwd）找——`lookup()`：先找 cwd，找不到照 cwd 裡 `env.json` 的 `parent` 往上找（C-46，繞圈或超過 16 層就停）。`brain`＝`brain.json`、`tools`＝`tools/*.json`（`lookup_dir()`：各層逐項合併、近的蓋過遠的；名字＝檔名去掉 `.json`）、`system`＝`system.md`（有才帶）、`history`＝cwd 的 `history.json`、`work`＝cwd 的 `work/`。stdin 不是物件＝`NoConfig`、退出 1。相對路徑從格的 cwd 算。定義資料夾的格都不寫 stdin，全靠 frame 找。

- **think**：讀 history、組請求（`tools` 從各工具 inst 的 `_tool` 來；沒工具就不帶）、蓋 stdin 跑腦（`aos_methods.run_cell`）、把 assistant 訊息（拿掉頂層 `usage`）接進 history，stdout `{"data": {"content", "tool_calls": [工具名]}}`。不吐 `next`：下一格寫在表上。history 最後已經是 assistant（上一拍接好才被殺）＝不再叫腦。腦結束碼非 0＝`BrainFailed`（白話＝腦 stderr 的錯誤 `代號: 白話`，腦沒吐才寫結束碼）、回的不是 assistant 訊息＝`BadReply`，這格退出 1，fsm 那行的 `error` 是 `CellFailed: BrainFailed: HttpError: …`。**連錯停住是格自己的事**（N-38）：次數記在 `work/think-fails.json`（成功一次就刪），到 `halt_after`（預設 3）次＝不報錯、改吐 `{"next": halt_state（預設 "halted"）, "data": {"error"}}`——表上要有那個狀態（例 done 格寫錯誤的 ret.json），不然 fsm 報 `UnknownNext`、每拍再叫一次腦。
- **tool**：找最後一則 assistant 還沒回的 `tool_calls`，跑一個、接 tool 訊息，stdout `{"data": {"tool", "result"}}`。跑工具前寫 `work/.tool-running.json`（記 tool_call id）、跑完刪：下一拍看到它還在、同一個 id＝上一拍被殺一半。
- **route**：看最後一則 assistant，有 `tool_calls`＝`{"next": "tool"}`，否則 `{"next": "idle", "data": {"reply"}}`（`--done 名` 把 idle 換掉，定義資料夾寫 `--done done`）。單層表用（demo 的 `clerk/`）。
- **intake**：把 cwd 的 `args.json`（實引數）接進 history，接完把 `args.json` 改名成 `args.taken.json`、刪掉上一輪的 `ret.json`（同一份不會接兩次；呼叫方下次再寫一份新的 `args.json` 就是新問題）。`{"question"}`：frame 還沒有 `history.json`＝生一份 `[user 訊息]`；已經有＝接在後面當一則新的 user 訊息（同一個 frame 續聊，10-15 使用者「按照建議」）；history 最後一則已經是同一句 user 訊息（上一拍接好了、改名前被殺）＝不再接。`{"history"}`＝整段換掉。沒有 `args.json`：已經有 history＝照舊往下（呼叫方綁了 history，或接著上次的）；也沒有＝`NoHistory`。
- **done**：寫 cwd 的 `ret.json`（`work/think-fails.json` 在＝`{"error"}`，否則 `{"reply": 最後一句}`）。不碰 ctl：done 在表的 `end` 裡，fsm 結束那拍那行帶 `"end": true`，拍它的 loop 寫了 `stop_on_end` 就停（N-44）。
- **fsm**（不是格，給 loop.json 用）：照 `lookup()` 找 `NAME`（預設 `fsm.json`），跑一拍 aos_fsm（格的名字從找到的那份所在的資料夾算、窗從 frame 算）。這樣定義資料夾的 `loop.json` 不必寫自己在哪：`{"inst": {"argv": ["aos", "agent", "fsm"]}, …}`；內層 fsm 的格也一樣寫 `aos agent fsm think/fsm.json`。找不到＝`NoFsm`、退出 125。
- stdin 給的 `brain`、`tools` 值除了 TARGET，也可以是內嵌一張 inst。

## 邊緣狀況（使用者 10-15 定）

| 情況 | 基礎實作 |
|---|---|
| 工具名不認得 | 回模型一則 tool 訊息 `{"error": {"code": "UnknownTool", "msg": "不認得這個工具：名"}}`，不算 fsm 的錯 |
| 一次回好幾個 `tool_calls` | 只跑第一個；其餘各回 `{"error": {"code": "Skipped", "msg": "基礎實作一次只跑一個，這個沒跑"}}`（OpenAI 要每個 id 都有回才能再問），stderr 警告 `ToolCallsSkipped` |
| 引數不合 schema | 不驗；工具自己報錯（code≠0），照樣回模型 |
| tool 格被殺一半（`work/.tool-running.json` 還在、同一個 id，N-38） | 不重跑工具，還沒回的全回 `{"error": {"code": "Interrupted", …}}` |

動工時自己定的（等使用者看）：`arguments` 不是 JSON＝回 `{"error": {"code": "BadArguments", …}}` 不跑；工具的 inst 起不來（aos_inst 出錯）＝回 aos_inst 的錯（同形狀、原代號）；工具 inst 沒寫 `_tool`＝空說明、不收引數。

## agent 當函數／當工具

概念：[CONCEPTS C-46、C-50](../CONCEPTS/05-agent.md)｜決定：[thinking 意見 1～4](../thinking/2026-10-15-opinions-1-4.md#callbindinglisp-式)（10-15 收工後：call／binding 不寫專用程式，用 json＋資料夾＋inst；原本的 `aos_agent_call.py`、`aos_agent_lib.py ask` 已退場）

**定義資料夾**（照 Lisp 的函數本體；呼叫時一個字都不寫，所以能重複用）：

```
clerk/
  fsm.json      {"start": "intake", "state": "fsm-state.json", "end": ["done", "halted"], "states": {
                   "intake": {"target": "cells/intake.json", "next": "thinking"},
                   "thinking": {"target": "cells/think.json", "next": "route"},
                   "route": "cells/route.json",                       // 回 {"next": "tool"} 或 {"next": "done"}
                   "tool": {"target": "cells/tool.json", "next": "thinking"},
                   "done": "cells/done.json", "halted": "cells/done.json"}}   // halted＝think 連錯自己跳來
  loop.json     {"inst": {"argv": ["aos", "agent", "fsm"]}, "times": 20, "stop_on_end": true, "ctl": "ctl.json", "state": "loop-state.json"}
  cells/intake.json  {"argv": ["aos", "agent", "intake"]}      think／route（--done done）／tool／done 同樣一行
  brain.json  system.md  tools/clock.json
```

**frame**＝被叫者跑的 cwd，放哪由呼叫方決定（C-46）。裡面：`env.json` `{"parent": "<定義資料夾>"}`（找名字往上一層）、`args.json`（實引數，intake 接走後改名 `args.taken.json`）、`ret.json`（回傳）、`history.json`、`fsm-state.json`、`loop-state.json`、`ctl.json`、`work/`。放同名檔＝綁定：`brain.json` 蓋過定義的腦、`tools/x.json` 追加或同名蓋過（逐項合併；「整份取代」不支援）、`history.json` 綁一段對話。

**呼叫**（直接叫）：

```
cd frame && echo '{"parent": "/abs/clerk"}' > env.json && echo '{"question": "幾點？"}' > args.json \
  && aos loop /abs/clerk/loop.json >/dev/null; cat ret.json
```

- 一趟：intake（args.json → history）→ think → route → (tool → think → route)* → done（寫 `ret.json`＝`{"reply"}`；done 在 `end` 裡，fsm 結束那行帶 `"end": true`，loop 的 `stop_on_end` 看到就停，N-44）。think 連錯 3 次＝halted → 同一張 done 格寫 `{"error": {"code", "msg"}}`。走完 end，fsm 的 phase 歸位 `intake`。
- loop 的 `times` 用完還沒走到 done＝沒有 `ret.json`（沒跑完）。
- **同一個 frame 再叫一次**＝接著那裡的 history：呼叫方只要再寫一份 `args.json`；intake 把它接在後面、順手刪上一輪的 `ret.json`（這次沒跑完就讀不到舊的）。不必刪 `ctl.json`：done 不寫 ctl，loop 靠 fsm 結束那行停。
- 兩個呼叫同時指同一個 frame 不擋（卡死不防護）；不同 frame 可以同時跑。

**當工具**：工具 inst 用 `sh -c` 三步（寫 env.json → 跑被叫者的 loop → 讀 ret.json）。tool 格每次在 `work/<n>/` 開新資料夾、寫好 `args.json`、在那裡跑它，所以那裡就是被叫者的 frame；`cat ret.json` 的內容就是工具結果，父 agent 的 tool 訊息 `result` 看得到（錯也是 N-29 形狀）。demo 的 `tools/clerk.json`：

```jsonc
{"argv": ["aos-demo", "sh", "-c",
   "printf '{\"parent\": \"%s\"}' \"$AOS_DEMO/fsm/clerk\" > env.json && aos loop \"$AOS_DEMO/fsm/clerk/loop.json\" >/dev/null; cat ret.json"],
 "timeout_ms": 120000, "_tool": {"description": "問報時員…", "parameters": {…}}}
```

- 綁定也在這一步做：例 `demo/kernel/boss/tools/clerk.json` 多一步 `cp …/boss/brain.json brain.json`，報時員就改用 boss 的腦（經閘門）。
- 上限：被叫者 loop 的 `times`、那張工具 inst 的 `timeout_ms`（父 agent 的 tool 格 `timeout_ms` 要更大）；遞迴深度不另外擋（Busy、TooDeep、MaxTicks 都拿掉了）。
- 定義資料夾的路徑：demo 用 `aos-demo` 給的 `AOS_DEMO` 拼絕對路徑；不在 demo 裡就直接寫絕對路徑。
