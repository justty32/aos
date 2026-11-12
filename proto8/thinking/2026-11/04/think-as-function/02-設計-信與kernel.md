← [入口](README.md)｜涵蓋：請求信與回信、`kernel.json`、endpoint 函數、`aos-llm` 基礎工具、kernel 當 loop／daemon｜下一份 [03-呼叫端](03-呼叫端.md)

# 設計（fable 照原則定的細節，可翻案）

盡量長在現成的 aos-llm-kernel／aos-llm-send／aos-post／aos-daemon 上（使用者 11-01「現有的機制組合一下就能搞定」），只改「信裡帶什麼」「kernel 跑什麼」兩件事。

## 1 請求信（呼叫端 → `$AOS_KERNEL`）

一封 N-16 的信（aos-post 寄），`body`：

```json
{"endpoint": "haiku",
 "request": {"messages": [...], "tools": [...]},
 "priority": "normal"}
```

- **`endpoint`**＝一個**代號**（字串，選填）：指 kernel 定義裡登記的那一組 llm 設定（使用者「各種llm設定也可以包裝，這樣寄信的時候只要寫簡單的代號就可以」）；沒寫＝kernel 的預設那組（§ 3）；kernel 不認的代號＝回信 `error: EndpointUnknown`。呼叫端只知道代號，不知道 url／模型／金鑰。
- `request`＝OpenAI chat completions 的 body 去掉端點：`messages` 必有；`tools`、`temperature`… 選填、原樣送到端點，蓋過那組設定裡的同名預設；`model` 可寫（臨時換同一端點的別的模型），沒寫＝那組的；`url`／`key` 信改不了；`stream` 寫了＝`RequestBad`。腦看到什麼全由呼叫端組（P-41）。
- `priority`＝kernel 認的那套原樣（字串、數字、`{"level","deadline"}`），在 `body` 裡；沒寫＝normal。
- 信裡沒有 `inst`、`env`：kernel 不替人跑單子、不帶走寄信人的環境。
- 信封（aos-post 寫）：`sender`＝`aos::identity()`、`sent_at`、**`reply_to` 必有**。`sender.flock`：`aos-llm ask`（同步）建、鎖到結束，kernel 看它判寄信人還在不在；`aos-llm send`（非同步）不建，kernel 看不到檔＝不判、照跑。
- 信件名稱＝aos-post 預設名；`aos-llm send` 把它印在 stdout（收回信要靠它）。

## 2 回信（kernel → `reply_to`）

```json
{"message": {"role": "assistant", "content": "…", "tool_calls": [...]}, "usage": {...}, "model": "實際模型"}
```

或 `{"error": {"code": "BudgetMissing", "msg": "…"}}`（代號：`DeadlineMissed`、`BudgetMissing`、`LetterBad`、`RunFailed`、`LaunchFailed`…；endpoint 函數退非 0＝`EndpointFailed`＋它 stderr 的第一行）。`in_reply_to`＝請求信的名稱。`message` 只留 `role`／`content`／`tool_calls`（由 endpoint 函數剪，kernel 不看內容）。kernel 這邊不留舊信（[08 題 3](08-邊緣狀況實測.md#留給你的題白話推薦放第一)）。

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

- `mailbox`、`slots`、`budget` 照舊；沒有 `accept`。
- **`endpoints`**（必填）＝代號 → 一組 llm 設定的表（C-54 裝同類的用複數）；kernel 只認組裡的 `exec`（選填，這組要用別的 endpoint 函數），其他鍵整個原樣交給 endpoint 函數（`url`／`model`／`key`／`body` 是 `llm_http` 認的）；指示詞照 N-45 解（金鑰寫 `{"$env": "LITELLM_KEY"}` 或 `{"$ref": "…"}`；整張表也可以 `$ref` 拆出去，C-72）。表空＝`CfgBad`。
- **`endpoint`**（選填）＝預設代號；沒寫而信也沒寫＝回信 `error: EndpointMissing`；寫了但表裡沒有＝`CfgBad`。信寫的代號表裡沒有＝回信 `error: EndpointUnknown`（只那封錯，kernel 照跑別封）。
- **`exec`**（必填）＝預設的 endpoint 函數＝aos-exec 目標，相對路徑從 kernel 定義資料夾算；某組自己寫了 `exec` 就用它的。
- `timeout_ms`（選填）＝跑 `exec` 的上限（整群 TERM）；沒寫＝不限。
- 跑一封＝kernel 查出那組設定、在信的資料夾寫 `request.json`（＝`{"endpoint": 那組（解好指示詞、去掉 exec）, "request": body.request}`），經 aos-exec 跑 `exec`，stack＝那封信的資料夾、stdin＝`request.json`、stdout＝`reply.json`；`reply.json` 讀成回信 `body`，讀不懂＝`ReplyBad`、非 0＝`EndpointFailed`。（11-05 起不由 kernel 自己 fork，改請 daemon 掛成 proc 跑，見 [kernel-daemon 03](../../05/kernel-daemon/03-問腦改掛daemon.md)。）
- 沒有 `AOS_KERNEL_REPORT`：usage 從 `reply.json` 拿（`body.usage.total_tokens`→`counter_tokens`，沒有＝null）。

## 分檔目錄

| 分檔 | 涵蓋 |
|---|---|
| [01-endpoint函數-aos-llm-kernel形態](02-設計-信與kernel/01-endpoint函數-aos-llm-kernel形態.md) | § 4 endpoint 函數 `lib/base/llm_http`／`llm_fake`；§ 5 `aos-llm send／recv／ask／regret`；§ 6 kernel 當資料夾程式、掛 daemon、「包起來的」讀法 ②、跟 C++ kernel 的關係、串流不做 |
