# `knowledge/wf/skeletons/code-map.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/wf/skeletons/code-map.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

**`#/_description`**：code map 的記憶骨架：程式碼導航 index（哪個領域在哪些檔、負責什麼、測試在哪）與本專案的真相層優先序。落在工作區的 `wf/knowledge/code-map.json`；讀法與維護鏈在 `wf/knowledge/code-map-rules.json`。

---

**`#/holds`**（原文是字串陣列，2 行）

- 放：領域表；本專案明確採用的真相層優先序。
- 不放：寫碼慣例（工作區的 `wf/knowledge/conventions.json`）；行為細節與規格（code map 是導航不是規格，行為以 code／tests 為準）；維護規則本身（`wf/knowledge/code-map-rules.json`）。

---

**`#/fields`**（物件，4 個鍵：`domains`、`truth_order`、`per_file`、`headline_rule`）

**`#/fields/domains`**：領域表，物件陣列：`domain`（領域名，例 匯入）、`files`（檔案，可用 glob，例 `src/import/*`）、`role`（一句話：這塊負責什麼）、`tests`（測試在哪，例 `tests/import/`）。

**`#/fields/truth_order`**：本專案的真相層優先序，一行字串。沒改就照抄預設 `code/tests > schema/examples/fixtures > code map > docs > generated`（`wf/knowledge/code-map-rules.json#/truth_order`）。

**`#/fields/per_file`**：（選用）有生成逐檔表時：`domains` 每列可加 `per_file`＝那個領域的逐檔表路徑（例 `wf/knowledge/code-map/src.json`）；做法見 `wf/knowledge/code-map-rules.json#/per_file_table`。

**`#/fields/headline_rule`**：（選用）有生成逐檔表時：各種檔的檔頭一句話寫在哪、怎麼重生，字串陣列一行一條。

---

**`#/rules`**（原文是字串陣列，5 行）

- **一列一個領域、不是一列一個檔**；檔案欄可用 glob。
- 表大到難讀就按領域拆成工作區的 `wf/knowledge/code-map/` 夾，上層留入口（拆法見 `wf/tidying.json#/split_method`）。
- 優先序可以改，但必須明確寫在 `truth_order`。
- 原始碼裡**不加**「對應 code map」的註釋；反向查找直接搜這份。
- 記錄是物件陣列，用 json 工具讀寫（`aos/packs.json#/json`）。

---

**`#/skeleton`**（物件，2 個鍵：`domains`、`truth_order`）

**`#/skeleton/domains`**：`[]`（空陣列）

**`#/skeleton/truth_order`**：（空字串）
