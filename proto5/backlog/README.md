# backlog：先記著、之後再做的事

← [proto5 README](../README.md)｜決策來源：[notes/2026-09-22-decisions.md](../notes/2026-09-22-decisions.md)

一件事一個檔。寫「是什麼問題、為什麼現在不做、以後從哪裡下手」就好，不寫方案細節。做掉了就把檔刪掉。2026-09-23 重架構後清過一次：[backlog-cleanup](../notes/2026-09-23-rearch/backlog-cleanup.md)。

| 檔 | 一句話 |
|---|---|
| [request-identity.md](request-identity.md) | agent 送出請求與加 waits 之間崩掉會重送；要不要請求身分與送件恢復（等 agent 重寫） |
| [agent-fail-state.md](agent-fail-state.md) | 連敗暫停要不要改成 agent 的 `fail` 狀態或 state.json 新 key（等 agent 重寫） |
| [tool-call-order.md](tool-call-order.md) | 讓模型指定同一批工具呼叫的先後順序的特殊工具（等 agent 重寫） |
| [llm-cpu-fallback.md](llm-cpu-fallback.md) | 問模型的 endpoint 壞掉自動換 url（等 agent 重寫） |
| [kiss-holes.md](kiss-holes.md) | proto5.1 為了 KISS 先接受的洞，重架構後剩四個 |
| [review-leftovers.md](review-leftovers.md) | fable 重審裡先不做的，重架構後剩 R4、R11 |
