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
