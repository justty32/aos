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
claude -p --no-session-persistence --setting-sources "" --disable-slash-commands \
  --output-format stream-json --verbose --model <model> --tools "" \
  --mcp-config <一串 JSON> --strict-mcp-config --allowedTools "mcp__aos__*" \
  --max-turns 1 --system-prompt <系統話> [--effort <級>]
```

**工具一定要用 MCP 給，不能用文字列。** 以前是把工具清單寫進 `--system-prompt`、再用
`--json-schema` 要一包 `{content, tool_calls}`。實跑會壞：haiku／sonnet 一看到工具名字就吐
**真的** `tool_use` block，Claude Code 回一句
`<tool_use_error>Error: No such tool available: task_assign</tool_use_error>`，模型繞五六輪、
最後回一句「工具調用異常，無法執行派工」，`tool_calls` 空的（`--max-turns 2` 也擋不住，
實跑 `num_turns` 還是 6）。**模型看到工具名字就會想真的叫它——那就給它真的工具。**

- 工具走 [`aos-mcp-tools`](../aos-mcp-tools)：一台**只登記、不執行**的 stdio MCP 小伺服器。
  `tools/list` 把請求裡的 `tools` 報上去（`parameters` 翻成 `inputSchema`）；`tools/call`
  什麼都不做，只把 `{name, arguments}` 附到記錄檔、回一句「已登記」。**工具是 aos-agent
  下一回合自己去跑的**，Claude Code 只負責替我們做「這一輪要叫哪個工具、參數長怎樣」的決定。
- 工具清單先落在 `<LLM 資料夾>/side/cli/<時間>-<pid>.tools.json`，MCP 的登記簿落在旁邊的
  `.calls.jsonl`；跑順了順手掃掉，**失敗才留著**給人翻。
- `--max-turns 1` 在第一個 assistant 回合就收工。它撞上限時 `result` 事件會是
  `subtype: error_max_turns`、`is_error: true`——那是**正常收工**，不是失敗，只要那一輪有
  assistant 訊息就算數。
- **不能用 `--safe-mode`**：它把 MCP 一起關了，連 `--mcp-config` 給的都不載（實測 init 事件回
  `mcp_servers: []`、`tools: []`，模型看不到工具，只好用 `<function_calls>` 假 XML 亂寫）。
  乾淨是靠這幾支湊出來的：`--setting-sources ""`（不載使用者／專案／本地 settings，hooks 一起沒）、
  `--disable-slash-commands`（關 skills）、`--tools ""`（關內建工具）、`--strict-mcp-config`
  （別人裝的 MCP 一概不載）、`--system-prompt`（整個換掉，CLAUDE.md 那些也就進不來）。
  cwd 一律是 LLM 資料夾，不會跑到誰的專案裡。
- `--system-prompt` 只放兩樣：請求裡的 system 訊息 ＋ 一條「要叫工具就用工具，不要用文字描述；
  content 是給人看的話」。**工具清單不寫在這裡**（寫了模型只會更想直接叫）。
- 對話從 stdin 餵：`【user】…`／`【assistant】…`（它的工具呼叫寫成 `→ 名字 {參數}`）／`【tool:名字】結果`，
  最後留一個空的`【assistant】`讓它接下去。
- 回來的是 stream-json（一行一個事件，`-p` 模式下一定要配 `--verbose`）。只收**第一則**
  assistant 訊息：text block 併成 `content`、`tool_use` block 翻成 `tool_calls`（名字剝掉
  `mcp__aos__` 前綴、id 就用 block 的 id），thinking 丟掉。**一則訊息會拆成好幾個 assistant
  事件**（一個 block 一個，thinking 也算一包），所以是照 `message.id` 收齊，不是只拿第一個事件。
  記錄檔當備援：MCP 那邊登記過、stream 裡卻沒有的，補進去。
- `usage` 從最後的 `type: "result"` 事件拿，跟 Anthropic 同一套折法（快取 token 折進
  `prompt_tokens`，另留 `prompt_tokens_details.cached_tokens`）；`session_id`、`total_cost_usd`、
  `num_turns` 記在結果的 `aos.cli` 底下。
- 退出碼非 0 且一句 assistant 都沒有 → `{"error": "claude-cli 失敗（exit N）：…"}`；有跑完但沒有
  assistant 訊息 → `{"error": "claude-cli 沒有回任何 assistant 訊息：…"}`；找不到執行檔當場就講，
  不會拖到逾時。帳本一樣把它算成一次 error。

實跑一發（haiku、兩個工具 say／order_status、對話「請叫 say 說 hi」）：MCP 起得來、init 事件看得到
`mcp__aos__say`／`mcp__aos__order_status`，模型吐 `mcp__aos__say {"text":"hi"}`，撿回來就是
`tool_calls[0].function.name == "say"`，`num_turns` 2、`stop_reason` `error_max_turns`、
1216／114 token、約 $0.0028。

兩句提醒：**這是把 Claude Code headless 當引擎，用量算在訂閱的五小時窗口裡**，不是 API 帳單，
`total_cost_usd` 只是等值參考。**每一發多兩三秒的進程啟動**（再加一個 MCP 子進程），所以
`max_concurrent` 別開太大、短請求別全塞這台。

- **一定是 `--system-prompt`（整個換掉），不是 `--append-system-prompt`**：留著 Claude Code 自己那兩萬 token 的身份，它會把我們的工具當成「要在這台機器上執行的事」、繞好幾輪才回話（實玩 4d 踩到：30k prompt／5 turns／回不出東西）。
- **`--bare` 不能用**：它只認 `ANTHROPIC_API_KEY`，會把 OAuth 登入踢掉。**`--safe-mode` 也不能用**：它把 `--mcp-config` 一起關了。
- 引擎裡最好寫 `"bin": "/home/<你>/.local/bin/claude"`：鐘是 daemon 開的，PATH 不一定有 `~/.local/bin`。

## codex-cli（用 ChatGPT 訂閱跑 Codex）

引擎寫 `"api": "codex-cli"` 就開一個本機的 `codex exec` 子進程——**給有 ChatGPT 訂閱、沒有
OpenAI API key 的人用**。模型名字要用訂閱認得的那幾個（`gpt-5.6-sol` 最強、`gpt-5.6-luna`／
`gpt-5.6-terra` 便宜）：

```json
[{"name": "cheap", "api": "codex-cli", "model": "gpt-5.6-luna", "max_concurrent": 2,
  "cost_class": "cheap", "params": {"effort": "low"}},
 {"name": "thinking", "api": "codex-cli", "model": "gpt-5.6-sol", "max_concurrent": 1,
  "cost_class": "expensive"}]
```

實際跑的是這一行（`bin` 不寫就是 PATH 上的 `codex`，`params.effort` 有寫才加那一個 `-c`，
`extra_args` 原樣接在後面）：

```sh
codex exec --ephemeral --skip-git-repo-check -s read-only --json -C <LLM 資料夾> -m <model> \
  -c 'mcp_servers.aos.command="<python3>"' \
  -c 'mcp_servers.aos.args=["<aos-mcp-tools>","<specs 檔>"]' \
  -c 'mcp_servers.aos.env={AOS_MCP_RECORD="<登記檔>"}' \
  -c 'mcp_servers.aos.default_tools_approval_mode="auto"' \
  [-c 'model_reasoning_effort="<級>"']
```

- `--ephemeral` 不落 session 檔、`--skip-git-repo-check` 允許在非 git 資料夾跑、`-s read-only`
  不讓它動東西、`-C` 把工作根釘在 LLM 資料夾（絕不是誰的專案目錄）。prompt 走 stdin。
- `-c` 的值是 TOML：字串要引號、`args` 是陣列、`env` 是 inline table。這幾個鍵都拿
  `codex exec --strict-config -c ...` 驗過（打錯的鍵它會回「unknown configuration field」）。

### 為什麼要架一台假的 MCP server

claude-cli 那條路是「工具用講的、回覆用 json-schema 收口」。**codex 這樣做不行**：它是一個
agent，不是一個「你給我工具清單、我回你一包 tool_calls」的端點。工具只用文字描述，它多半
只會寫一段「我要叫 say」的話，形狀對不上；但只要工具是**真的掛上去**的，它就會發出真的
工具呼叫。所以：

1. 請求裡的 `tools` 寫成 `<LLM 資料夾>/side/codex/<請求名>.specs.json`。
2. 用 `-c` 把 [`aos-mcp-tools`](../aos-mcp-tools) 掛成一台叫 `aos` 的 stdio MCP server，
   `tools/list` 時把 OpenAI 的 `parameters` 換名成 `inputSchema` 端給它看。
3. **那台 server 什麼都不做**：被叫到就把 `{name, arguments}` append 進登記檔
   `<請求名>.record.jsonl`，回一句「已登記，這一輪到此為止」。真的要跑工具是外面
   `aos-agent` 下一回合的事——我們要的只是「它這一輪決定叫誰、帶什麼參數」。
4. codex 沒有 max-turns，會一直做下去，所以停手的規矩是我們自己訂的：**登記檔一出現第一批
   呼叫就再給 2 秒**（引擎寫 `"grace": 5` 可以調），然後 SIGTERM／SIGKILL 收掉整個 process
   group，有什麼算什麼。`turn.completed` 先到就直接走。
5. 成功就把 `side/codex/` 那兩個小抄刪掉；失敗留著給人看。

翻譯的部分：`item.completed` 裡 `agent_message` 的 `text` 接成 `content`、`mcp_tool_call`
拿來對帳、`turn.completed` 的 `usage` 換算成 `prompt_tokens`（＝`input_tokens`，本來就含快取）／
`completion_tokens`（＝`output_tokens` ＋ `reasoning_output_tokens`）／`total_tokens`，
另外留 `prompt_tokens_details.cached_tokens` 與原始那幾欄。**`tool_calls` 以登記檔為準**，
登記檔空的才退而用事件流那一份。`thread_id`、原始 usage、有沒有被我們收掉記在 `aos.cli`。
`turn.failed`、非零退出碼、逾時都變成一句 `{"error": "codex-cli 失敗：…"}`；找不到執行檔當場就講。

### 兩個要先知道的坑

- **工具核准**：`codex exec` 是非互動的，沒人能按核准，所以 MCP 工具呼叫會被擋成「此工具需要
  核准」——`mcp_servers.<台>.default_tools_approval_mode="auto"` 與 `approval_policy="never"`
  都擋不住（codex 0.153.2 實測，上游 issue #24135 也是這樣）。這時**登記檔會是空的**，還好
  事件流裡的 `mcp_tool_call` 已經帶了名字與參數，我們照樣拼得出 `tool_calls`，只是 `content`
  會多一句模型的道歉。真的要讓登記檔生效，得在 `extra_args` 加
  `--dangerously-bypass-approvals-and-sandbox`——**那會連 `-s read-only` 一起關掉**，自己衡量。
- **輸入 token 很貴**：一發只有兩個工具、三句話的請求，實測 `input_tokens` 約 4.6～4.7 萬
  （其中 3.4～3.7 萬是快取命中），比空手跑一句話的約 1.3 萬多出一大截——多的是 codex 自己的
  工具與指示。`--ignore-user-config`、`-c project_doc_max_bytes=0`、`-C 空資料夾` 都救不了
  （本機 `~/.codex/config.toml` 才 657 bytes，工作目錄也沒有 AGENTS.md）；真正的把手是
  `model_instructions_file`（0.153.2 認這個鍵，`base_instructions`／`experimental_instructions_file`
  不認），還沒實測。**所以 codex-cli 適合「一發抵一個決定」的粗活，不適合拿來聊天**。

一句提醒：跟 claude-cli 一樣，這是把訂閱當引擎用，用量算在訂閱的窗口裡、不是 API 帳單，
帳本的 token 只是等值參考；每發還多幾秒到幾十秒的進程與工具啟動時間，`max_concurrent` 別開太大。

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
