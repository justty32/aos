# agent：回合制資料夾 agent

`aos agent` 把 agent 的對話、狀態與工具往返保存在 `<folder>/.aos/agents/<name>/`，
而 `.aos/every/agent-<name>.json` 讓 loop 每回合複製一條 `step`。一個資料夾只住
一隻 agent，cwd 就是世界；子命令會從 cwd 往上找最近的 `.aos/`。agent 直接連結
`aos::llm`，不會啟動另一個 `aos llm` 子行程。

## 快速使用

```sh
mkdir bob && cd bob
aos agent init
# 另一個視窗也在 bob/ 裡啟動世界：
aos run --step 0
# 回到第一個視窗：
aos say "你叫什麼名字"
aos listen

# 從通訊錄把訊息送到另一個世界：
aos contact add alice ../alice-world
aos say --to alice "可以幫我看一下嗎"
```

頂層的 `aos say`、`aos listen`、`aos talk`、`aos state` 都自動解析世界與唯一的
agent。`aos say --to <名字> <文字...>` 會查目前世界的 `.aos/contacts.json`，把訊息
投到聯絡人的世界與 agent。`talk` 會逐行讀 stdin，等待外部 loop 推進後印出該次新增的 log；`listen`
不帶 `--once` 時每 200 ms 印出新增內容。舊的 `aos agent say|listen|talk|state
<folder> <name>` 形式仍可使用。`aos agent talk --interface pi` 的整合限制與建議
adapter 見 [docs/pi-interface.md](docs/pi-interface.md)；目前 CLI 會清楚回報它尚未內建。

## 工具往返

世界層工具登記表是一項一檔的 `.aos/tools/<name>.json`；agent 自己的
`agents/<name>/tools.json` 若存在，只是工具名稱白名單。白名單不存在表示世界裡的工具
全部可用，`[]` 表示全部停用。送給模型時，每個工具固定表述成一行：

```text
- <name> — <description> (args: <list|string|none>, stdin: <none|text>)
```

模型只能在回覆末段的一個獨立 JSON 行要求一個已登記工具。`args: list` 使用字串陣列，
逐項接到登記的 argv；`args: string` 使用單一字串，代入 argv 裡所有 `{args}`（沒有占位符
時當一個 argv 接在後面）；`args: none` 省略 `args`。例如：

```json
{"tool":"ls","args":["-la","."]}
```

工具在第 N 回合投遞，第 N+1 回合執行，第 N+2 回合才從
`batch/<N+1>/out/` 收結果。執行結果與未知工具／參數形狀錯誤都會以一行固定形狀 JSON
寫成 `tool` 訊息，包含 `call_id`、`tool`、原始 `args`、`ok`、`result`，失敗時另有
`error.type`／`message`／`retryable`；模型會在下一次適合的回合接著處理。沒有新 user 訊息
或新工具結果時，`step` 不呼叫 LLM，
但 `.aos/every/` 仍讓它在下一回合被執行，不會浪費 LLM token。

```json
{"call_id":"agent-bob-tool-11-0","tool":"ls","args":["-la"],"ok":true,"result":{"exit":0,"signal":null,"stdout":"alpha\n","stderr":""}}
{"call_id":"agent-bob-tool-7-0","tool":"nope","args":[],"ok":false,"result":null,"error":{"type":"unknown_tool","message":"沒有登記工具 nope","retryable":false}}
```

## 函式庫

公開 API 在 `<aos/agent.hpp>`。`aos::agent::step` 接受可選的 completion callback；
未提供時呼叫 `aos::llm::complete()`，測試則可注入固定回覆，全程離線。

## 用 pi 當 LLM CPU

除了預設的 LM Studio 引擎，也可以讓一次 `aos agent step` 在世界資料夾裡執行一次
本機 pi coding agent：

```sh
mkdir bob && cd bob
aos agent init --engine pi
aos say "在這個資料夾建一個 hello.txt 內容是 hi"
aos run --step 1
aos listen --once
```

`--engine pi` 預設選 `deepseek`／`deepseek-v4-flash`；需要時可在 init 加上
`--provider P --model M`。初始化後的 `.aos/agents/<name>/engine.json` 會是：

```json
{"engine":"pi","provider":"deepseek","model":"deepseek-v4-flash",
 "session_id":"<自動產生的 v4 UUID>"}
```

執行 loop（也就是實際跑 `aos agent step`）的行程必須有 `DEEPSEEK_API_KEY`；pi 會
自行從環境變數讀取，不需要把 key 寫進檔案。不傳 `--engine` 時仍使用 lmstudio，舊世界
沒有 `engine.json` 也視同 lmstudio。

pi 引擎不走世界工具登記表／agent 白名單、`aos llm` 或 pending 的三回合工具往返；pi 自帶的
read／bash／edit／write 工具會在一次 step 內直接操作世界資料夾。對話記憶由 pi session
保存，`history.json` 只是 aos 端的鏡射。實測、argv、隔離方式與這條路的取捨見
[docs/pi-cpu.md](docs/pi-cpu.md)。

pi 的一次 step 算一個 LLM 呼叫，整個 step 會佔住一個以 `engine.json`
的 `provider`（預設 `deepseek`）命名的槽。上限設在 `<AOS_HOME>/cpus.json`，
格式見 [`core/llm/README.md`](../llm/README.md)。取槽等超過 `wait_ms` 時，step
會在吃掉 `say/` 訊息之前退回，status 寫 `waiting-llm`、不算失敗；下回合
`every` 再投一次 step 就會自然重試。優先度可用 `AOS_LLM_PRIORITY`（預設 0）；
沒設 `cpus.json` 就完全不取槽，行為與以前一樣。
