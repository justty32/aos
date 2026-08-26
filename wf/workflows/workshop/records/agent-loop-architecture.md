# agent loop 的實作架構與基礎 `aos core` 功能
← [workshop](../README.md)｜前一場：[四個懸而未決的設計選擇](four-open-choices-tradeoffs.md)

這份研討會紀錄已按內容職責拆進 [`agent-loop-architecture/`](agent-loop-architecture/README.md)；
懶人包、檔頭表格與續場 session id 都在那份 README。

| 檔案 | 裡面有什麼 | 什麼時候會想看 |
|---|---|---|
| [README](agent-loop-architecture/README.md) | 500 字懶人包、檔頭表格（主題／輪數／參與身份／缺哪個角度）、續場 session id。 | 先讀這份 |
| [R1：想法池](agent-loop-architecture/r1-ideas.md) | R1 四位各自發想。`aos core` 該收掉什麼（deliver／effect／publish／recover 候選表）、agent loop 是磁碟上的耐久狀態機、一個完整循環怎麼走、斷點續跑的硬邊界，外加還在生長的想法、大家問出來的問題、明顯的坑。 | 想知道 agent loop 的架構長什麼樣、`unknown` 為什麼不能自動重跑 |
| [R2：收攏成三個原語](agent-loop-architecture/r2-three-primitives.md) | R2 把 R1 的不同命名收成 Publish／Deliver／Effect 三個功能家族：合併後的功能清單、依賴鏈、「只能先做三樣」的一致選擇、不該進 `aos core` 的、還缺的一塊。 | 想知道基礎 `aos core` 功能收窄成哪幾項、什麼刻意留在腳本 |
| **[轉交提案](agent-loop-architecture/handoff.md)** | **要使用者拍板才足以改規格／roadmap 的六項提案。** | **要拍板時看這份** |
