# aos 與 coding agent、skills、MCP 的協作

這場紀錄已拆成資料夾：[tool-interop/README.md](tool-interop/README.md)（檔頭表格、500 字懶人包與續場資訊都在那裡）。

| 檔案 | 裡面有什麼 | 什麼時候會想看 |
|---|---|---|
| [本場索引（含懶人包）](tool-interop/README.md) | 檔頭表格、〈先讀這段（500 字懶人包）〉、本場兩輪的來由、〈續場資訊〉 | 第一次讀這場，或要找 codex session id |
| [追問輪：`aos deliver` 的形狀](tool-interop/deliver-tool.md) | 〈追問輪：那支投遞 tool 到底長什麼樣〉（合成版 `--help`、寫到哪裡檔名怎麼配、退出碼、誰驗證驗不過怎麼回）、〈給模型看的錯誤訊息〉、〈最小 tool 組〉、〈一套 CLI 能不能同時服務 skill／MCP／腳本〉、〈四位收回／改寫的〉 | 要動手定 Deliver 的參數、JSON、退出碼或驗證責任時 |
| [主輪：分層與各入口怎麼接](tool-interop/entry-points.md) | 〈主輪：aos 怎麼跟現有工具協作〉（pi 前提、誰在上面誰在下面、stdout→stdin、session 只可當快取）、〈skills 怎麼接〉、〈MCP 怎麼接，或為什麼 pi 不接〉、〈權限這塊〉、〈把這場研討會搬到 aos 上〉 | 要接 pi／MCP／skill，或要決定權限與 session 怎麼放時 |
| [未決問題與明顯的坑](tool-interop/open-issues.md) | 〈大家問出來的問題〉九題、〈明顯的坑〉 | 想知道本場哪些還沒有答案、哪些做法已被四位否掉 |
| [轉交提案](tool-interop/handoff.md) | 〈轉交提案（未拍板，不自行改規格／roadmap）〉八條 | **要決定下一步做什麼時從這裡開始。** |
