# `knowledge/wf/knowledge/iron-rules.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/wf/knowledge/iron-rules.md`，跟到正本 commit `33835099a`（正本這頁最後一次改動）。這一庫本來就是中文，內容照抄正本，標題就是尋址。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

工作區的鐵律：極少、always-on、任何時刻都適用的規矩，常駐工作區根的 `AGENTS.md`；其餘一切按需取用（為什麼這麼少、為什麼常駐，見 `wf/layers.md#/分層原則` 第 4 條，這裡不重講）。落地時把 `#/rules` 的條文寫進工作區 `AGENTS.md` 的鐵律段，`#/agents_md_entry` 寫進它的入口段。

# rules

- keep_meaning: 1. 重構／整理**不改原意**：開發＝行為不變且驗證綠燈（驗證指令是專案自己的：測試／build／lint，記在工作區的 `wf/knowledge/verification.json`；骨架是 `wf/skeletons/verification.md`）；非開發＝原意不變，照工作流節點的 `done_when` 驗收。
- authorization: 2. **不可逆或對外的動作**（push、刪除、對外送出、動 DB）要有**授權來源**：使用者當場確認，或他親自登記在清單裡（routines／schedule）。都沒有就先問。
- flow_in_nodes: 3. **具體流程**在各工作流節點（工作區的 `wf/workflows/`），不在頂層。

# adopt

鐵律 3–5 條，且必須「任何時刻都適用」才夠格；只在特定場景適用的規矩下放該工作流節點。要加、改、刪鐵律時照這條判斷；使用者個人的確認邊界（哪些直接做、哪些先問）不是鐵律，記在工作區的 `wf/knowledge/user.json`（流程 `wf/workflows/user.md`）。

# agents_md_entry

工作區 `AGENTS.md` 入口段要有的幾行（always-on，只指向下一層）：
- 每個 session 先掃兩軸：信，再數進度 `wf/progress.json` 的條目，非 0 才打開讀（指令與寫法見 `wf/knowledge/live-lists.md#/session_start`）。
- 要動手做事 → 工作區的 `wf/workflows/_index.json` 依意圖派發，再讀該工作流節點（派發通則見 `wf/workflows/_description.md`）。
- 想看專案結構 → 工作區的 `wf/_index.json`。
- 使用者偏好與邊界 → 工作區的 `wf/knowledge/user.json`。
- 有程式碼的工作區另加一行：碰原始碼前先讀慣例與 code map（`wf/knowledge/dev-dispatch.md#/before_code`）；環境與指令 → 工作區的 `wf/knowledge/dev-env.json`（`wf/workflows/dev-env.md`）。
