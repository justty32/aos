← [入口](README.md)｜涵蓋：請求信與回信、`kernel.json`、endpoint 函數、`aos-llm` 基礎工具、kernel 當 loop／daemon、跟現有 C++ kernel 的關係｜上一份 [01-現況](01-現況.md)｜下一份 [03-呼叫端](03-呼叫端.md)

# 設計（fable 照原則定的細節，可翻案）

原則：盡量長在現成的 aos-llm-kernel／aos-llm-send／aos-post／aos-daemon 上（使用者 11-01「現有的機制組合一下就能搞定」），只改「信裡帶什麼」「kernel 跑什麼」兩件事。

## 1 請求信（呼叫端 → `$AOS_KERNEL`）

一封 N-16 的信（aos-post 寄），`body`：

```json
{"endpoint": "haiku",
 "request": {"messages": [...], "tools": [...]},
 "priority": "normal"}
```

- **`endpoint`**＝一個**代號**（字串，選填）：指 kernel 定義裡登記的那一組 llm 設定（使用者「各種llm設定也可以包裝，這樣寄信的時候只要寫簡單的代號就可以」）；沒寫＝kernel 的預設那組（§ 3）；kernel 不認的代號＝回信 `error: EndpointUnknown`。呼叫端**只知道代號**，不知道 url／模型／金鑰。
- `request`＝OpenAI chat completions 的 body **去掉端點**：`messages` 必有；`tools`、`temperature`… 選填、原樣送到端點，**蓋過那組設定裡的同名預設**（臨時覆寫個別欄位＝直接寫在 `request`；但 `url`／`key` 不在 request 裡、信改不了——不讓一封信把 kernel 的金鑰送去別的網址）；`model` 也可以寫（臨時換同一端點的別的模型），沒寫＝那組的；`stream` 寫了＝`RequestBad`（下 § 6）。腦看到什麼全由呼叫端組（system、history、工具清單照 P-41）。
- `priority`＝現在 kernel 認的那套原樣（字串、數字、`{"level","deadline"}`），搬進 `body`；沒寫＝normal。
- **不再有 `inst`、`env`**：kernel 不替人跑單子、不帶走寄信人的環境（金鑰不再隨信外洩；kernel 已知限制那條解掉）。
- 信封（aos-post 寫）：`sender`＝`aos::identity()`、`sent_at`、**`reply_to` 必有**（寫哪個信箱回信就回哪裡）。`sender.flock`：`aos-llm ask`（同步）照舊建、鎖到結束，kernel 看它判「寄信人還在不在」；`aos-llm send`（非同步）**不建**，kernel 看不到檔＝不判、照跑。
- 信件名稱＝aos-post 預設名（時間開頭）；`aos-llm send` 把它印在 stdout（呼叫端收回信要靠它）。

## 2 回信（kernel → `reply_to`）

```json
{"message": {"role": "assistant", "content": "…", "tool_calls": [...]}, "usage": {...}, "model": "實際模型"}
```

或 `{"error": {"code": "BudgetMissing", "msg": "…"}}`（kernel 沒跑或跑不起來；代號沿用現在的：`DeadlineMissed`、`BudgetMissing`、`LetterBad`、`RunFailed`、`LaunchFailed`…，端點函數退非 0＝`EndpointFailed`＋它 stderr 的第一行）。`in_reply_to`＝請求信的名稱。`message` 只留 `role`／`content`／`tool_calls`（P-23 模型想的內容不收：由 endpoint 函數剪，kernel 不看內容）。`done/<信>/reply.json` 照舊留同一份當紀錄；`served.jsonl` 多記 `model`。

## 3 kernel 的定義：`kernel.json`

```json
{"mailbox": "mailbox", "slots": 2, "budget": {...}, "timeout_ms": 120000,
 "exec": "../../lib/base/llm_http",
 "endpoint": "luna",
 "endpoints": {
   "luna":       {"url": "http://localhost:4000/v1", "model": "chatgpt-gpt-6-luna-low", "key": {"$env": "LITELLM_KEY"}},
   "sol":        {"url": "http://localhost:4000/v1", "model": "chatgpt-gpt-6-sol",      "key": {"$env": "LITELLM_KEY"}, "body": {"temperature": 0.2}},
   "local-qwen": {"url": "http://localhost:1234/v1", "model": "qwen3-1.7b"},
   "fake":       {"exec": "../../lib/base/llm_fake"}}}
```

- `mailbox`、`slots`、`budget` 照舊；`accept` 拿掉（它擋的是「別人塞單子」，信裡沒單子就沒這題）。
- **`endpoints`**（新，必填）＝**代號 → 一組 llm 設定**的表（裝同類的用複數，C-54）；一組＝一層物件，kernel 只認裡面的 `exec`（選填，這組要用別的 endpoint 函數，例 `fake`），其他鍵**整個原樣交給 endpoint 函數**（`url`／`model`／`key`／`body` 是 `llm_http` 認的，不是 kernel 的規範）；指示詞照 N-45 解（所以金鑰寫 `{"$env": "LITELLM_KEY"}`——kernel 自己殼裡的變數、不是 `AOS_`——或 `{"$ref": "/home/me/.secrets/llm.json#/key"}` repo 外的檔；整張表也可以 `{"$ref": "endpoints.json#/"}` 拆出去，C-72，不另定「一組一個資料夾」）。表空＝`CfgBad`。
- **`endpoint`**（新，選填）＝預設代號（信沒寫 `endpoint` 時用）；沒寫而信也沒寫＝回信 `error: EndpointMissing`；寫了但表裡沒有＝`CfgBad`（kernel 自己的錯、起不來）。信寫的代號表裡沒有＝回信 `error: EndpointUnknown`（一封信的錯，kernel 照跑別封）。
- **`exec`**（新，必填）＝預設的 endpoint 函數＝aos-exec 目標（「要跑什麼」全體系叫 `exec`，10-23 決定）：資料夾、檔、`檔#/指標`，相對路徑從 kernel 定義資料夾算（kernel 的 cwd，N-59）；某組自己寫了 `exec` 就用它的。這就是「實際 endpoint 呼叫是 aos-exec 包起來的」（內部做法）。
- `timeout_ms`（新，選填）＝跑 `exec` 的上限（寫進那張單子的 `timeout_ms`，整群 TERM）；沒寫＝不限。
- 跑一封＝kernel 查出那組設定、在信的資料夾裡寫 `request.json`（＝`{"endpoint": 那組（解好指示詞、去掉 exec）, "request": body.request}`），fork 子行程 `run_inst({"argv": ["aos-exec", "--stack", "<信資料夾>/", "<exec>"], "stdin": "request.json", "stdout": "reply.json", "stderr": "stderr.txt", "timeout_ms": …})`——環境是 **kernel 自己的**（不再換成信裡的），stack＝那封信的資料夾（四元素 01 的建議；函數的小格，P-17）。`reply.json` 讀成回信 `body`；讀不懂＝`ReplyBad`；非 0＝`EndpointFailed`。
- **`AOS_KERNEL_REPORT` 退場**：usage 從 `reply.json` 拿（`body.usage.total_tokens`→`counter_tokens`，沒有＝null），不再另開回報檔；N-63 ① 少一個變數。

## 分檔目錄

> 超過 8 KB，依 [STRUCTURE](../../../../../wf/STRUCTURE.md) 拆：§ 4～§ 6 逐字在分檔。

| 分檔 | 涵蓋 |
|---|---|
| [01-endpoint函數-aos-llm-kernel形態](02-設計-信與kernel/01-endpoint函數-aos-llm-kernel形態.md) | § 4 endpoint 函數 `lib/base/llm_http`／`llm_fake`；§ 5 `aos-llm send／recv／ask／regret`；§ 6 kernel 當資料夾程式、掛 daemon、「包起來的」讀法 ②、退化版、跟 C++ kernel 的關係、串流不做 |
