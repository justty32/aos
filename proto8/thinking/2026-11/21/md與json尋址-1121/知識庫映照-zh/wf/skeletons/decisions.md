# `knowledge/wf/skeletons/decisions.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/wf/skeletons/decisions.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

**`#/_description`**：決策記錄表的骨架：專案定下了什麼、從誰來、前提是什麼。落點是工作區的 `wf/knowledge/decisions.json`；何時記、怎麼記在 `wf/workflows/decisions.json`。

---

**`#/holds`**（原文是字串陣列，3 行）

- 放：在兩個以上可行方案裡選定的結論、它的來源（使用者原文或誰定的）、它成立的前提。
- 不放：比較過的方案、未選原因、AI 寫的理由——要查靠 git 歷史。
- 不放：「改了什麼」——交給 git log。

---

**`#/fields`**（物件，4 個鍵：`date`、`decision`、`origin`、`premise`）

**`#/fields/date`**：日期（YYYY-MM-DD）

**`#/fields/decision`**：決定：定了什麼，寫結論。不可空。

**`#/fields/origin`**：來源：使用者原文（逐字），或寫誰定的。

**`#/fields/premise`**：前提：這個決定成立靠什麼；前提變了就重看。不可空。

---

**`#/rules`**（原文是字串陣列，5 行）

- 記錄寫成物件陣列放在 `records`，用 json 工具讀寫。
- 新的在上：新的一筆加在陣列最前。
- `decision`、`premise` 兩欄非空才算記完。
- 條目多到難讀 → 升級成資料夾（工作區的 `wf/knowledge/decisions/`）、一決策一檔，拆法照 `wf/tidying.json#/split_method`。
- `skeleton` 裡的路徑是工作區裡的路徑。

---

**`#/skeleton`**（物件，2 個鍵：`_description`、`records`）

**`#/skeleton/_description`**：決策記錄：定了什麼、從誰來、前提是什麼。只記結論、來源與前提；比較過的方案與理由不記，要查靠 git 歷史。新的在上；怎麼記見 `wf/workflows/decisions.json`。

**`#/skeleton/records`**：`[]`（空陣列）
