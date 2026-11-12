# 方案與時間軸

本頁由 [`../team-model.md`](../team-model.md) 拆出。**隨每月帳單與錢包變動改這頁，只寫現況**；project-owned，kernel 升級不覆蓋。

- **現況**：Claude、GPT 各一個 200 美元方案，兩套體系同時可用。codex 可用 slug 與試水溫結果見 [dispatch/aos-teams](../dispatch/aos-teams.md) 與 [probe-2026-10-09](probe-2026-10-09.json)；隊形是 opus 隊長（自家 subagent）＋兩名隊員（codex `gpt-6.1-sol`、claude CLI opus），隊員各自無上限派子 agent、盡量派 codex，見 [dispatch/aos-teams](../dispatch/aos-teams.md)。

## 若退掉 GPT

gpt-sol／terra／luna 這層**消失**，替代如下：

| 角色 | 有 GPT | 退 GPT 後 |
|---|---|---|
| 頂層 | Opus | 不變 |
| 領導 | Fable 或 Opus | 不變 |
| 工人（大量、便宜）| gpt-sol（aos 的隊員）、terra、luna | Sonnet |
| 工人（重要部分）| Opus | 不變；原本給 gpt-sol 的 A 級活**應該會改派 Opus** |

連帶效果：**工人層的消耗速度整體上升**——少了「A 級聰明、C 級消耗」那一格，同樣的工作量會更貴。使用者說**等退了再說，到時會重新規劃團隊政策**；headcount 要不要跟著下修也一併那時定。aos 的隊形（[dispatch/aos-teams](../dispatch/aos-teams.md)）到時也要跟著改。
