# `knowledge/wf/skeletons/notes.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/wf/skeletons/notes.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

**`#/_description`**：調查筆記的記憶骨架：一個主題一篇，問題、方法、發現、結論、來源。落在工作區的 `wf/knowledge/notes/<主題>.json`；流程在 `wf/workflows/investigation.json`。

---

**`#/holds`**（原文是字串陣列，2 行）

- 放：一次調查回答的一個窄問題，連同查了什麼、看到什麼、出處。
- 不放：初次接觸陌生專案的整套分析（工作區的 `wf/knowledge/analysis/<project>/`，`wf/skeletons/analysis.json`）；踩坑（工作區的 `wf/knowledge/gotchas.json`）；決定（工作區的 `wf/knowledge/decisions.json`）。

---

**`#/fields`**（物件，6 個鍵：`_description`、`question`、`method`、`findings`、`conclusion`、`sources`）

**`#/fields/_description`**：主題一句話。

**`#/fields/question`**：**問題**：要回答什麼，一句話。

**`#/fields/method`**：**方法**：讀了哪些檔、跑了什麼指令。字串陣列，一條一則。

**`#/fields/findings`**：**發現**：一條一則事實，附出處。字串陣列。

**`#/fields/conclusion`**：**結論**：直接回答問題；不確定就寫缺什麼。

**`#/fields/sources`**：**來源**：檔案路徑＋行號、指令輸出、連結。字串陣列。

---

**`#/index`**（原文是字串陣列，3 行）

- 筆記夾的入口：工作區的 `wf/knowledge/notes/_description.json` 寫這夾是什麼。夾裡東西多（門檻見 knowledge 的 `docs/01`）或要靠 description 挑讀哪篇時放 `_index.json`，一篇一格：
- `{"<主題>.json": {"description": "日期、一句結論、何時讀"}}`
- 有 `_index.json` 就每篇都要列。

---

**`#/rules`**（原文是字串陣列，3 行）

- **不把未驗證的猜測寫成結論**——不確定就寫「缺什麼證據」，不要補完。
- 五段都要非空。
- 一篇連貫的調查筆記本質不可分，可以超過大小建議保留（`wf/tidying.json#/split`）；過時的照 `wf/tidying.json#/archive` 封存。

---

**`#/skeleton`**（物件，6 個鍵：`_description`、`question`、`method`、`findings`、`conclusion`、`sources`）

**`#/skeleton/_description`**：（空字串）

**`#/skeleton/question`**：（空字串）

**`#/skeleton/method`**：`[]`（空陣列）

**`#/skeleton/findings`**：`[]`（空陣列）

**`#/skeleton/conclusion`**：（空字串）

**`#/skeleton/sources`**：`[]`（空陣列）
