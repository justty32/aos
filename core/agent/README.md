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
```

頂層的 `aos say`、`aos listen`、`aos talk`、`aos state` 都自動解析世界與唯一的
agent。`talk` 會逐行讀 stdin，等待外部 loop 推進後印出該次新增的 log；`listen`
不帶 `--once` 時每 200 ms 印出新增內容。舊的 `aos agent say|listen|talk|state
<folder> <name>` 形式仍可使用。`aos agent talk --interface pi` 的整合限制與建議
adapter 見 [docs/pi-interface.md](docs/pi-interface.md)；目前 CLI 會清楚回報它尚未內建。

## 工具往返

模型只能在回覆最後一個獨立 JSON 行要求一個已登記工具，例如：

```json
{"tool":"ls","args":"-la"}
```

工具在第 N 回合投遞，第 N+1 回合執行，第 N+2 回合才從
`batch/<N+1>/out/` 收結果。沒有新 user 訊息或新工具結果時，`step` 不呼叫 LLM，
但 `.aos/every/` 仍讓它在下一回合被執行，不會浪費 LLM token。

## 函式庫

公開 API 在 `<aos/agent.hpp>`。`aos::agent::step` 接受可選的 completion callback；
未提供時呼叫 `aos::llm::complete()`，測試則可注入固定回覆，全程離線。

## 用 pi 當 LLM CPU

除了預設的 LM Studio 引擎，也可以讓一次 `aos agent step` 在世界資料夾裡執行一次
本機 pi coding agent：

```sh
aos agent init ./world --name bob --engine pi
aos agent say ./world bob "在這個資料夾建一個 hello.txt 內容是 hi"
aos run ./world --step 1
aos agent listen ./world bob --once
```

`--engine pi` 預設選 `deepseek`／`deepseek-v4-flash`；需要時可在 init 加上
`--provider P --model M`。初始化後的 `<world>/.aos/agents/bob/engine.json` 會是：

```json
{"engine":"pi","provider":"deepseek","model":"deepseek-v4-flash",
 "session_id":"<自動產生的 v4 UUID>"}
```

執行 loop（也就是實際跑 `aos agent step`）的行程必須有 `DEEPSEEK_API_KEY`；pi 會
自行從環境變數讀取，不需要把 key 寫進檔案。不傳 `--engine` 時仍使用 lmstudio，舊世界
沒有 `engine.json` 也視同 lmstudio。

pi 引擎不走 `tools.json`、`aos llm` 或 pending 的三回合工具往返；pi 自帶的
read／bash／edit／write 工具會在一次 step 內直接操作世界資料夾。對話記憶由 pi session
保存，`history.json` 只是 aos 端的鏡射。實測、argv、隔離方式與這條路的取捨見
[docs/pi-cpu.md](docs/pi-cpu.md)。
