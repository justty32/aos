# 試玩紀錄（play）

← [proto5 README](../../README.md)｜前一輪原型的試玩在 [proto4/notes/play](../../../proto4/notes/play/README.md)

每個段落收線後，開沒看過設計筆記的 agent 只拿 README 當新使用者玩，照五條標準打分（① 容易上手 ② 容易理解 ③ 複雜藏好 ④ 外層簡單但全面 ⑤ 少背）。一輪一列。

| 輪 | 日期 | 玩什麼 | 報告 | 分數（①②③④⑤） |
|---|---|---|---|---|
| r1 | 2026-09-24 | proto5 重架構後全套：daemon→kernel、真 agent 一整圈、故意弄壞、第二個工具 | [astra](2026-09-24-r1-astra.md)、[Opus](2026-09-24-r1-opus.md)、[任務書](2026-09-24-r1-task.md) | astra 3/4/3/4/2、Opus 2/3/4/4/2 |
| r1 修正 | 2026-09-24 | 兩份報告的十條（A 文件＋小程式、B 碰設計）全做：十分鐘上手、check、init --env、stop 等停好、錯誤附路徑、agent stop 不讀 info、last、done/ | [fix-r1](fix-r1.md) | — |
| r2 | 2026-09-24 | fix-r1 之後：照 README 上手、只看規範架兩個 agent 共用 llm cpu、六類故障（含 daemon kill -9 重開）、自製工具 | [astra](2026-09-24-r2-astra.md)、[Opus](2026-09-24-r2-opus.md)、[任務書](2026-09-24-r2-task.md) | astra 4/3/3/4/2、Opus 4/3/3/4/3 |
| r2 修正 | 2026-09-24 | 兩份報告合併的六條全做：日常 CLI 最小版（init／say／status／continue）、daemon 重開提示 boot、check 驗 K 家目錄、小修一包；README 上手改 init＋say --wait | [fix-r2](fix-r2.md) | — |
