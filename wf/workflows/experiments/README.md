# experiments — 實測紀錄
← [WORKFLOWS](../../WORKFLOWS.md)｜[INDEX](../../INDEX.md)

這裡放的是把規格、roadmap 與待決問題拿到真實環境執行後留下的實測紀錄，不是設計討論；紀錄保留原始指令、輸出、失敗現場與尚未能由實驗回答的邊界。

| 實驗 | 日期 | 範圍 | 結論 |
|---|---|---|---|
| [T5 agent loop](t5-agent-loop.md) | 2026-08-25 | 假模型 golden slice、投遞、SIGINT／SIGKILL、壞 JSON、真 agent CLI | 機制通；T5 驗收未全過，單次 exec 的 Ctrl-C 無法直接續跑 |
