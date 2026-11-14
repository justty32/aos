# experiments — 實測紀錄
← [WORKFLOWS](../../WORKFLOWS.md)｜[INDEX](../../INDEX.md)

這裡放的是把規格、roadmap 與待決問題拿到真實環境執行後留下的實測紀錄，不是設計討論；紀錄保留原始指令、輸出、失敗現場與尚未能由實驗回答的邊界。

> **跟 hackathon（11-14 已封存）的分界**：experiments 是**我自己**拿**一個明確假設**去驗，要的是是／否；hackathon 是**多個 agent 各自動手做同一題**，要的是不同做法各撞到什麼坑。

| 實驗 | 日期 | 範圍 | 結論 |
|---|---|---|---|
| [T5 agent loop](t5-agent-loop.md) | 2026-08-25 | 假模型 golden slice、投遞、SIGINT／SIGKILL、壞 JSON、真 agent CLI | 機制通；T5 驗收未全過，單次 exec 的 Ctrl-C 無法直接續跑 |
| [Claude 訂閱 OAuth](claude-subscription/README.md) | 2026-09-13 | 只讀本機 pi／pi-ai 0.85.1 的原始碼（沒連網、沒送 API 請求）：pi 怎麼把 Claude 訂閱的 OAuth 當 Messages endpoint 用 | pi 用 Claude Code 的 OAuth 身分登入、打 API 時帶 Claude Code 的標頭；aos 不自己寫這種客戶端，要接 Claude 只用 API key 或把 pi 當子行程 |
