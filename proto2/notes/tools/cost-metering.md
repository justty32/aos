# cost 工具包——測算自己每次工具呼叫花了多少

← [proto2/README](../../README.md)｜[抒發原文](../2026-09-06-world-clock-agent.md)

一句話：**每叫一次工具就記一筆帳，讓 agent 自己知道哪個工具貴，也讓主人算得出錢。**

為什麼要：現在 `aos-llm` 的帳本只記到「哪台引擎、哪個模型、今天燒了多少」，
看不出是誰、為了哪件事燒的。工具結果會原樣接進記憶，下一輪整包又送一次，
所以一個話多的工具是會一直收錢的。要省，得先看得到。

（`self_status`／`self_cost` 那種「我今天花多少」的總覽在
[self-and-memory](self-and-memory.md)，這篇是餵給它的那層——一次呼叫一筆。）

## 量什麼

一次工具呼叫，量五件事：

1. **執行時間 `took_ms`**——在 `act` 那格量，工具開始跑到回來，`time.monotonic()` 前後一減。
2. **字數 `args_chars`／`result_chars`**——參數多長、回傳多長。
   回傳那串**下一輪就是 prompt token**，所以這欄最重要。要估 token 就除以 3。
3. **這次呼叫引起的那一輪 LLM 用量**——`act` 之後必定接 `collect`→`llm`→`wait`，
   那一發請求就是「帶著這些工具結果去問」。所以**直接把下一輪回來的 `prompt_tokens`／
   `completion_tokens`／`reasoning_tokens` 整包記在這次呼叫上**，不要拿上一輪去減。
   減法看起來精準，其實會被記憶摘要、新收到的信搞歪，不值得。
   同一格叫了好幾個工具，就**按 `result_chars` 的比例分攤**那一輪的數字。
4. **幾格才做完 `round_steps`**——`act` 那格的 `step`，跟後來 `wait` 撿到回覆那格的 `step` 一減。
   等 LLM 排隊、機器慢，都會反映在這裡。
5. **錢 `cost`**——單價寫在 `engines.json`，**每台引擎多一個 `price`**：
   `"price": {"input": 0.14, "output": 0.28, "reasoning": 0.28, "cached": 0.014}`，
   單位是**每一百萬 token 幾美金**，本機那台填 0。沒填 `price` 就回 `null`，**不猜**。

## 記在哪

**一天一個檔，一行一次呼叫**，`<home>/ledger/<YYYY-MM-DD>.jsonl`：

```json
{"time": "2026-09-06T14:05:11", "step": 42, "tool": "shell_run", "args_chars": 63,
 "result_chars": 2140, "took_ms": 812, "round_steps": 4,
 "llm_round": {"prompt_tokens": 3180, "completion_tokens": 96, "reasoning_tokens": 0, "cost": 0.00047}}
```

外加一張累加的 `<home>/ledger/summary.json`，**按工具名**一列：
`{"shell_run": {"calls": 37, "avg_ms": 640, "avg_result_chars": 1900, "avg_prompt_tokens": 2800,
"total_cost": 0.021, "last": "..."}}`。要看趨勢就翻 jsonl，要一眼看完就看 summary。

**誰來寫：agent 自己，不是工具。** 工具只管做事，不該每包都自己記帳。分兩段：

- `act` 那格：每跑完一個工具，**先寫半行**（`time`／`step`／`tool`／`args_chars`／
  `result_chars`／`took_ms`），行號記進 `state.json` 的 `pending_ledger`。
- `wait` 那格撿到回覆：拿 `aos.usage` 按比例補進那幾行的 `llm_round`，算錢，
  順手折進 `summary.json`，清掉 `pending_ledger`。

沒等到回覆就死了？那幾行就只有前半，`llm_round` 是 `null`——照樣看得到時間跟字數，夠用了。

## 給模型的工具（只讀，`packs/cost.py`）

### cost_summary
- 參數：`day`（選填，不給就今天）。
- 回：按工具名列出 `calls`／`avg_ms`／`avg_result_chars`／`avg_prompt_tokens`／`total_cost`，
  外加一列 `total`。
- 什麼時候用：覺得自己變慢或變貴、要決定接下來怎麼做、有人問你哪個工具最花錢。

### cost_recent
- 參數：`n`（最近幾次，預設 10，最多 50）。
- 回：最近 n 行原樣（時間、工具、毫秒、字數、那輪 token）。
- 什麼時候用：剛剛某一步特別久，想知道是哪個工具、花在哪。

預設 prompt（`PROMPT`）大概這樣寫：

> 你每叫一次工具都會被記帳：花多少時間、回傳多少字、害下一輪多吃多少 token。
> 回傳很長的工具很貴，因為那串會一直留在你的記憶裡、每輪都重送一次。
> 所以：**貴的工具少叫、能一次講完就別分兩次、要一小段東西就別整包抓回來**。
> 覺得自己變慢變貴，就叫 `cost_summary` 看一眼。

## 主人的視角

`aos-llm` 的請求檔名已經是 `<agent 資料夾名>-<時間戳>.json`，所以「誰花的」本來就在。
建議**帳本多一層 `by-requester`**：`usage/<day>.json` 從現在的
`{"<base_url>|<model>": {...}}` 變成 `{"by-model": {...}, "by-requester": {"agent-a": {...}}}`。
舊的鍵原樣留在 `by-model`，只是多一層。

requester 從哪來：**請求檔多寫一個頂層 `requester` 欄位**（`aos_llm.write_request` 加個參數），
檔名前綴只當備援——檔名是給人看的，不該拿來當資料。

`aos-llm usage` 多一個 `--by requester`，`aos-user status` 順手印 ledger summary 前三名的工具。

## 跟現有東西怎麼接

- `proto2/aos-agent`：`do_act` 每個工具前後量時間、寫半行；`do_wait` 撿到 `aos.usage` 後補後半。
- `proto2/aos_agent.py`：加 `ledger_open()`／`ledger_close()`／`ledger_summary()`，`Ctx` 開一個 `ledger()` 給工具包讀。
- `proto2/packs/cost.py`：**新檔**，`cost_summary`／`cost_recent`。
- `state.json`：加 `pending_ledger`（這輪 act 寫了哪幾行）。
- `<home>/ledger/`：**新資料夾**，`<day>.jsonl` ＋ `summary.json`。
- `proto2/aos-llm`：`worker` 的紙條多帶 `requester`，`fold_pending`／`do_usage` 多一層 `by-requester`。
- `engines.json`：每台多一個 `price`（可有可無）。

## 現在故意不做

- 快取命中的折扣不細算（`cached` 單價填了才算，沒填就當一般 input）。
- 不做精準 tokenizer，字數除以 3 就是估值。
- 不上鎖——一個 agent 一個 ledger，只有它自己在寫。
- jsonl 不輪替、不清舊檔，一天一個檔堆著。
- 不把子 agent 的花費疊到父身上（各記各的）。
- 不算 shell 工具自己吃的 CPU／記憶體，只算牆上時間。
- 不做匯率、不做預算上限、不做超支就停。

## 要你拍板

1. 那一輪的 LLM 用量，整包算在這次呼叫上、多工具按字數分攤——可以嗎？（建議可以，減法不划算）
2. 單價放 `engines.json` 每台一個 `price`，還是另開 `prices.json`？（建議放 `engines.json`，一台的事就寫在一台旁邊）
3. ledger 放 agent 自己的 `<home>/ledger/`，LLM 資料夾照舊只記模型帳——兩邊各記各的？（建議是）
4. `usage/<day>.json` 改成 `by-model`／`by-requester` 兩層，舊格式就不相容了——換嗎？（建議換，現在檔還很少）
5. `cost_summary` 要不要每輪自動塞一句摘要進 prompt？（建議不要，太吵；讓它自己想叫再叫）
