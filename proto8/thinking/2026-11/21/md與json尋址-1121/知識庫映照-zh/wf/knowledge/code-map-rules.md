# `knowledge/wf/knowledge/code-map-rules.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/wf/knowledge/code-map-rules.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

**`#/_description`**：code map 的通用規則：預設真相層優先序、衝突時誰為準、維護鏈（改碼前怎麼讀、改完怎麼更新）。每個專案都一樣；專案自己的領域表與優先序在工作區的 `wf/knowledge/code-map.json`（骨架 `wf/skeletons/code-map.json`）。

---

**`#/truth_order`**（原文是字串陣列，10 行）

各專案可以改自己的優先序，但必須明確。預設：

```text
code/tests > schema/examples/fixtures > code map > docs > generated
```

- 上層與下層衝突時，**以上層為準並修正下層**。
- generated（產生出來的檔、html）永遠不是唯一真相。
- 原始來源與摘要衝突時，以**原始來源**為準。
- code map 是**導航不是規格**；行為以 code/tests 為準。

---

**`#/maintenance_chain`**（原文是字串陣列，8 行）

**維護鏈：程式碼 > code map > 文檔**。

**優先級**（衝突或時間不夠時，依序保持一致）：程式碼 > code map > 文檔。**code map 與程式碼衝突時以程式碼為準，立刻改 code map。**

1. **修改前**：先讀 code map 找到相關領域，只讀清單裡的檔——不讀無關領域的檔。
2. **修改後**：新增／刪除了原始碼檔案，或某檔職責顯著改變，必須同步更新 code map。
3. 原始碼裡**不加**「對應 code map」的註釋（維護成本過高）；反向查找直接搜 code map。
4. 迭代期間 code map 可暫時落後，**commit 前必須對齊**（見 `wf/workflows/feature-dev.json`）。

---

**`#/per_file_table`**（原文是字串陣列，4 行）

**逐檔表（選用）**：程式檔多到手寫領域表顧不到每個檔時，可以讓每個檔的檔頭第一行寫一句「它負責什麼」，用生成器從檔頭產出逐檔表，放在工作區的 `wf/knowledge/code-map/`（例：一個頂層夾一份 json，照資料夾巢狀、葉子是那一句話）。
- 逐檔表是**生成物、不手改**：要改說明去改檔頭再重生，生成物跟程式同一個 commit。
- 手寫的 `wf/knowledge/code-map.json` 仍是入口：領域表每列用 `per_file` 指到對應的逐檔表；檔頭一句話寫在哪（各語言）記在 `headline_rule`。
- 生成器由各專案自己接（例：aos repo 的 `wf/tools/index_gen.py`），這裡不提供通用版。
