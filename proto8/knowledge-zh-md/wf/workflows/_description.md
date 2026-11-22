# `knowledge/wf/workflows/_description.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/wf/workflows/_description.md`，跟到正本 commit `33835099a`（正本這頁最後一次改動）。這一庫本來就是中文，內容照抄正本，標題就是尋址。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

# 出廠的工作流節點

做事的流程，一個工作流一個節點。這一夾照工作區 `wf/workflows/` 的佈局放：節點裡寫的 `wf/workflows/…`、`wf/knowledge/…` 路徑，在本庫與在工作區讀起來是同一個位置——可以直接照這裡的做，也可以把節點抄進工作區的 `wf/workflows/` 再照專案改。例外：指到 `wf/tidying.md`、`wf/nodes.md`、`wf/layers.md` 的是本庫頂層的組織原則，指到 `wf/skeletons/…` 的是本庫的記憶骨架；工作區裡沒有這些，要看就讀知識庫。另外 `wf/knowledge/` 底下本庫出廠的幾份（`workflow-template`、`content-trim`、`gotchas` 的 `tidy_` 各段、`live-lists`、`iron-rules`、`code-map-rules`、`green-is-not-checked`、`dev-dispatch`）是通用規則；節點寫「工作區的 `wf/knowledge/…`」的是專案自己的記錄。

節點的固定形式見 `wf/nodes.md#/工作流的統一形式`，骨架在 `wf/knowledge/workflow-template.md`。有哪些工作流、各自的觸發說法看本夾 `_index.json`（它就是派發表）。

## 派發

使用者要做事 → 從工作區的 `wf/workflows/_index.json`（派發表：每格 description 含觸發說法；工作區還沒有就看本夾的）選工作流 → 讀那個工作流節點；細節都在節點裡。開發類幾條容易混的怎麼分、碰原始碼前先讀什麼，在 `wf/knowledge/dev-dispatch.md`。

**可以跳流程**：單行或小範圍、低風險、不跨 session 的修正；純查詢或一次性回答，不留 durable 知識；使用者明確要求快速處理；既有工作流只會增加同步成本而不降低風險。跳流程不等於跳過工程規矩——仍要讀必要上下文、不破壞使用者改動、能測就測。

**都不符**：

- 派發表都不符 → 看工作區的 `wf/_index.json`（wf 這層的 index，往下有 `wf/knowledge/_index.json`）。
- 新開工作流 → 照 `wf/nodes.md#/工作流的統一形式` 的固定形式寫一個節點（骨架 `wf/knowledge/workflow-template.md`），並在工作區的 `wf/workflows/_index.json` 加一格（description 含觸發說法）。
- 要定期喚醒、多 agent 協作這類工作流本庫沒有，需要就自建。

**活狀態**記哪裡（等使用者／等同 repo 另一個 session／等別資料夾的 agent）在 `wf/knowledge/live-lists.md#/which`；只列 open、完成即刪（`wf/layers.md#/分層原則` 第 3 條），這裡不重抄。
