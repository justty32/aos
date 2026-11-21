# `knowledge/wf/skeletons/ideas.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/wf/skeletons/ideas.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

**`#/_description`**：planning 的兩張表的骨架：想法表（要不要做）與 roadmap 表（會做，何時）。落點是工作區的 `wf/knowledge/ideas.json`；怎麼用在 `wf/workflows/planning.json`。

---

**`#/holds`**（原文是字串陣列，3 行）

- 放：還在想要不要做的想法（`ideas`）、決定會做的事與它的時機和前提（`roadmap`）。
- 不放：spec／plan——各一檔放工作區的 `wf/knowledge/specs/`、`wf/knowledge/plans/`（`wf/layers.json#/skills_vs_memory`）。
- 不放：定下的決定——進工作區的 `wf/knowledge/decisions.json`。

---

**`#/fields`**（物件，2 個鍵：`ideas`、`roadmap`）

---

**`#/fields/ideas`**（物件，3 個鍵：`idea`、`summary`、`status`）

**`#/fields/ideas/idea`**：想法（短名）

**`#/fields/ideas/summary`**：一句話說它是什麼

**`#/fields/ideas/status`**：狀態，只有三種：想想／會做→搬 roadmap／不做＋原因

---

**`#/fields/roadmap`**（物件，3 個鍵：`item`、`when`、`premise`）

**`#/fields/roadmap/item`**：事項

**`#/fields/roadmap/when`**：何時／順序

**`#/fields/roadmap/premise`**：前提

---

**`#/rules`**（原文是字串陣列，4 行）

- 兩張表都寫成物件陣列，用 json 工具讀寫。
- 想法狀態變「會做」→ 搬進 `roadmap`；「不做」要寫原因。
- 更新狀態就改既有那筆，不另開一筆。
- `skeleton` 裡的路徑是工作區裡的路徑。

---

**`#/skeleton`**（物件，3 個鍵：`_description`、`ideas`、`roadmap`）

**`#/skeleton/_description`**：planning 的想法表（`ideas`：要不要做）與 roadmap 表（`roadmap`：會做，何時）。想法狀態：想想／會做→搬 roadmap／不做＋原因。怎麼用見 `wf/workflows/planning.json`。

**`#/skeleton/ideas`**：`[]`（空陣列）

**`#/skeleton/roadmap`**：`[]`（空陣列）
