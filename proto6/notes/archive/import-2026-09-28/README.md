# 09-28 從 proto5 收錄的交接快照

← [封存索引](../README.md)

> 封存 2026-09-29：這批是 proto6 的起點；09-29 起架構改為 node／kernel 樹，spec 已重寫。現行看 [spec](../../../spec/README.md) 與 [kernel 樹](../../2026-09-29-kernel-tree.md)。

依使用者要求，完整收錄 09-28 這輪 proto5 討論、兩份外牆調查及探針，作為 proto6 的起點。原位置保留歷史，不刪除；這裡是標示來源的交接快照，不代表現行 proto5 已變成新架構。閱讀順序是[最新討論紀錄](2026-09-28-linux-resources-and-task-scheduling.md) → [萬 agent 改動計畫](plan/README.md)；背景見[人的架構閱讀筆記](2026-09-28-human-architecture.md)，隔離選型在[調查入口](investigations/README.md)。

`plan/backend-switch.md` 不是收錄快照，是 09-29 從 spec 移出的附註，跟著計畫一起放這裡。探針（`probes/`）沒有搬，仍在 [notes/probes](../../probes/README.md)。

## 完整來源對照

以下 15 份來源完整收錄。Markdown 僅增加快照說明、重算連結與更新探針執行路徑；兩支探針程式保持位元組相同。已收錄資料互連 proto6，現行程式、spec、舊 benchmark 仍指向 proto5；外部來源與當時的行號、實測數字均保留。後續演進以 proto6 為入口，不把歷史提案自動升格成規格。

| proto6 收錄 | 歷史來源 |
|---|---|
| [架構背景](2026-09-28-human-architecture.md) | [proto5 human-architecture](../../../../proto5/notes/2026-09-28-human-architecture.md) |
| [員工身分與方向演進](2026-09-28-employee-identity.md) | [proto5 employee-identity](../../../../proto5/notes/2026-09-28-employee-identity.md) |
| [root daemon 草案](2026-09-28-host-root-design.md) | [proto5 host-root-design](../../../../proto5/notes/2026-09-28-host-root-design.md) |
| [Linux 實作成本](2026-09-28-linux-employee-implementation.md) | [proto5 linux-employee-implementation](../../../../proto5/notes/2026-09-28-linux-employee-implementation.md) |
| [隔離實測報告](2026-09-28-linux-isolation-probes.md) | [proto5 linux-isolation-probes](../../../../proto5/notes/2026-09-28-linux-isolation-probes.md) |
| [資源與任務排程](2026-09-28-linux-resources-and-task-scheduling.md) | [proto5 linux-resources-and-task-scheduling](../../../../proto5/notes/2026-09-28-linux-resources-and-task-scheduling.md) |
| [萬 agent 計畫入口](plan/README.md) | [proto5 計畫 README](../../../../proto5/notes/2026-09-28-ten-thousand-agents/README.md) |
| [執行與排程](plan/runtime.md) | [proto5 runtime](../../../../proto5/notes/2026-09-28-ten-thousand-agents/runtime.md) |
| [Linux 與儲存](plan/linux-and-storage.md) | [proto5 linux-and-storage](../../../../proto5/notes/2026-09-28-ten-thousand-agents/linux-and-storage.md) |
| [LLM 與驗收](plan/llm-and-validation.md) | [proto5 llm-and-validation](../../../../proto5/notes/2026-09-28-ten-thousand-agents/llm-and-validation.md) |
| [探針重跑入口](../../probes/README.md)（未搬） | [proto5 探針 README](../../../../proto5/notes/2026-09-28-linux-probes/README.md) |
| [探針 runner](../../probes/run.py)（未搬） | [proto5 run.py](../../../../proto5/notes/2026-09-28-linux-probes/run.py) |
| [Landlock canary](../../probes/landlock-canary.c)（未搬） | [proto5 landlock-canary.c](../../../../proto5/notes/2026-09-28-linux-probes/landlock-canary.c) |
| [宿主 root 第二道牆](investigations/proto5-host-root-second-wall.md) | [wf 第二道牆調查](../../../../wf/workflows/investigations/proto5-host-root-second-wall.md) |
| [Linux 外牆可行性](investigations/proto5-linux-wall-feasibility.md) | [wf Linux 外牆調查](../../../../wf/workflows/investigations/proto5-linux-wall-feasibility.md) |
