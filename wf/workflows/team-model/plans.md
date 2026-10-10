# 方案與時間軸

本頁由 [`../team-model.md`](../team-model.md) 拆出。**隨每月帳單與錢包變動，每次改動要標日期**；project-owned，kernel 升級不覆蓋。

- **2026-08-30 當下**：Claude、GPT 各買一個月 200 美元方案，兩套體系同時可用。
- **大約 2026 年 9 月初會退掉 GPT。**

退掉後 gpt-sol／terra／luna 這層**消失**，替代如下：

| 角色 | 現在（有 GPT）| 退 GPT 後 |
|---|---|---|
| 頂層 | Opus（aos 這條 session 目前是 Fable，歷史原因）| 不變 |
| 領導 | Fable 或 Opus | 不變 |
| 工人（大量、便宜）| gpt-sol（aos 的隊員）、terra、luna | Sonnet |
| 工人（重要部分）| Opus | 不變；原本給 gpt-sol 的 A 級活**應該會改派 Opus** |

連帶效果：**工人層的消耗速度整體上升**——少了「A 級聰明、C 級消耗」那一格，同樣的工作量會更貴。使用者說**等退了再說，到時會重新規劃團隊政策**；headcount 要不要跟著下修也一併那時定。aos 的隊形（[dispatch/aos-teams](../dispatch/aos-teams.md)）到時也要跟著改。

- **2026-09-24／09-30 現況**：GPT 沒有照原計畫退掉，但 codex 上 gpt-sol／terra／luna 都已不支援，只剩 `gpt-6-astra`；那段期間 aos 碰程式碼一律派 Opus、Sonnet 只做文字小事（**10-09 起**家機實測 9 個 slug 恢復可用，工人層改回 codex，見 aos-teams），細節見 [dispatch/aos-teams](../dispatch/aos-teams.md)。
- **2026-10-09 現況**：codex 又有新 slug（`gpt-6.1-sol` 等 9 個實測可用，舊 sol／terra／luna 改名 `gpt-5.6-*`）；隊形改為 Opus 隊長＋codex 工人（寫碼 6.1-sol、審查 astra），見 [dispatch/aos-teams](../dispatch/aos-teams.md) 與 [probe-2026-10-09](probe-2026-10-09.json)。
