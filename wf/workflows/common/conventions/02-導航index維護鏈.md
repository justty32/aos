← [入口](../conventions.md)｜涵蓋：導航 index（code map）維護鏈｜上一份 [01-程式碼慣例](01-程式碼慣例.md)

## 導航 index（code map）維護鏈

三個面向構成維護鏈：**程式碼 → code map → 文檔**。三份真相的完整優先序（含 normative 規格）在 [code-map「真相層優先序」](../code-map.md)。

**優先級（衝突或時間不夠時，依序保持一致）：** 程式碼 > code map > 文檔。
**code map 與程式碼衝突時：以程式碼為準，立即修正 code map。**

**日常規則**（逐檔表由程式生成，使用者裁「七題照推薦」，[thinking arch-refactor](../../../../proto8/thinking/2026-11/05/arch-refactor/README.md)）：
1. **修改前**：先讀 code map 地圖，再到[生成冊](../code-map/proto8/README.md)找相關的夾，只讀列出的檔——不要讀無關領域的檔案。
2. **檔頭一句話就是 code map 的來源**：每個程式檔第一行（腳本跳過 shebang 的第一行、Python 可以是 docstring 第一行；JSON 用 `description`）寫「它負責什麼」一句話。新增檔一定要寫；職責變了改那一句。
3. **commit 前跑 `python3 wf/tools/codemap_gen.py --apply`**，生成冊跟程式同一個 commit；不帶參數＝只檢查（不一致退 1）。生成冊不要手改；一句話空或只寫檔名會印 warning，順手補。
4. 手寫的只剩 [code-map](../code-map.md) 地圖（夾一句話、常查表、真相層優先序）與各程式 README 的**行為**說明；README 不再放逐檔表。
5. 原始碼檔案本身**不加**「對應 code map」的註釋；反向查找 grep 生成冊。
