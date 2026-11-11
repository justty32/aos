# knowledge-fix：出廠知識庫修整與補全（11-11，線 C）

← [2026-11-11](../README.md)｜[thinking](../../../README.md)｜盤點摘要 [01](01-盤點摘要.md)｜施工結果、代定、warning、待裁 [02](02-施工結果與待裁.md)｜六題裁定與施工（線 I）[03](03-六題裁定與施工.md)

## 使用者原話與裁定（11-11）

調查員只讀盤點 `proto8/knowledge/` 後，使用者在選項框裁了這幾題：

- knowledge_write 寫哪：「不給預設，要自己透過旗標指定或環境變數設定，或是工具呼叫內給。如果都沒有，那就報錯。」頂層的理解是**只管「寫」**，`knowledge_read` 範本照舊指出廠庫（開場的知識庫根靠它）；頂層跟使用者說明過這個理解，他沒反對。
- thought：「放進某一包」→「小工具那包」（`lib/packs/gadgets.json`）。
- 寫多細：「每支都有節點」——每支登記的工具、每支 `aos-*` 指令在知識庫都有自己的節點。
- 開場：「照現在只帶目錄」＝不動。
- 大小：「這個"不超過2kb"我沒說過，拿掉。不過也可以用，我的建議是改成一個檔案不超過8kb，一段不超過1kb。」「那個知識庫上限，只是推薦，不要訂死。」

同一線先做的 children 系改名（使用者「隊長那串...一起改吧」）記在 [subagent-rename](../subagent-rename.md)。

## 決定

- knowledge_write 找根：`--root`（人釘死）＞ 呼叫參數 `root`（新增，相對 `$AOS_WS`、沒設從 cwd）＞ 工具夾 `_knowledge.json` ＞ `AOS_KNOWLEDGE`；都沒有＝`KnowledgeMissing`（訊息教腦給 `root` 或請人設 `AOS_KNOWLEDGE`、不要寫讀的那個庫）。兩範本拿掉 knowledge_write 那格的 env；knowledge_read 不動。export／sync 本來就沒有預設，不動。
- thought 進 gadgets 包，兩範本十一包 36 支。
- 每支工具一個節點（`aos/tools/<名>.json`，self_*、subagent 等原有的照舊），每支指令一個節點（`aos/cli/`，impls 零件在 `aos/cli/parts/`）；tooldef 都帶 `Details:`。
- 大小改推薦口氣（一檔約 8 KB、一段約 1 KB）；超長的能自然拆就拆、原路徑放 `$ref` 不變。
- 新檢查 `lib/aos/knowledge_check`（指標、`_index`、覆蓋、錯誤代號、開發殘留、大小），出廠庫 0 錯誤進測試；大小與代號結尾只 warning。

## 結論

施工完，出廠庫檢查 0 錯誤、42 warning，見 [02](02-施工結果與待裁.md)。代號結尾等六題 11-11 使用者已裁、線 I 施工完，見 [03](03-六題裁定與施工.md)。
