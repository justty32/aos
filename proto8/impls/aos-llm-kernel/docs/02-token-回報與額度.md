← [回入口 README.md](../README.md)｜段落：用法｜上一份：[01-用法](01-用法.md)｜下一份：[03-元素等](03-元素等.md)

### 跑一封（endpoint 函數）

（[thinking 11-04 think-as-function 02 § 3](../../../thinking/2026-11/04/think-as-function/02-設計-信與kernel.md)：「實際 endpoint 呼叫是 aos-exec 包起來的」）

1. 查代號（信的 `body.endpoint`，沒寫用預設）→ 解那組的指示詞 → 那組有 `exec` 就用它、沒有用 kernel.json 的 `exec`，`exec` 鍵拿掉。
2. 在信的資料夾（`cur/<信件名稱>/`）寫 `request.json`＝`{"endpoint": 那組（指示詞已解、去掉 exec）, "request": body.request}`。
3. fork 子行程，交給 aos-exec 的 `run_inst` 跑
   `{"argv": ["aos-exec", "--stack", "<信>/", <exec 絕對路徑>], "cwd": "<信>", "stdin": "<信>/request.json", "stdout": "<信>/reply.json", "stderr": "<信>/stderr.txt", "timeout_ms": kernel.json 的}`。
   **環境是 kernel 自己的**（不換成寄信人的、不另加變數）；stack＝那封信的資料夾（函數的小格，P-17：函數要寫暫存、`stream.txt` 之類就寫在 `$AOS_STACK`）。
4. 跑完：退非 0（含逾時、被訊號停）＝回信換成 `{"error": {"code": "EndpointFailed", "msg": "endpoint 函數退 N（逾時…）：stderr.txt 第一行"}}`；
   退 0 而 `reply.json` 不是 `{"message": 物件, …}`（或 error 形狀）＝`ReplyBad`；讀得懂＝原樣當回信。起不來（aos-exec 不在 PATH…）＝`EndpointFailed`「跑不起來」。
5. kernel 收尾時刪掉 `request.json`（裡面有那組的金鑰，[04 #13](../../../thinking/2026-11/04/think-as-function/04-邊緣狀況.md)）；寄完回信、寫完 served 那行，整封（`cur/<信>/`）刪掉，不留紀錄（11-04 夜使用者「舊信根本不用留，就是刪」，[think-as-function 08 題 3](../../../thinking/2026-11/04/think-as-function/08-邊緣狀況實測.md#留給你的題白話推薦放第一)）。

endpoint 函數的契約（stdin `{"endpoint", "request"}` → stdout 一行 `{"message", "usage", "model"}`、退 0；錯退非 0、stderr 一行）是 [lib/base/llm_http、llm_fake](../../../lib/README.md) 定的，kernel 只看結束碼與 stdout 的形狀，不看內容（`message` 剪不剪是函數的事）。

### token 與額度

- **用量從回信拿**（11-04 起；原本的 `AOS_KERNEL_REPORT`／`report.json` 退場）：回信的 `usage.total_tokens`（非負整數）就是這封的 token 數；沒有就 `prompt_tokens`＋`completion_tokens`；沒有 `usage`（含 error 回信）＝`counter_tokens` null、只算次數；`usage` 不是物件、數字不對＝`usage_bad: true`（也只算次數，照樣回信）。
- **算什麼**：子行程起來過（`runner.json` 在）的信才算一次——`LetterBad`、`RequestBad`、`Endpoint{Missing,Unknown}`、`DeadlineMissed`、`BudgetMissing` 不算；`EndpointFailed`、`ReplyBad` 算（函數跑過、可能已經花了錢）；kernel 死了、下一次回 `RunFailed` 的那封也算。
- **額度**（kernel.json 的 `budget`，都選填）：`max_calls`、`max_tokens`＝每窗上限（非負整數；沒寫＝那一種不限；寫舊名 `calls`、`tokens`＝`CfgBad`）；`window`＝`"hour"`／`"day"`／`"all"`（沒寫＝`day`；窗的起點用 kernel 的本地時間〔`TZ`〕的整點／午夜，`all`＝不歸零）；
  `spent`＝到頂時排著的信怎麼辦：`"refuse"`（沒寫＝這個）回 `BudgetMissing`、不跑；`"wait"` 留在 `new/` 等下一窗。
  `budget` 沒寫也照樣記 `used.json`（窗＝day）：`{"window", "since", "counter_calls", "counter_tokens", "counter_all_calls", "counter_all_tokens"}`。換窗＝`window` 或 `since` 跟現在算出來的不同：`counter_calls`、`counter_tokens` 歸零，`counter_all_*` 照留。
- **到頂怎麼判**：要開下一封之前看——`counter_calls`＋這次已開的＋上一次留下還在跑的 ≥ `max_calls`，或 `counter_tokens` ≥ `max_tokens`。token 只能跑完才知道，所以一次裡最多超過「那一次所有封的量」。

### 一次

1. 建信箱三格、flock；`queue.json` 的 `counter_runs`＋1。
2. **`cur/` 還有信**＝上一次 kernel 跑到一半死了：有讀得懂的 `reply.json` 就照它；跑信的子行程（`runner.json`）還活著＝讓它跑完、這次少一格；都不是＝回 `RunFailed`（不重跑）。有回信的寄回信、寫一行 served、刪掉。
3. **收拾**（只看有 `sender.flock` 的信）：`tmp/` 裡寄信的人不在了的刪掉；`new/` 裡寄信的不在了的先改名回 `tmp/` 再刪（不白跑）。沒有 `sender.flock` 的一律不碰。舊 kernel 留下的 `done/` 整個刪。
4. **看 `new/`**：`LetterBad`、`RequestBad`、`EndpointMissing`、`EndpointUnknown`、那組壞了（`DirectiveBad`、`CfgBad`）、deadline 已過（`DeadlineMissed`）＝直接回信（都不佔格、不跑）。
5. **排隊**（`used.json` 先讀進來、換窗了先歸零）：`level`＋等了幾次÷10（每等 10 次升一級，不封頂）大的先 → deadline 近的先（有寫的在沒寫的前面）→ 等得久的先 → 先寄的先。
6. 跑之前看一眼訊號（有＝不認領、直接 128＋N）。照排好的順序一封封看：額度到頂＝`refuse` 回 `BudgetMissing`、`wait` 就停；沒到頂、`slots` 也還有空就認領（`new/` → `cur/` 改名；改不成＝寄信的剛撤信，換下一封），每封照上面「跑一封」fork 一個子行程。
7. **全部跑完才往下**（一次裡不補位）：每封讀 usage、有 `reply_to` 就寄回信（有 `sender.flock` 而寄信的人已不在＝馬上撤回那封）、寫一行 served、記進 `used.json`、整封 `cur/<信>/` 刪掉；寫 `queue.json`；結束碼 0。

### 訊號

整支擋著 SIGINT／SIGTERM／SIGHUP。跑信的期間收到就轉給每個子行程（它們的 `run_inst` 再轉給 endpoint 函數的整群），等全部結束、回信照寫（多半是 `EndpointFailed` 退 143），再以 128＋N 結束（P-36）。
