# kernel — 掛在 daemon 上的管理元件

← [proto8](../README.md)｜用它們的 agent 範本：[templates](../templates/README.md)｜概念：[CONCEPTS kernel](../docs/CONCEPTS/04-kernel.md)、[NORMS kernel](../docs/NORMS/09-kernel.md)

| 元件 | 是什麼 |
|---|---|
| `llm-kernel/` | 問腦的那台：agent 寄請求信、它挑能力包（`smart-high`、`stupid-fast`…）問模型、寄回信；自己一台 daemon |
| `daemon-judge/` | 繼承式 kernel：判官先判過 ctl 請求、才轉寄進 daemon 的 ctl 信箱 |
| `procs-kernel/` | 0 號 proc 式 kernel：daemon 的 0 號 proc 收請求、判完才轉寄 |

判官工具本身在 [lib/aos/judge](../lib/README.md)。

## 分檔目錄

| 分檔 | 涵蓋的段 |
|---|---|
| [01-llm-kernel](docs/01-llm-kernel.md) | llm kernel 範本 llm-kernel（11-04 晚：問腦＝寄信給它、收回信；11-05 改成自己一台 daemon；11-05 午 能力包、`aos-llm ls`） |
| [02-kernel-modes](docs/02-kernel-modes.md) | kernel 三種模式：daemon 本身、daemon-judge（繼承式）、procs-kernel（0 號 proc 式）；判官 lib/aos/judge、AOS_KERNEL、「唯一能下 ctl」三級（11-05） |
| [03-feat-proto](docs/03-feat-proto.md) | 新功能原型的假腦劇本（11-05 午）：agent 給自己加工具、能力包與排程、agent 生 agent、資源份額 |
