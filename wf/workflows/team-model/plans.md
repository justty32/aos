# 方案與時間軸

本頁由 [`../team-model.md`](../team-model.md) 拆出。**隨每月帳單與錢包變動改這頁，只寫現況**；project-owned，kernel 升級不覆蓋。

- **現況**：Claude、GPT 各一個 200 美元方案（未核實），兩套體系同時可用。試水溫結果見 [probe-2026-10-09](probe-2026-10-09.json)；隊形（11-14 起）是 opus 或 fable 的 eca 帶 sol 隊員（agent-fsm，走本地 LiteLLM 的 sol；11-21 起 `llm.json` 是 `sol` 加 `reasoning_effort` high，以前是 pack `sol-high`），不走 codex CLI、蒐集和施工不用 terra，sol 走不通由 Claude 子 agent 補位，見 [dispatch/aos-teams](../dispatch/aos-teams.md)。

## 若退掉 GPT

gpt-sol／terra／luna 這層**消失**，替代如下：

| 角色 | 有 GPT | 退 GPT 後 |
|---|---|---|
| 頂層 | Opus | 不變 |
| 領導 | Fable 或 Opus | 不變 |
| 工人（大量、便宜）| gpt-sol（aos 的隊員；本專案蒐集和施工不用 terra、luna）| Sonnet（補位） |
| 工人（重要部分）| Opus | 不變；原本給 gpt-sol 的 A 級活**應該會改派 Opus** |

連帶效果：**工人層的消耗速度整體上升**——少了「A 級聰明、C 級消耗」那一格，同樣的工作量會更貴。使用者說**等退了再說，到時會重新規劃團隊政策**；headcount 要不要跟著下修也一併那時定。aos 的隊形（[dispatch/aos-teams](../dispatch/aos-teams.md)）到時也要跟著改。
