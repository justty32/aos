# tick — 單次定期心跳（派發器）

← [WORKFLOWS](../WORKFLOWS.md)｜[INDEX](../INDEX.md)

跑**一次**心跳：依序叫起 [routines](routines.md) 與 [schedule](schedule.md)，最後回一句摘要。刻意極薄——**自己不判時間、不存清單、不做事**，判斷與清單全在被叫起的那兩個工作流裡。**本檔就是心跳的主體**：任何能「每隔 N 分鐘叫 agent 做一件事」的東西都可以當引擎，叫它跑本工作流即可。

**何時用**：[`/wf-tick [週期]`](../../.claude/commands/wf-tick.md) 每隔一個週期喚醒時（也可以是 OS cron / CI 排程或其他工具的循環功能）；或你直接說「跑一次心跳」。
**何時不用**：要**登記**一件常規事務 → 直接去 [routines](routines.md)；要登記一個一次性行程 → 直接去 [schedule](schedule.md)（都不必經過 tick）。心跳裡也不跑重活（深度巡檢、調查、批次改檔）。

## Done when

- 回了一句摘要，且（若有到期的間隔項）[routines](routines.md) 間隔登記表該列的「上次執行」已更新。

## 流程

1. 執行 [routines](routines.md) 的「B. 執行」段：判當地時間 → 對照時機分區 / 間隔登記表 → 到期的就做。
2. 執行 [schedule](schedule.md) 的「B. 執行」段：到點的一次性行程就做、做完刪列。
3. **回一句摘要**：兩邊這次各做了什麼、有沒有到期的。都沒事就一句「無事」。

## 交接

- 到期項需要使用者決定 / 親自做 → [WAIT_USER](../WAIT_USER.md) 一行，心跳不卡在那裡。
- 到期項是重活 → [SESSION-LOG](../SESSION-LOG.md) 一行 open，另開 session 做。
- 心跳**不推任何外部通知**：到期項只在 session 裡當場做、當場說。
