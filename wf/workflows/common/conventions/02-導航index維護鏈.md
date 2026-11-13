← [入口](../conventions.md)｜涵蓋：導航 index（code map）維護鏈｜上一份 [01-程式碼慣例](01-程式碼慣例.md)

## 導航 index（code map）維護鏈

三個面向構成維護鏈：**程式碼 → code map → 文檔**。三份真相的完整優先序（含 normative 規格）在 [`wf/knowledge/code-map.json`](../../../knowledge/code-map.json) 的 `truth_order`、`truth_rules`。

**優先級（衝突或時間不夠時，依序保持一致）：** 程式碼 > code map > 文檔。
**code map 與程式碼衝突時：以程式碼為準，立即修正 code map。**

**日常規則**（逐檔表由程式生成，使用者裁「七題照推薦」，[thinking arch-refactor](../../../../proto8/thinking/2026-11/05/arch-refactor/README.md)）：
1. **修改前**：先讀 [`wf/knowledge/code-map.json`](../../../knowledge/code-map.json)（`domains` 找到夾），再用 `json_get` 查逐檔表 `wf/knowledge/code-map/proto8/<頂層夾>.json#/tree/<夾>`，只讀列出的檔——不要讀無關領域的檔案。
2. **檔頭一句話就是 code map 的來源**：每個程式檔第一行（腳本跳過 shebang 的第一行、Python 可以是 docstring 第一行；JSON 用 `description`）寫「它負責什麼」一句話。新增檔一定要寫；職責變了改那一句。
3. **commit 前跑 `python3 wf/tools/index_gen.py --apply`**（一支：程式區的 `_index.json` 與 `wf/knowledge/code-map/` 逐檔表一次重生；11-13 使用者「code map這塊，就按照推薦。」），生成物跟程式同一個 commit；不帶 `--apply`＝只檢查（不一致印 `CodemapStale`／`IndexStale`、退 1）。舊指令 `codemap_gen.py --apply` 過渡期是轉呼叫它的薄殼。`wf/knowledge/code-map/` 底下不要手改；一句話空或只寫檔名只算數不擋，順手補。
4. 手寫的只剩 [`wf/knowledge/code-map.json`](../../../knowledge/code-map.json)（領域 `domains`、常查表 `lookup`、真相層優先序；proto8 頂層夾增減時要跟著改）與各程式 README 的**行為**說明；README 不再放逐檔表。
5. 原始碼檔案本身**不加**「對應 code map」的註釋；反向查找搜逐檔表（`json_search`，或 `rg 詞 wf/knowledge/code-map/`）。
