**真問題**

- `proto5/README.md:61–62`：`add --once` 未帶 `--wait-ms` 時只印請求名稱與回音路徑，立即退 0；不代表 kernel 已收單回音，現有敘述漏了條件。（既有問題）

**小問題**

- `wf/session_logs/README.md:20`：文字涵蓋「WAIT_USER 集中說明」，但只連到「最小原型」；缺少 `2026-08.md:31` 那個獨立 `##` 節的直接連結。
- `proto5/README.md:100`：「三行各印 `stopped`」不精確；agent 實際印 `stopped agent-bob`。（既有問題）

**其餘通過**

非 spec 的 `BROKEN`＝0；102 條 archive 連結指向正確；行號轉換未見重複、括號或表格破壞。notes、rearch、repo 頂層索引無漏項。09-24 全文僅連結多一層 `../`，open 與 (a)～(f) 完整，SESSION-LOG **2567 bytes**。WAIT_USER 未見遺失仍 open 的內容或改變原意。

全程唯讀，未開服務、未碰模型。