# `knowledge/aos/brain.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/brain.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**`#/_description`**

# 問腦

一個問腦的請求怎麼走、端點包是什麼、優先順序怎麼運作。

你的身體去問 llm kernel；不要把你的腦當工具呼叫。這頁用來替子 agent 選腦，或解釋它的設定。

信：`{"endpoint": "<pack name>", "reasoning_effort"?: "<effort name>", "request": {"messages": [...], "tools": [...]}, "priority": {...}}`，用指令 `aos-llm ask`（等回覆）或 `aos-llm send` + `aos-llm recv`（晚點再回來拿）送進 `$AOS_LLM_KERNEL/requests/`。

端點包：llm kernel 有一張有名字的包的表，例如 `smart-high`（強、較慢、貴）、`stupid-fast`（弱、快、便宜）、`fake`（沒有真的模型，給測試用）。一個包固定了模型和取樣設定，像是 temperature。你只用名字挑包。

- 在信裡，包放在 `endpoint`。不要把 `model` 或 `temperature` 放進 `request` 裡：如果包固定了它們，kernel 會回 `RequestBad ... is fixed by endpoint <pack>`。要改它們，就挑別的包。
- 這跟你的腦設定（`llm.json`，用 `self_llm` 改，見 `aos/me.json#/self_llm`）裡的 `model` 不是同一個。那裡的 `model` 是包的名字，你的身體會替你把它放進 `endpoint`。
- 有哪些包：指令 `aos-llm ls` 會連同速度和花費印出來；`aos-llm ls --json` 還會顯示每個包接受的 `reasoning_efforts`。
- 推理力度（reasoning effort，模型想得多用力）：在信裡 `endpoint` 旁邊寫 `"reasoning_effort": "high"`。它是給 llm kernel 的，跟你放在 `request` 裡的 `reasoning_effort` 不一樣（那個會原樣送到模型服務）。列了 `reasoning_efforts` 的包接受那些名字；它沒列的力度是 `RequestBad`；沒有這張清單的包會忽略這個鍵。在你的腦設定裡，它是鍵 `reasoning_effort`。範本的包在你改它的時候會保住 prompt cache。

優先順序和預算：`aos/brain.json#/priority`。錯誤代號：`aos/brain.json#/codes`。

---

**`#/priority`**

# 優先順序和預算

優先順序：可有可無。`"priority": {"level": "high"}` 或 `{"level": "high", "deadline": "2026-11-05T10:00:00Z"}`。等級越高、期限越近的先服務；同等級時，快的包排在慢的前面。等很久的信會自動往前調，所以不會有誰一直餓著。

預算：每個時段（`hour`、`day` 或 `all`，由 kernel 設定）都有，分成總量、每個包、每個寄件人。寄件人是你的 stack（`$AOS_STACK`，跟你信上的寄件人一樣），所以就算幾個 agent 共用一個工作區，每個 agent 也各算各的。`BudgetMissing ... max_calls N reached in this window` 表示這個時段的預算用完了。錯誤物件還帶有 `scope`（total、endpoint 或 sender）、`window`、`since`、`resets_at`（下一個時段什麼時候開始，ISO 8601 帶時區偏移；`all` 時是 null）、`limit`（`max_calls` 或 `max_tokens`）和 `max`。kernel 不會替你換包；挑一個便宜的包，或停下來。拿到 `BudgetMissing` 的 agent-fsm agent 不會停：它留在等待狀態，到了 `resets_at` 再送一次同樣的請求（沒有這個欄位時：冷卻 30 秒，加倍到 30 分鐘為止；`aos-agent ctl ls --long` 會在 COOLDOWN 和 LAST ERROR 顯示它）；它的 `brain_notify` hook 每一串連續拒絕寄一封 BLOCKED 信到 `$AOS_NOTIFY_BOX`（`subagent add` 會把它設成父 agent 的信箱）。改它的腦（`llm.json`）會立刻清掉那段冷卻。時段是 `all` 的預算永遠不會重置：agent 在寄出 BLOCKED 信之後以 `BudgetMissing` 停下（結束碼 1）；把預算調高，再重新啟動它。

其他腦的錯誤：拿到 `retry: true` 錯誤（見 `aos/brain.json#/codes`）的 agent-fsm agent 也不會停：一樣的冷卻（或 `retry_after_s`，如果比較長，最多 30 分鐘），再送一次同樣的請求，次數不限；連續第三次失敗時，`brain_notify` 寄一封 BLOCKED 信。其他任何腦的錯誤都會讓它停下（結束碼 1，`BrainFailed`），`brain_notify` 寄一封 BLOCKED 信說明；重新啟動後它會先等冷卻結束。改 `llm.json` 會清掉這兩種冷卻。冷卻記在 agent 的 stack 裡的 `cooldown.json`：`code`、`reason`、`failures`、`until`、`retry`（true = 它會自己再試，false = 它因為這個錯誤停了），以及來自 agent-fsm 的 `error`（kernel 的 `code` 和 `msg`，例如 `EndpointFailed` `HTTP 400 ...`）；`aos-agent ctl ls --long` 會在 LAST ERROR 顯示那個錯誤；`aos-agent listen` 不讀這兩個欄位：它引用的是 agent 的 `stderr.txt` 結尾的錯誤行，連程式名一起（例如 `aos-llm: error: EndpointFailed HTTP 400 ...`）。重試也是腦的呼叫，也算進預算：長時間的故障可能把時段 `all` 的預算用光，那時 agent 就會停下。

---

**`#/codes`**

# 腦的錯誤代號

`EndpointUnknown`（沒有這個名字的包；查 `aos-llm ls`）、`EndpointFailed`（模型服務失敗、逾時或拒絕）、`ReplyBad`（服務回的東西不是可用的回覆）、`DeadlineBad`（還沒輪到它跑，你的期限就過了）、`LlmKernelMissing`（`AOS_LLM_KERNEL` 沒設定；要由人來啟動 llm kernel）。

錯誤欄位：除了 `code` 和 `msg`，錯誤還可能帶有 `retry`（true = 同樣的請求之後可能會成功：連不上、回覆到一半被切斷、HTTP 408/429/5xx、壞掉的回覆，或 kernel 自己啟動／逾時的問題；false 或沒有 = 不會成功：HTTP 401/403/其他 4xx、網址或金鑰錯誤、壞的請求）、`status`（HTTP 狀態，有回應時才有）、`retry_after_s`（服務要求等待的秒數）和 `tries`（endpoint 函式呼叫服務幾次：0、1 或 2；回覆壞掉或被切斷時，它本來就會在 1 秒後自己再呼叫一次）。只有 `retry: true` 才算可以重試。
