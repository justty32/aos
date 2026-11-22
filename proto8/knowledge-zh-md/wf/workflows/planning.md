# `knowledge/wf/workflows/planning.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/wf/workflows/planning.md`，跟到正本 commit `33835099a`（正本這頁最後一次改動）。這一庫本來就是中文，內容照抄正本，標題就是尋址。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

想法成熟管線（idea → roadmap → 詳規 → 執行）：從萌芽到動工的四階段收在同一條管線，不拆成四個工作流——免得卡在「這算 idea 還是 roadmap」。想法表與 roadmap 表長什麼樣在 `wf/skeletons/ideas.md`。

# when

- 使用者說「記個想法」「以後要做」「排進 roadmap」「幫我規劃」。
- 使用者說「討論方案」「寫動工計畫」（spec／plan，開發專案）→ 直接進詳規階段。

# not_when

- 三兩步的小事直接做。
- 已有 spec／plan 且在動工 → 執行工作流（開發：`wf/workflows/feature-dev.md`；非開發：本庫沒有對應的工作流，需要就自建）。
- 只是要調查清楚 → `wf/workflows/investigation.md`。

# done_when

- idea／roadmap：工作區的 `wf/knowledge/ideas.json` 對應的表（`ideas` 或 `roadmap`）多一筆，或既有那筆的狀態欄更新。
- 詳規：spec 有「方案／取捨」段、plan 有「步驟／驗證」段。
- 詳規動工完成後：那份 spec／plan 已移到各自的 `archive/`（工作區的 `wf/knowledge/specs/archive/`、`wf/knowledge/plans/archive/`）。

# stages

## 0

- stage: idea
- question: 要不要做？
- where: 工作區的 `wf/knowledge/ideas.json` 的 `ideas`（想法表）

## 1

- stage: roadmap
- question: 會做，何時？
- where: 工作區的 `wf/knowledge/ideas.json` 的 `roadmap`（roadmap 表）

## 2

- stage: 詳規
- question: 怎麼做？
- where: 開發：先 spec（方案）再 plan（動工前詳規），各一檔放工作區的 `wf/knowledge/specs/`、`wf/knowledge/plans/`（記錄進 knowledge、第一份出現時才建資料夾，見 `wf/layers.md#/skills 與 memory 分家`）。非開發：本庫沒有對應的工作流，需要就自建。

## 3

- stage: 執行
- question: —
- where: 開發：`wf/workflows/feature-dev.md`；非開發：本庫沒有對應的工作流，需要就自建。

# steps

- 照本檔 `#/stages` 判斷這件事在哪一階段（它回答的是哪個問題）。
- 工作區還沒有 `wf/knowledge/ideas.json` → 照 `wf/skeletons/ideas.md#/skeleton` 建。
- idea：在 `ideas` 加一筆（`idea` 想法、`summary` 一句話、`status` 狀態）。狀態只有三種：想想／會做→搬 roadmap／不做＋原因。
- roadmap：狀態變「會做」就搬進 `roadmap`，寫 `when`（何時／順序）與 `premise`（前提）。
- 詳規：開發先寫 spec 再寫 plan，spec 要有「方案／取捨」段、plan 要有「步驟／驗證」段（位置見本檔 `#/stages`）；動工完成後移各自的 `archive/`（封存規則見 `wf/tidying.md#/archive 規則`）。
- 執行：開發接 `wf/workflows/feature-dev.md`；非開發的本庫沒有對應的工作流，需要就自建。

# handoff

- 定下的決定 → `wf/workflows/decisions.md`。
- 卡在使用者 → 工作區的 `wf/progress.json` 記一條、status 寫「等使用者」（寫法見 `wf/knowledge/live-lists.md#/progress`）。
- 跨 session → 工作區的 `wf/progress.json` 記一條（寫法見 `wf/knowledge/live-lists.md#/progress`）。
