# planning — 想法成熟管線（本專案的落點：proto8 thinking → CONCEPTS／NORMS）

← [WORKFLOWS](../WORKFLOWS.md)｜[INDEX](../INDEX.md)

kernel 的 planning 管線（idea → roadmap → 詳規 → 執行）在本專案**早已長成自己的工作流**，本檔只做路由、不另存表格：

| 階段 | 回答的問題 | 本專案的落點 |
|------|-----------|-------------|
| **idea** | 要不要做？ | [proto8/thinking](../../proto8/thinking/README.md)——使用者原文、決定、結論；定下來的概念進 [proto8/docs/CONCEPTS](../../proto8/docs/CONCEPTS.md) |
| **roadmap** | 會做，何時？ | [SESSION-LOG](../SESSION-LOG.md) 的 open 進度與下一步（方向由使用者定，鐵律 5） |
| **詳規** | 怎麼做？ | `.aos` 版面、指令 JSON 與回合語意的唯一真源是 [PROTOCOL](dispatch/proto/PROTOCOL.md)；子命令規格在 [experiments/t5-agent-loop/subcommand-specs](experiments/t5-agent-loop/subcommand-specs.md) |
| **執行** | — | [feature-dev](feature-dev/README.md) |

**何時用**：「記個想法」→ proto8/thinking；「接下來做什麼」→ SESSION-LOG；「討論方案／寫動工計畫」→ 先查 thinking 的決定與 CONCEPTS／[NORMS](../../proto8/docs/NORMS.md)，別重想已定的。舊的 ideas 13 章與 roadmap 已封存（10-13）。
**何時不用**：只是要查清楚 → [investigation](investigation.md)；拿一個明確假設去驗 → [experiments](experiments/README.md)；多個 agent 各自試做 → [hackathon](hackathon/README.md)。

## 交接

- 為什麼選 A 不選 B → [decisions](decisions.md)（→ thinking 的決定）；卡在使用者一句話 → [WAIT_USER](../WAIT_USER.md)；跨 session → [SESSION-LOG](../SESSION-LOG.md)。
