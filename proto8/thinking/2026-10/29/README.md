# proto8 討論紀錄：2026-10-29

← [2026-10](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 日期 | 一句話 |
|---|---|
| [2026-10-29 介質後續規劃：投遞、有順序的投遞、daemon 兩個手把、鎖的用法、父子交代、窗的改口](medium-plan/README.md) | 投遞（信箱四格、一封信＝資料夾＋`letter.json`）、有順序的投遞、daemon 拆兩對窗、鎖、父子交代（N-64）；使用者「都照建議」，條文已落、已實作 |
| [2026-10-29 playground：agent 的輸入是對話簿、看信箱是一個 tool](playground-queue/README.md) | 檔名沿用 `history.jsonl`、試驗場最小版看信箱是 aos-mcp 的 inbox tool；看完兩個使用場景都用不到 agent 自己看信箱，inbox tool 解錯題、帶給使用者的題擱著 |
| [2026-10-29 agent-bob：射後不理、射後有理兩隻實跑](agent-bob/README.md) | bob-1（射後不理）與 bob-2（射後有理）實跑、aos-say／listen 當通用接口；決定 33～35：agent 這層是訊息的 queue、aos-loop 是 aos agent 的內部組件、外部 coding agent 的生命週期在外面包 |
