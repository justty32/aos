# backlog：先記著、之後再做的事

← [proto5 README](../README.md)｜決策來源：[notes/2026-09-22-decisions.md](../notes/2026-09-22-decisions.md)

一件事一個檔。寫「是什麼問題、為什麼現在不做、以後從哪裡下手」就好，不寫方案細節。做掉了就把檔刪掉。

| 檔 | 一句話 |
|---|---|
| [request-identity.md](request-identity.md) | agent 送出請求與加 waits 之間崩掉會重送；要不要請求身分與送件恢復 |
| [agent-fail-state.md](agent-fail-state.md) | 連敗暫停要不要改成 agent 的 `fail` 狀態或 state.json 新 key |
| [tool-call-order.md](tool-call-order.md) | 讓模型指定同一批工具呼叫的先後順序的特殊工具 |
| [llm-cpu-fallback.md](llm-cpu-fallback.md) | llm cpu 的 endpoint 壞掉自動換 url |
| [cpu-simpler.md](cpu-simpler.md) | cpu 佇列實作再精簡（不加複雜度）→ proto5-2 試 |
| [kill-tree-exceptions.md](kill-tree-exceptions.md) | kill_tree 開著時，某些工具要能例外存活 |
| [kiss-holes.md](kiss-holes.md) | proto5.1 為了 KISS 先接受的七個洞 |
