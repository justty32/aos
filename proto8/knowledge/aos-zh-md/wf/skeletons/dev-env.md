# `knowledge/wf/skeletons/dev-env.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/wf/skeletons/dev-env.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

**`#/_description`**：開發環境的記憶骨架：fresh clone 後的步驟、冒煙指令、指令表、跨機／離線差異、外部工具與 env var。落在工作區的 `wf/knowledge/dev-env.json`；流程在 `wf/workflows/dev-env.json`。

---

**`#/holds`**（原文是字串陣列，2 行）

- 放：這個專案在這些機器上怎麼裝、怎麼跑、要哪些外部工具與環境變數。
- 不放：驗證與測試指令（連同「誰跑」在工作區的 `wf/knowledge/verification.json`）；寫碼慣例（工作區的 `wf/knowledge/conventions.json`）；金鑰的值（金鑰不進 repo，這裡只寫放哪）。

---

**`#/fields`**（物件，5 個鍵：`fresh_clone`、`smoke`、`commands`、`machines`、`tools`）

**`#/fields/fresh_clone`**：字串陣列，一步一個元素。通常四步：取得完整原始碼（例 `git submodule update --init`）→ 安裝依賴（例 `npm ci`）→ 設定 env var（例 複製 `.env.example` → `.env`，填 `tools` 表的值）→ 跑一次冒煙指令確認裝好了。

**`#/fields/smoke`**：冒煙指令（例 `npm run build`），回傳 0 表示環境裝好了。

**`#/fields/commands`**：指令表，物件陣列：`task`（做什麼）、`command`（指令）、`note`（備註）。建議起手四列：安裝依賴（備註寫何時要重跑）、build、跑起來（備註寫 port／進入點）、lint／format。

**`#/fields/machines`**：跨機／離線差異，物件陣列：`env`（環境，例 主力機、離線機、CI、容器）、`can_run`（能跑什麼，全部或可跑的子集）、`cannot_then`（跑不了的 → 改跑什麼；真的跑不了就記工作區的 `wf/progress.json` 一條、status 寫「等使用者」）。

**`#/fields/tools`**：外部工具與 env var，物件陣列：`name`（工具名或環境變數名）、`purpose`（用途）、`how`（工具：安裝方式與版本要求；env var：放哪、預設值）。

---

**`#/rules`**（原文是字串陣列，5 行）

- 三張表不留空欄；沒有就寫「無」。
- 只有單一開發環境、沒有離線／CI 差異 → `machines` 留空陣列；這時工作區 `wf/knowledge/verification.json` 的「誰跑」欄全部是 agent，並清掉工作區 `wf/progress.json` 裡因環境而卡的「等使用者」條目。
- 驗證與測試指令不列這裡。
- 要帳號、付費、授權才能取得的工具：`how` 寫清楚，並在工作區的 `wf/progress.json` 記一條、status 寫「等使用者」。
- 記錄是物件陣列，用 json 工具讀寫（`aos/packs.json#/json`）。

---

**`#/skeleton`**（物件，5 個鍵：`fresh_clone`、`smoke`、`commands`、`machines`、`tools`）

**`#/skeleton/fresh_clone`**：`[]`（空陣列）

**`#/skeleton/smoke`**：（空字串）

**`#/skeleton/commands`**：`[]`（空陣列）

**`#/skeleton/machines`**：`[]`（空陣列）

**`#/skeleton/tools`**：`[]`（空陣列）
