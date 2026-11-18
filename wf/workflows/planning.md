# planning — 想法成熟管線（本專案的落點：proto8 thinking → CONCEPTS／NORMS）

← [WORKFLOWS](../WORKFLOWS.md)

kernel 的 planning 管線（idea → roadmap → 詳規 → 執行）在本專案**早已長成自己的工作流**，本檔只做路由、不另存表格：

| 階段 | 回答的問題 | 本專案的落點 |
|------|-----------|-------------|
| **idea** | 要不要做？ | [proto8/thinking](../../proto8/thinking/README.md)——使用者原文、決定、結論；定下來的概念進 [proto8/docs/CONCEPTS](../../proto8/docs/CONCEPTS.md) |
| **roadmap** | 會做，何時？ | [SESSION-LOG](../SESSION-LOG.md) 的 open 進度與下一步（方向由使用者定，鐵律 5） |
| **詳規** | 怎麼做？ | 規範 [proto8/docs/NORMS](../../proto8/docs/NORMS.md)、agent 慣例 [proto8/docs/CONVENTION](../../proto8/docs/CONVENTION.md)；各程式的行為在它自己的 README（C／C++ 見 [proto8/cpp](../../proto8/cpp/README.md)）。 |
| **執行** | — | [feature-dev](feature-dev/README.md) |

**何時用**：「記個想法」→ proto8/thinking；「接下來做什麼」→ SESSION-LOG；「討論方案／寫動工計畫」→ 先查 thinking 的決定與 CONCEPTS／[NORMS](../../proto8/docs/NORMS.md)，別重想已定的。
**何時不用**：只是要查清楚 → 只讀直接查、筆記寫進當天的 proto8/thinking（舊的 investigation 工作流 11-17 已封存）；拿一個明確假設去驗 → 直接跑、紀錄寫進 proto8/thinking（舊的 experiments 工作流 11-17 已封存）；多個 agent 各自試做 → 照 [dispatch/aos-teams](dispatch/aos-teams.md) 開隊（舊的 hackathon 工作流 11-14 已封存）。

## 交接

- 為什麼選 A 不選 B → [decisions](decisions.json)（→ thinking 的決定）；卡在使用者一句話 → 新題寄使用者專區（`aos-user send`，見 [common/user.md](common/user.md)），進度記在 [SESSION-LOG](../SESSION-LOG.md)、標「等使用者」；跨 session → [SESSION-LOG](../SESSION-LOG.md)。
