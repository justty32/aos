# proto5-2/notes — 筆記索引

← [proto5-2 README](../README.md)

任務書、審查報告、調查。按日期排，新的在下面；同一件事超過三四份就收成 `日期-主題/` 子資料夾，裡面自己有 README。

| 檔 | 一句 |
|---|---|
| [2026-09-24-spec-review-astra-task.md](2026-09-24-spec-review-astra-task.md)／[report](2026-09-24-spec-review-astra-report.md) | astra 唯讀審 proto5-2 規範草稿第 1 版，挑出 R1～R28 |
| [2026-09-24-impl/](2026-09-24-impl/README.md) | 第 1 版實作：總報告、decisions、十段進度、run 紀錄、astra 對實作的唯讀審查（任務書＋回報）、team-rules（各檔見資料夾內） |
| [2026-09-24-one-program/](2026-09-24-one-program/README.md) | 調查：daemon＋kernel 能不能合成一支、能不能脫離 JSON 檔。四格表、甲乙對辯＋兩份 codex；建議先不動，要動就走「分開、kernel 帳本改 sqlite」，第一步是給 agent 一個「查一筆行程」的入口 |
| [2026-09-24-idle-wait/](2026-09-24-idle-wait/README.md) | 提案：等模型的 agent 不空轉。實測一次空轉＝起一支 Python 約 40 ms＋kernel 整份存帳本三次（1000 agent 時 56 ms）；四方案比較，建議 kernel 加「停車＋喚醒」（估 50～80 行＋崩潰測試） |
