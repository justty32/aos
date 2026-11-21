# `knowledge/wf/knowledge/workflow-template.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/wf/knowledge/workflow-template.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**`#/_description`**

新工作流節點的骨架：複製 `#/skeleton` 存成工作區的 `wf/workflows/<名稱>.json`，照 `#/fields` 逐鍵填；固定鍵順序不動，用不到的專屬段刪掉。改完在 `wf/workflows/_index.json` 加一條（description 含觸發說法）。形式規則在 `wf/nodes.json#/workflow_form`。

---

**`#/skeleton`**（物件，6 個鍵：`_description`、`when`、`not_when`、`done_when`、`steps`、`handoff`）

**`#/skeleton/_description`**：<一句話：這工作流做什麼、產出什麼>

**`#/skeleton/when`**：<觸發情境；index 那句「你說…」的展開>

**`#/skeleton/not_when`**：<像是但不該進來的情境 → 該去哪個工作流（統一路徑）>

**`#/skeleton/done_when`**（原文是字串陣列，1 行）：<可觀察的完成條件>

---

**`#/skeleton/steps`**（原文是字串陣列，2 行）

- <步驟>
- <步驟>

**`#/skeleton/handoff`**：完成後 → 接 <哪個工作流>；卡在使用者 → `wf/progress.json` 一條、status 寫「等使用者」，跨 session → `wf/progress.json` 一條，為什麼這樣選 → `wf/workflows/decisions.json`。

---

**`#/fields`**（物件，8 個鍵：`_description`、`when`、`not_when`、`done_when`、`steps`、`handoff`、`contents`、`<其他>`）

**`#/fields/_description`**：必填。一句話：這工作流做什麼、產出什麼。記錄或知識放在 `wf/knowledge/` 的，在這裡指過去。

**`#/fields/when`**：必填。觸發情境；把 `wf/workflows/_index.json` 那條的觸發說法（使用者會怎麼說）展開。

**`#/fields/not_when`**：必填。像是但不該進來的情境 → 該去哪個工作流，寫統一路徑（例 `wf/workflows/refactor.json`）。

**`#/fields/done_when`**：必填。一條一個可觀察條件，只准三類：檔案存在、指令回傳、表格填滿。✗「功能做好」「使用者滿意」；✓「`<驗證指令>` 回傳 0，且 `docs/<x>.md` 有『用法』段」。

**`#/fields/steps`**：必填。流程：一段 markdown 文字（字串或字串陣列，寫法見 knowledge 的 `docs/02`）。

**`#/fields/handoff`**：必填。交接：做完接哪個工作流；卡在使用者 → `wf/progress.json` 一條、status 寫「等使用者」；跨 session → `wf/progress.json` 一條；為什麼這樣選 → `wf/workflows/decisions.json`。

**`#/fields/contents`**：長出來才寫。資料夾型才有：子檔一覽（例 `archive/`：過時節點封存，規則見 `wf/tidying.json#/archive`）。

**`#/fields/<其他>`**：選填。該工作流專屬段落，自取英文鍵名（`[a-z0-9_-]`）。

**`#/paths`**：引用一律寫從 repo 根算的統一路徑，單節點或資料夾型寫法都一樣，不必像舊 md 那樣多一層 `../`。
