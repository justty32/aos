# `knowledge/wf/knowledge/dev-dispatch.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/wf/knowledge/dev-dispatch.md`，跟到正本 commit `33835099a`（正本這頁最後一次改動）。這一庫本來就是中文，內容照抄正本，標題就是尋址。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

開發類工作流怎麼派：碰原始碼前先讀什麼、幾條容易混的工作流（analysis／investigation／patch／feature-dev／planning）怎麼分、本庫沒附的開發工作流去哪。派發通則（怎麼選工作流、什麼時候可以跳流程、都不符去哪）在 `wf/workflows/_description.md`；各工作流的觸發說法在 `wf/workflows/_index.json`。

# before_code

**碰原始碼前**：慣例與 code map → 工作區的 `wf/knowledge/conventions.json`、`wf/knowledge/code-map.json`；環境與指令 → 工作區的 `wf/knowledge/dev-env.json`。碰原始碼的工作流（feature-dev、refactor 與搬移專章 moving-things、investigation）都共用這兩份，各自的 steps 開頭也寫了這一步；還沒有就照 `wf/skeletons/conventions.md#/skeleton`、`wf/skeletons/code-map.md#/skeleton` 建。always-on：落地後放工作區 `AGENTS.md` 的入口行（`wf/knowledge/iron-rules.md#/agents_md_entry`）。

# disambiguation

- **analysis** ＝初次接觸陌生專案、要建立可延續的分析產物；**investigation** ＝回答一個窄問題。
- **patch** ＝跨 repo、原專案無 git 或不能直接 push、要交給冷啟動 agent 套用時才用；同一個 repo 內能改能測就走 feature-dev。
- 「討論方案」「寫動工計畫」（spec／plan）→ `wf/workflows/planning.md`（planning 管線的後兩段），定案後動工走 feature-dev。

# menu

本庫沒附、需要時才建的開發工作流（新工作流照 `wf/nodes.md#/工作流的統一形式` 從單節點長起，並在工作區的 `wf/workflows/_index.json` 加一格）：

- idea（要不要做）／roadmap（會做，何時）／spec（討論後方案）／plan（動工前詳規）：已合成一條 planning 管線（`wf/workflows/planning.md`）。四個是同一個想法的四個階段，分四份會讓 agent 卡在「這算 idea 還是 roadmap」。
- tooling（工具設定、env var、依賴）：併在 `wf/workflows/dev-env.md`——那些本來就是環境的一部分。
- release／deploy／incident（維運類）、review／benchmark／migration：本庫沒有，需要就自建。
