# trial — 大量試用：驗證＋找不順手（2026-08-30）

← [dispatch](../README.md)｜判準 [usability-target](../../ideas/usability-target.md)

**目的**：照使用者定的兩級劇本，用「使用者的方式」大量操作 aos，記**多餘的動作／看不見的狀態／錯誤不指路**，
每條附「用 pi／Claude Code 做同一件事的對照」。這階段**只找、不修**（修 bug 隊與改進隊之後另開）。

| 隊 | 劇本 | 發現檔 | 交接書 |
|---|---|---|---|
| L1 單人 coding agent | 在一個真的程式碼資料夾裡全程只用 `aos …`，lmstudio 與 pi 各跑一遍 | [findings-L1.csv](findings-L1.csv) | [proto-L1](../proto/proto-L1-solo.md) |
| L2 指揮 agent 團隊 | 主 agent 派生子 agent（各住一個資料夾）、通訊錄投遞、收回報 | [findings-L2.csv](findings-L2.csv) | [proto-L2](../proto/proto-L2-team.md) |

**發現檔格式**（`wf-table/1`，一行一條）：`id,lane,kind(bug|awkward|spec-gap|cannot),severity(1-3),step,expected,actual,compare,repro`。
`repro` 指向 `trial/repro/<id>.sh`（可重跑的最小重現，之後修 bug 隊直接當回歸）。
