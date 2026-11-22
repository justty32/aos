# `knowledge/wf/workflows/decisions.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/wf/workflows/decisions.md`，跟到正本 commit `33835099a`（正本這頁最後一次改動）。這一庫本來就是中文，內容照抄正本，標題就是尋址。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

記決定：留下「定了什麼」與它成立的前提。git log 找得回改了什麼，找不回當時定下的規則與它成立的前提；只記結論、前提與使用者原文，比較過的方案與 AI 寫的理由不記，要查靠 git 歷史。記錄表長什麼樣在 `wf/skeletons/decisions.md`。

# when

- 在兩個以上可行方案裡選了一個，且日後可能被問「當初定的是什麼、還成立嗎」。
- 使用者說「記個決定」「為什麼選 A 不選 B」。

# not_when

- 只有一條路，或隨時可回頭的小事：不記。
- 決策過程要結構化評估（攤選項、準則、逐項評估）→ 本庫沒有這種工作流，需要就自建（骨架 `wf/knowledge/workflow-template.md`），結論再落到這裡。

# done_when

- 工作區的 `wf/knowledge/decisions.json` 的 `records` 新增一筆，且 `decision`（決定）、`premise`（前提）兩欄非空。

# steps

- 工作區還沒有 `wf/knowledge/decisions.json` → 照 `wf/skeletons/decisions.md#/skeleton` 建。
- 在 `records` 加一筆，新的在上（加在陣列最前），用 json 工具寫。
- 填四欄：`date`（日期）、`decision`（決定）、`origin`（來源：使用者原文，或誰定的）、`premise`（前提，變了就重看）；欄意見 `wf/skeletons/decisions.md#/fields`。
- 只寫結論、前提與使用者原文：比較過的方案、AI 寫的理由不寫，要查靠 git 歷史（「只留現行結論」的判準在 `wf/knowledge/content-trim.md`）。
- 條目多到難讀 → 升級成資料夾、一決策一檔，照 `wf/nodes.md#/一個工作流的成長軌跡（四級）` 與 `wf/tidying.md#/拆法（兩種觸發都照做）`。

# handoff

- 記完回到觸發它的工作流繼續。
- 日後某筆的前提變了 → 回頭重看那一筆。
