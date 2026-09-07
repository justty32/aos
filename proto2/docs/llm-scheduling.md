# LLM 排隊優先度

LLM 世界每一格都會重排。舊數字還能用。新工作建議用 priority 物件。

## 會用到的介面

- `aos_llm.write_request()`：程式丟請求時用。`priority` 可給數字或物件。`requester` 寫誰丟的。
- `aos-llm ls`：想知道誰排前面、為什麼插隊時用。
- `aos-llm exec`：LLM 世界每一格自己叫。人通常不用手動叫。
- `aos-llm usage`：看今天按模型、按 requester 分開的用量。
- `aos-llm usage --by requester`：只看誰用了多少。

## priority 怎麼寫

```json
{
  "priority": {
    "level": 5,
    "deadline": "2026-09-06T22:00:00+08:00",
    "kind": "chat",
    "requester": "group-a/kid-1",
    "cost_class": "normal",
    "age_boost": 1
  }
}
```

- `level`：通常填 0 到 9。越大越急。預設 0。
- `deadline`：最晚開工時間。要帶時區。沒有就不填。
- `kind`：`chat`、`tool`、`think`、`background`。預設 `chat`。
- `requester`：建議寫 `集團/agent`。沒有斜線就整串算一個集團。
- `cost_class`：`cheap`、`normal`、`expensive`。以引擎設定為準。
- `age_boost`：每等一分鐘加幾分。預設 1。請求只能比資料夾預設低。

舊寫法仍可用：

```json
{"priority": 5}
```

它等於只寫 `{"level": 5}`。舊數字不會被限制在 0 到 9。

## 怎麼排

過期的 deadline 一定排在未過期的前面。其餘分數是：

`level × 100 + kind 分 + 等待分 - 費用分 - 近期占用分`

- kind：chat `+40`、tool `+20`、think `0`、background `-40`。
- 等待：等待分鐘乘 age_boost。最多 `+300`。
- 費用：cheap `0`、normal `-10`、expensive `-30`。
- 近期占用：同一集團在最近 10 次開工中，每次 `-25`。

最後看分數高、檔案較早、檔名較小。每成功開一筆，近期紀錄立刻更新，剩下的再算一次。某台引擎滿了，不會擋住別台。

`aos-llm ls` 會顯示這種理由：

```text
score=465 level=5 chat +40 wait=10 normal=-10 recent=-75 requester=group-a/kid-1
```

過期的會多一個 `deadline=late`。

## 預設設定

`defaults.json` 可以繼續放數字，也可以放物件：

```json
{
  "engine": "local",
  "priority": {"level": 0, "kind": "chat", "age_boost": 1, "cost_class": "normal"}
}
```

引擎知道自己的價格時，在 `engines.json` 那台旁邊寫 `"cost_class": "cheap"`。排程不信請求自己喊便宜。

## Anthropic 直連

引擎寫 `"api": "anthropic"` 就直接打 Anthropic 的 `/v1/messages`，不用架轉接器。不寫這個鍵＝
`openai`，一切照舊。整個系統（aos-agent、帳本、packs）只認 OpenAI 的 chat/completions 形狀，
所以 worker 在送出前與收回後各翻一次：

- 送出去：`system` 訊息抽到頂層 `system`（好幾則用空行接起來）；`role: tool` 變成一則 user 的
  `tool_result`；assistant 的 `tool_calls` 變成 `tool_use` 塊（arguments 那串 JSON 會 parse 回物件）。
- **連續同一邊的訊息會併成一輪**：Anthropic 不收兩個 user 連著，而工具結果一多就會連著好幾則。
- `tools` 從 `{type: function, function: {...}}` 換成 `{name, description, input_schema}`；
  `tool_choice` 一起換（`required` → `any`、指名某個工具 → `{"type": "tool", "name": ...}`）。
- `max_tokens` 是必填，`params` 沒寫就 4096；`stop` 換成 `stop_sequences`；`temperature` 那些原樣過；
  `n`、`seed`、`response_format` 這種 Anthropic 不吃的先丟掉，免得整發被打回 400。
- 收回來：text 塊接成 `message.content`、`tool_use` 塊變成 `message.tool_calls`、`thinking` 塊放進
  `reasoning_content`；`stop_reason` 換成 `finish_reason`（`tool_use` → `tool_calls`、`end_turn` → `stop`、
  `max_tokens` → `length`）。
- usage 換成 `prompt_tokens`／`completion_tokens`／`total_tokens`。**快取讀到的與寫進去的 token 都折進
  `prompt_tokens`**（OpenAI 那邊本來就含快取命中，算錢是「(prompt − cached) × 進價 + cached × 快取價」，
  不折進去會少算），另外留一份 `prompt_tokens_details.cached_tokens` 與 Anthropic 原本的兩個數字。
- 打錯了（例如 HTTP 400）就把 Anthropic 的 `{"type":"error","error":{...}}` 挑成一句
  `{"error": "HTTP 400 ... invalid_request_error: 訊息"}`，跟別種引擎的錯誤長一樣。

工作室 preset 的 cheap／thinking 兩層可以直接對上兩台：

```json
[{"name": "cheap", "api": "anthropic", "base_url": "https://api.anthropic.com",
  "model": "claude-haiku-4-5-20251001", "api_key_env": "ANTHROPIC_API_KEY",
  "max_concurrent": 4, "cost_class": "cheap", "params": {"max_tokens": 4096}},
 {"name": "thinking", "api": "anthropic", "base_url": "https://api.anthropic.com",
  "model": "claude-sonnet-5", "api_key_env": "ANTHROPIC_API_KEY",
  "max_concurrent": 2, "cost_class": "expensive", "params": {"max_tokens": 8192}}]
```

## claude-cli（用 Claude Code 訂閱）

引擎寫 `"api": "claude-cli"` 就不打 HTTP，改開一個本機的 `claude -p` 子進程——**給有 Claude 訂閱、
沒有 API key 的人用**。工作室的 cheap／thinking 兩層可以直接這樣寫：

```json
[{"name": "cheap", "api": "claude-cli", "model": "haiku", "max_concurrent": 2,
  "cost_class": "cheap", "params": {"effort": "low"}},
 {"name": "thinking", "api": "claude-cli", "model": "sonnet", "max_concurrent": 2,
  "cost_class": "expensive"}]
```

實際跑的是這一行（`bin` 不寫就是 PATH 上的 `claude`，`params.effort` 有寫才加 `--effort`）：

```sh
claude -p --safe-mode --no-session-persistence --output-format json --tools ""   --model <model> --json-schema <schema> --append-system-prompt <系統話> [--effort <級>]
```

- `--safe-mode` 把 CLAUDE.md／skills／plugins／hooks／MCP 全關掉，每一發都一樣乾淨；cwd 一律是
  LLM 資料夾，不會跑到誰的專案裡。**不用 `--bare`**：`--bare` 的認證只認 `ANTHROPIC_API_KEY`，
  訂閱制的 OAuth 會直接回「Not logged in」。
- `--tools ""` 關掉全部內建工具。請求裡的 `tools` 改用講的：`--append-system-prompt` 裡列一行一個
  `名字(參數 schema) — 說明`，外加一條「回覆一定要符合 json-schema」的規矩，由 `--json-schema`
  （`{content, tool_calls[{name, arguments}]}`）收口。
- 對話從 stdin 餵：`【user】…`／`【assistant】…`（它的工具呼叫寫成 `→ 名字 {參數}`）／`【tool:名字】結果`，
  最後留一個空的`【assistant】`讓它接下去。
- 回來的 `structured_output` 翻成 `choices[0].message`（`tool_calls` 的 id 補成 `call_1`、`call_2`…），
  `usage` 跟 Anthropic 同一套折法，`session_id` 與 `total_cost_usd` 記在結果的 `aos.cli` 底下。
- 退出碼非 0、吐的不是 JSON、或 `is_error` → `{"error": "claude-cli 失敗（exit N）：…"}`；找不到執行檔
  當場就講，不會拖到逾時。帳本一樣把它算成一次 error。

兩句提醒：**這是把 Claude Code headless 當引擎，用量算在訂閱的五小時窗口裡**，不是 API 帳單，
`total_cost_usd` 只是等值參考。**每一發多兩三秒的進程啟動**，所以 `max_concurrent` 別開太大、
短請求別全塞這台。

## 用量帳本

新帳本有兩層：

```json
{"by-model": {"網址|模型": {}}, "by-requester": {"group-a/kid-1": {}}}
```

`requester` 先讀請求資料。沒有才拿檔名前綴。`aos-llm usage` 也讀得懂舊的平鋪帳本。

## 已知坑

- 已開跑的請求不會重排，也不會取消。
- 不處理兩台機器時間不同、時間倒退、requester 冒名。
- 大量排隊時，每開一筆都會重讀分數。先求簡單，還沒為效能加索引。
