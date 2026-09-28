# proto6 設計筆記與交接索引

← [proto6](../README.md)

2026-09-28，依使用者要求，完整收錄本輪 proto5 討論、兩份外牆調查及探針，作為 proto6 的起點。原位置保留歷史，不刪除；這裡是標示來源的交接快照，不代表現行 proto5 已變成新架構。

## 先讀最新方向

先讀[三大概念：基底、agent、任務與排程](concepts.md)。這是使用者已接受的責任分區，也是接續閱讀入口；不代表三個程序或已完成的實作。

逐塊閱讀草案：[基底](base.md) → [agent](agent.md) → [任務與排程](scheduling.md)。每篇說明責任、交接與小案例；細分待討論，不是完整規範。

繼續細拆到欄位、合法狀態、提交與失敗恢復，見 [spec 規格草案](../spec/README.md)。兩份獨立的[冗餘審查](spec-redundancy-review.md)與[遺漏審查](spec-gaps-review.md)區分編輯修正、可選精簡與尚需裁定的政策；不代表其中建議都已採納。四隊獨立審查本篇 notes 全部內容與收錄忠實度的結果見[notes 審查](notes-review.md)，同樣不代表建議已採納。

軟性設計原則：[兩次 tick 之間的環境穩定性](between-ticks-configuration.md)。由原先硬保證改為設計指導，不屬於 spec，也不設強制驗收。

最新討論先放下正式員工／工具的組織分類，以一 agent 一 Linux 使用者、cgroup v2 管執行資源、project quota 管自有容量。工具沿用委託 agent 的權限與資源，不需要逐工具 bwrap；保護宿主的整套 aos 外牆仍保留，具體部署未定。CPU worker 取消是後續方向，尚未實作；前文的固定 worker 構想保留為演進脈絡，不能同時當成最新要求。

工作負載目標是一台家用機保存 10,000 個 agent，每小時活躍不到 100 個，共用十幾個雲端 LLM endpoint；這不是同時併發上限，也不是已完成的規模驗證。idle 不常駐、不頻繁 tick，事件或到期才喚醒。Docker／FUSE 不作基本前提，FUSE 延後。

接著讀[最新討論紀錄](2026-09-28-linux-resources-and-task-scheduling.md)，再看[萬 agent 改動計畫](plan/README.md)。需要背景時回看[人的架構閱讀筆記](2026-09-28-human-architecture.md)；隔離選型在[調查入口](investigations/README.md)，局部實測與重跑方式在[探針入口](probes/README.md)。

## 完整來源對照

以下 15 份來源完整收錄。Markdown 僅增加快照說明、重算連結與更新探針執行路徑；兩支探針程式保持位元組相同。已收錄資料互連 proto6，現行程式、spec、舊 benchmark 仍指向 proto5；外部來源與當時的行號、實測數字均保留。後續演進以 proto6 為入口，不把歷史提案自動升格成規格。

| proto6 收錄 | 歷史來源 |
|---|---|
| [架構背景](2026-09-28-human-architecture.md) | [proto5 human-architecture](../../proto5/notes/2026-09-28-human-architecture.md) |
| [員工身分與方向演進](2026-09-28-employee-identity.md) | [proto5 employee-identity](../../proto5/notes/2026-09-28-employee-identity.md) |
| [root daemon 草案](2026-09-28-host-root-design.md) | [proto5 host-root-design](../../proto5/notes/2026-09-28-host-root-design.md) |
| [Linux 實作成本](2026-09-28-linux-employee-implementation.md) | [proto5 linux-employee-implementation](../../proto5/notes/2026-09-28-linux-employee-implementation.md) |
| [隔離實測報告](2026-09-28-linux-isolation-probes.md) | [proto5 linux-isolation-probes](../../proto5/notes/2026-09-28-linux-isolation-probes.md) |
| [資源與任務排程](2026-09-28-linux-resources-and-task-scheduling.md) | [proto5 linux-resources-and-task-scheduling](../../proto5/notes/2026-09-28-linux-resources-and-task-scheduling.md) |
| [萬 agent 計畫入口](plan/README.md) | [proto5 計畫 README](../../proto5/notes/2026-09-28-ten-thousand-agents/README.md) |
| [執行與排程](plan/runtime.md) | [proto5 runtime](../../proto5/notes/2026-09-28-ten-thousand-agents/runtime.md) |
| [Linux 與儲存](plan/linux-and-storage.md) | [proto5 linux-and-storage](../../proto5/notes/2026-09-28-ten-thousand-agents/linux-and-storage.md) |
| [LLM 與驗收](plan/llm-and-validation.md) | [proto5 llm-and-validation](../../proto5/notes/2026-09-28-ten-thousand-agents/llm-and-validation.md) |
| [探針重跑入口](probes/README.md) | [proto5 探針 README](../../proto5/notes/2026-09-28-linux-probes/README.md) |
| [探針 runner](probes/run.py) | [proto5 run.py](../../proto5/notes/2026-09-28-linux-probes/run.py) |
| [Landlock canary](probes/landlock-canary.c) | [proto5 landlock-canary.c](../../proto5/notes/2026-09-28-linux-probes/landlock-canary.c) |
| [宿主 root 第二道牆](investigations/proto5-host-root-second-wall.md) | [wf 第二道牆調查](../../wf/workflows/investigations/proto5-host-root-second-wall.md) |
| [Linux 外牆可行性](investigations/proto5-linux-wall-feasibility.md) | [wf Linux 外牆調查](../../wf/workflows/investigations/proto5-linux-wall-feasibility.md) |
