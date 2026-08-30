# planning — 想法成熟管線（本專案的落點：ideas → roadmap）

← [WORKFLOWS](../WORKFLOWS.md)｜[INDEX](../INDEX.md)

kernel 的 planning 管線（idea → roadmap → 詳規 → 執行）在本專案**早已長成自己的工作流**，本檔只做路由、不另存表格：

| 階段 | 回答的問題 | 本專案的落點 |
|------|-----------|-------------|
| **idea** | 要不要做？ | [ideas/](ideas/README.md)——構想、心智模型、十輪拷問的紀錄；裁決總表在 [verdicts](ideas/verdicts.md) |
| **roadmap** | 會做，何時？ | [roadmap](roadmap.md)——M0–M5 階段表、每階段先裁什麼、動工前讀什麼 |
| **詳規** | 怎麼做？ | 規格在 `docs/`（[`aos-folder.md`](../../docs/aos-folder.md) 是 `.aos` 的唯一真源）；子命令規格在 [experiments/t5-agent-loop/subcommand-specs](experiments/t5-agent-loop/subcommand-specs.md) |
| **執行** | — | [feature-dev](feature-dev/README.md) |

**何時用**：「記個想法」→ ideas；「接下來做什麼」→ roadmap；「討論方案／寫動工計畫」→ 先過 [verdicts A 表](ideas/verdicts.md) 別重想已裁決的，再進 roadmap 對應階段。
**何時不用**：只是要查清楚 → [investigation](investigation.md)；拿一個明確假設去驗 → [experiments](experiments/README.md)；多個 agent 各自試做 → [hackathon](hackathon/README.md)。

## 交接

- 為什麼選 A 不選 B → [decisions](decisions.md)（→ verdicts）；卡在使用者一句話 → [WAIT_USER](../WAIT_USER.md)；跨 session → [SESSION-LOG](../SESSION-LOG.md)。
