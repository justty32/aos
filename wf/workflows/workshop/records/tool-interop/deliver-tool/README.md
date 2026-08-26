# 追問輪：`aos deliver` 的形狀

← [本場索引](../README.md)｜[workshop](../../../README.md)

追問輪的收攏原本是一份 8.9 KB 的單檔，照 [DEV-GUIDE](../../../../../DEV-GUIDE.md) 的「膨脹即拆」再拆成兩份：一份是投遞命令自己的介面與錯誤契約，一份是它之外的 tool 組、單一 CLI 語意與被收回的自然語言 adapter。

| 檔案 | 裡面有什麼 | 什麼時候會想看 |
|---|---|---|
| [`aos deliver` 這支命令長什麼樣](deliver-interface.md) | 〈追問輪：那支投遞 tool 到底長什麼樣〉（合成版 `--help`、寫到哪裡檔名怎麼配、退出碼還沒有共同編號、誰驗證驗不過怎麼回）、〈給模型看的錯誤訊息〉 | 要動手定 Deliver 的參數、寫檔順序、退出碼、驗證責任或錯誤 JSON 時 |
| [最小 tool 組、一套 CLI，與四位收回的](tool-set-and-retractions.md) | 〈最小 tool 組〉、〈一套 CLI 能不能同時服務 skill／MCP／腳本〉、〈四位收回／改寫的〉 | 要決定總共做哪幾支 tool、要不要另寫一套 MCP 語意，或想確認哪些主輪設計已被收回時 |
