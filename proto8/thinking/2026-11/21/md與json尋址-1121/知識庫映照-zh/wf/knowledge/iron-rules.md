# `knowledge/wf/knowledge/iron-rules.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/wf/knowledge/iron-rules.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**`#/_description`**

工作區的鐵律：極少、always-on、任何時刻都適用的規矩，常駐工作區根的 `AGENTS.md`；其餘一切按需取用（為什麼這麼少、為什麼常駐，見 `wf/layers.json#/layers` 第 4 條，這裡不重講）。落地時把 `#/rules` 的條文寫進工作區 `AGENTS.md` 的鐵律段，`#/agents_md_entry` 寫進它的入口段。

---

**`#/rules`**（物件，3 個鍵：`keep_meaning`、`authorization`、`flow_in_nodes`）

---

**`#/rules/keep_meaning`**

1. 重構／整理**不改原意**：開發＝行為不變且驗證綠燈（驗證指令是專案自己的：測試／build／lint，記在工作區的 `wf/knowledge/verification.json`；骨架是 `wf/skeletons/verification.json`）；非開發＝原意不變，照工作流節點的 `done_when` 驗收。

**`#/rules/authorization`**：2. **不可逆或對外的動作**（push、刪除、對外送出、動 DB）要有**授權來源**：使用者當場確認，或他親自登記在清單裡（routines／schedule）。都沒有就先問。

**`#/rules/flow_in_nodes`**：3. **具體流程**在各工作流節點（工作區的 `wf/workflows/`），不在頂層。

**`#/adopt`**：鐵律 3–5 條，且必須「任何時刻都適用」才夠格；只在特定場景適用的規矩下放該工作流節點。要加、改、刪鐵律時照這條判斷；使用者個人的確認邊界（哪些直接做、哪些先問）不是鐵律，記在工作區的 `wf/knowledge/user.json`（流程 `wf/workflows/user.json`）。

---

**`#/agents_md_entry`**（原文是字串陣列，6 行）

工作區 `AGENTS.md` 入口段要有的幾行（always-on，只指向下一層）：
- 每個 session 先掃兩軸：信，再數進度 `wf/progress.json` 的條目，非 0 才打開讀（指令與寫法見 `wf/knowledge/live-lists.json#/session_start`）。
- 要動手做事 → 工作區的 `wf/workflows/_index.json` 依意圖派發，再讀該工作流節點（派發通則見 `wf/workflows/_description.json`）。
- 想看專案結構 → 工作區的 `wf/_index.json`。
- 使用者偏好與邊界 → 工作區的 `wf/knowledge/user.json`。
- 有程式碼的工作區另加一行：碰原始碼前先讀慣例與 code map（`wf/knowledge/dev-dispatch.json#/before_code`）；環境與指令 → 工作區的 `wf/knowledge/dev-env.json`（`wf/workflows/dev-env.json`）。
