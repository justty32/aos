---
description: 每隔一個週期跑一次 tick 定期心跳工作流（如 /wf-tick 5m；預設 30m）
---

本檔是 **Claude Code 的 slash 指令適配層（可選）**：用 `/loop` 機制**循環**跑 tick 工作流（[wf/workflows/tick.md](../../wf/workflows/tick.md)）——每隔一個週期喚醒、跑一次單次心跳、回一句摘要。主體是 tick 工作流本身；其他工具沒有對應機制就忽略本檔，改用自家的循環功能、OS cron 或 CI 排程，**每隔 N 分鐘叫 agent 跑一次 tick 工作流**即可。

1. **決定週期**：`$ARGUMENTS` 就是週期（例 `5m`、`30m`、`2h`）。**沒給就用預設 `30m`**，並先回一句「未指定週期，用 30m」。
2. **起 loop**：用 `/loop` 每隔該週期跑一次，**loop 的目標是 tick 工作流本身，不是本指令**（指向本指令會遞迴）。
3. **每次喚醒**：照 [wf/workflows/tick.md](../../wf/workflows/tick.md) 的「流程」做一次，回一句摘要。

要停就中止 loop。本指令只是薄殼——實際做什麼全在 tick 工作流；tick 醒來時才去讀 routines / schedule 的清單。
