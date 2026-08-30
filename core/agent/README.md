# agent：回合制資料夾 agent

`aos agent` 把 agent 的對話、狀態與工具往返保存在 `<folder>/.aos/agents/<name>/`，
並在每次 `step` 結束前把下一次 `step` 原子投遞回 `.aos/inbox/`。它直接連結
`aos::llm`，不會啟動另一個 `aos llm` 子行程。

## 快速使用

```sh
aos agent init ./world --name bob
aos agent say ./world bob "你叫什麼名字"
# 由處理世界回合的 loop 執行 inbox；測試時可用：
python3 core/agent/tests/fake_loop.py ./world --step 1
aos agent listen ./world bob --once
aos agent state ./world bob
```

`talk` 會逐行讀 stdin，等待外部 loop 推進後印出該次新增的 log。`listen` 不帶
`--once` 時每 200 ms 印出新增內容。`talk --interface pi` 的整合限制與建議 adapter
見 [docs/pi-interface.md](docs/pi-interface.md)；目前 CLI 會清楚回報它尚未內建。

## 工具往返

模型只能在回覆最後一個獨立 JSON 行要求一個已登記工具，例如：

```json
{"tool":"ls","args":"-la"}
```

工具在第 N 回合投遞，第 N+1 回合執行，第 N+2 回合才從
`batch/<N+1>/out/` 收結果。沒有新 user 訊息或新工具結果時，`step` 不呼叫 LLM，
但仍會自我投遞，避免浪費 token 或讓 agent 靜默死亡。

## 函式庫

公開 API 在 `<aos/agent.hpp>`。`aos::agent::step` 接受可選的 completion callback；
未提供時呼叫 `aos::llm::complete()`，測試則可注入固定回覆，全程離線。
