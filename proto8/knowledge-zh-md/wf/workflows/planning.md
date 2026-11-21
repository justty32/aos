# `knowledge/wf/workflows/planning.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/wf/workflows/planning.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

**`#/_description`**：想法成熟管線（idea → roadmap → 詳規 → 執行）：從萌芽到動工的四階段收在同一條管線，不拆成四個工作流——免得卡在「這算 idea 還是 roadmap」。想法表與 roadmap 表長什麼樣在 `wf/skeletons/ideas.json`。

---

**`#/when`**（原文是字串陣列，2 行）

- 使用者說「記個想法」「以後要做」「排進 roadmap」「幫我規劃」。
- 使用者說「討論方案」「寫動工計畫」（spec／plan，開發專案）→ 直接進詳規階段。

---

**`#/not_when`**（原文是字串陣列，3 行）

- 三兩步的小事直接做。
- 已有 spec／plan 且在動工 → 執行工作流（開發：`wf/workflows/feature-dev.json`；非開發：本庫沒有對應的工作流，需要就自建）。
- 只是要調查清楚 → `wf/workflows/investigation.json`。

---

**`#/done_when`**（原文是字串陣列，3 行）

- idea／roadmap：工作區的 `wf/knowledge/ideas.json` 對應的表（`ideas` 或 `roadmap`）多一筆，或既有那筆的狀態欄更新。
- 詳規：spec 有「方案／取捨」段、plan 有「步驟／驗證」段。
- 詳規動工完成後：那份 spec／plan 已移到各自的 `archive/`（工作區的 `wf/knowledge/specs/archive/`、`wf/knowledge/plans/archive/`）。

---

**`#/stages`**（陣列，4 項）

---

**`#/stages/0`**（物件，3 個鍵：`stage`、`question`、`where`）

**`#/stages/0/stage`**：idea

**`#/stages/0/question`**：要不要做？

**`#/stages/0/where`**：工作區的 `wf/knowledge/ideas.json` 的 `ideas`（想法表）

---

**`#/stages/1`**（物件，3 個鍵：`stage`、`question`、`where`）

**`#/stages/1/stage`**：roadmap

**`#/stages/1/question`**：會做，何時？

**`#/stages/1/where`**：工作區的 `wf/knowledge/ideas.json` 的 `roadmap`（roadmap 表）

---

**`#/stages/2`**（物件，3 個鍵：`stage`、`question`、`where`）

**`#/stages/2/stage`**：詳規

**`#/stages/2/question`**：怎麼做？

---

**`#/stages/2/where`**

開發：先 spec（方案）再 plan（動工前詳規），各一檔放工作區的 `wf/knowledge/specs/`、`wf/knowledge/plans/`（記錄進 knowledge、第一份出現時才建資料夾，見 `wf/layers.json#/skills_vs_memory`）。非開發：本庫沒有對應的工作流，需要就自建。

---

**`#/stages/3`**（物件，3 個鍵：`stage`、`question`、`where`）

**`#/stages/3/stage`**：執行

**`#/stages/3/question`**：—

**`#/stages/3/where`**：開發：`wf/workflows/feature-dev.json`；非開發：本庫沒有對應的工作流，需要就自建。

---

**`#/steps`**（原文是字串陣列，6 行）

- 照本檔 `#/stages` 判斷這件事在哪一階段（它回答的是哪個問題）。
- 工作區還沒有 `wf/knowledge/ideas.json` → 照 `wf/skeletons/ideas.json#/skeleton` 建。
- idea：在 `ideas` 加一筆（`idea` 想法、`summary` 一句話、`status` 狀態）。狀態只有三種：想想／會做→搬 roadmap／不做＋原因。
- roadmap：狀態變「會做」就搬進 `roadmap`，寫 `when`（何時／順序）與 `premise`（前提）。
- 詳規：開發先寫 spec 再寫 plan，spec 要有「方案／取捨」段、plan 要有「步驟／驗證」段（位置見本檔 `#/stages`）；動工完成後移各自的 `archive/`（封存規則見 `wf/tidying.json#/archive`）。
- 執行：開發接 `wf/workflows/feature-dev.json`；非開發的本庫沒有對應的工作流，需要就自建。

---

**`#/handoff`**（原文是字串陣列，3 行）

- 定下的決定 → `wf/workflows/decisions.json`。
- 卡在使用者 → 工作區的 `wf/progress.json` 記一條、status 寫「等使用者」（寫法見 `wf/knowledge/live-lists.json#/progress`）。
- 跨 session → 工作區的 `wf/progress.json` 記一條（寫法見 `wf/knowledge/live-lists.json#/progress`）。
