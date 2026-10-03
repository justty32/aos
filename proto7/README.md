# proto7 — aos 時空架構

← [repo INDEX](../wf/INDEX.md)

proto7 從使用者 2026-10-03 的分層想法開始：daemon 是運行層，檔案系統是空間、tick-tock 是時間，kernel 與 agent 是跑在這個時空上的任務。**目前只有核心 spec，還沒有細部 spec 和程式。** 上一代是 proto6；proto7 的文件不連回去，需要的東西搬過來。

## 入口

- **[核心 spec](spec/core.md)**（[spec 入口](spec/README.md)）：使用者定下的核心概念，條號 S-；之後的細部 spec、程式與測試都以它為準。
- [notes](notes/2026-10-03-aos-layering.md)：使用者 10-03 的分層想法原文，核心 spec 的「第 N 行」指這份。
