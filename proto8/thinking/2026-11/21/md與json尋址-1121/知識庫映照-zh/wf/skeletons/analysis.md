# `knowledge/wf/skeletons/analysis.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/wf/skeletons/analysis.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

**`#/_description`**：陌生專案分析產物的記憶骨架：落點、資料夾結構、寫作規則。落在工作區的 `wf/knowledge/analysis/<project>/`（用到才建）；流程在 `wf/workflows/analysis.json`。

---

**`#/holds`**（原文是字串陣列，2 行）

- 放：一個被分析專案的整套產物——架構分析、教學、問答、深入剖析、操作日誌。
- 不放：一個窄問題的調查（工作區的 `wf/knowledge/notes/`，`wf/skeletons/notes.json`）；要動手的想法與計畫（planning 的記錄：工作區的 `wf/knowledge/ideas.json` 與 `wf/knowledge/specs/`，骨架 `wf/skeletons/ideas.json`）。

---

**`#/fields`**（物件，7 個鍵：`architecture/`、`tutorial/`、`answers/`、`details/`、`others/`、`session_log.md`、`html/`）

**`#/fields/architecture~1`**：Level 1–6 架構分析

**`#/fields/tutorial~1`**：「如何做到 X」的目標導向教學

**`#/fields/answers~1`**：一次性具體問答

**`#/fields/details~1`**：單點深入剖析

**`#/fields/others~1`**：雜項與反向連結

**`#/fields/session_log.md`**：一句話操作日誌，建議上限 50 行

**`#/fields/html~1`**：選用導覽層

**`#/fields_note`**：`fields` 的 key 是 `wf/knowledge/analysis/<project>/` 底下的路徑。

---

**`#/rules`**（原文是字串陣列，4 行）

- 技術結論附來源位置：`path:line`、函式名、URL、論文 id 或命令摘要。
- 教學文件要包含：前置知識、原始碼導航、實作步驟、驗證方式。
- 圖表用 Mermaid、表格、列點；不要用 ASCII 框線圖。
- 子夾用到才建；`session_log.md` 一開始就建。

**`#/skeleton`**（原文是字串陣列，1 行）：session_log.md

**`#/skeleton_note`**：`skeleton` 是初始化 `wf/knowledge/analysis/<project>/` 時要先建的檔。
