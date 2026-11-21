# `knowledge/wf/workflows/decisions.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/wf/workflows/decisions.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

**`#/_description`**：記決定：留下「定了什麼」與它成立的前提。git log 找得回改了什麼，找不回當時定下的規則與它成立的前提；只記結論、前提與使用者原文，比較過的方案與 AI 寫的理由不記，要查靠 git 歷史。記錄表長什麼樣在 `wf/skeletons/decisions.json`。

---

**`#/when`**（原文是字串陣列，2 行）

- 在兩個以上可行方案裡選了一個，且日後可能被問「當初定的是什麼、還成立嗎」。
- 使用者說「記個決定」「為什麼選 A 不選 B」。

---

**`#/not_when`**（原文是字串陣列，2 行）

- 只有一條路，或隨時可回頭的小事：不記。
- 決策過程要結構化評估（攤選項、準則、逐項評估）→ 本庫沒有這種工作流，需要就自建（骨架 `wf/knowledge/workflow-template.json`），結論再落到這裡。

**`#/done_when`**（原文是字串陣列，1 行）：工作區的 `wf/knowledge/decisions.json` 的 `records` 新增一筆，且 `decision`（決定）、`premise`（前提）兩欄非空。

---

**`#/steps`**（原文是字串陣列，5 行）

- 工作區還沒有 `wf/knowledge/decisions.json` → 照 `wf/skeletons/decisions.json#/skeleton` 建。
- 在 `records` 加一筆，新的在上（加在陣列最前），用 json 工具寫。
- 填四欄：`date`（日期）、`decision`（決定）、`origin`（來源：使用者原文，或誰定的）、`premise`（前提，變了就重看）；欄意見 `wf/skeletons/decisions.json#/fields`。
- 只寫結論、前提與使用者原文：比較過的方案、AI 寫的理由不寫，要查靠 git 歷史（「只留現行結論」的判準在 `wf/knowledge/content-trim.json`）。
- 條目多到難讀 → 升級成資料夾、一決策一檔，照 `wf/nodes.json#/growth` 與 `wf/tidying.json#/split_method`。

---

**`#/handoff`**（原文是字串陣列，2 行）

- 記完回到觸發它的工作流繼續。
- 日後某筆的前提變了 → 回頭重看那一筆。
