# `knowledge/wf/workflows/analysis.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/wf/workflows/analysis.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**`#/_description`**

陌生專案分析：初次接觸外部 repo、開源專案、舊系統或大型資料夾時，建立可延續、可搬移、可被後續 patch／planning 使用的分析產物。產物是記錄，放工作區的 `wf/knowledge/analysis/<project>/`（歸屬見 `wf/layers.json#/skills_vs_memory`；產物的形狀與寫法見 `wf/skeletons/analysis.json`）。

**`#/when`**：初次接觸陌生專案，需要建立可供後續工作延續的架構與能力分析；使用者說「這個陌生專案是怎麼運作的」「幫我分析這個 repo」。

---

**`#/not_when`**

只回答一個窄問題（「查清楚這是怎麼運作的」「這樣做可不可行」）→ `wf/workflows/investigation.json`；只是閱讀論文／規格／文章 → 本庫沒有對應的工作流，需要就自建；已在目標 repo 內實作功能 → `wf/workflows/feature-dev.json`。分辨：analysis＝初次接觸、要留下可延續的整套產物；investigation＝回答一個窄問題、留一篇筆記。

---

**`#/done_when`**（原文是字串陣列，3 行）

- 工作區的 `wf/knowledge/analysis/<project>/session_log.md` 與指定 Level 的分析檔存在。
- 主要入口、核心模組與測試方式的表格已填滿。
- 被分析專案的 README 指定的 build／run／test 指令回傳 0。

---

**`#/steps`**（原文是字串陣列，5 行）

1. 初始化工作區的 `wf/knowledge/analysis/<project>/` 與它底下的 `session_log.md`（還沒有就建；夾的結構照 `wf/skeletons/analysis.json#/fields`）。
2. Level 1 初始探索：README、頂層結構、依賴、入口點、build／run／test 指令。
3. Level 2 核心模組職責：主要模組、權責劃分、耦合點、資料流。
4. Level 3+ 依專案類型選模板深入（`#/level3_templates`）。
5. 將可行功能或缺口導向 `wf/workflows/planning.json`；將可套用修改導向 `wf/workflows/patch.json`。

---

**`#/level3_templates`**（陣列，7 項；每項是同一組鍵的小物件，排成表：第 i 列＝`#/level3_templates/i`）

| i | `type` | `focus` |
|---|---|---|
| 0 | 遊戲／引擎 | game loop、資源、渲染、AI、玩法、存檔 |
| 1 | 嵌入式／IoT | 控制迴圈、ISR、通訊、硬體抽象、即時性 |
| 2 | Web／API | 路由（routing）、middleware、domain／service、DB、驗證（auth）、佇列（queue） |
| 3 | 前端／桌面 | 路由（routes）、元件（components）、狀態（state）、API client、樣式（style）、建置（build） |
| 4 | CLI／SDK／函式庫（library） | 指令／API 介面（command／API surface）、設定（config）、I/O、外掛（plugin）、發布（release） |
| 5 | 資料／ML | 連接器（connector）、schema、管線（pipeline）、訓練（training）、服務上線（serving）、監控（monitoring） |
| 6 | DevOps／IaC | 模組（module）、環境（environment）、CI/CD、機密（secret）、可觀測性（observability） |

---

**`#/handoff`**（原文是字串陣列，2 行）

- 可行功能或缺口 → `wf/workflows/planning.json`；可獨立套用的修改 → `wf/workflows/patch.json`。
- 窄問題 → `wf/workflows/investigation.json`；需使用者驗證 → 工作區的 `wf/progress.json` 一條、status 寫「等使用者」。
