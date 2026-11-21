# `knowledge/wf/skeletons/user.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/wf/skeletons/user.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

**`#/_description`**：使用者偏好與確認邊界的骨架：agent 不用重猜的事。落點是工作區的 `wf/knowledge/user.json`；何時記、怎麼記在 `wf/workflows/user.json`。

---

**`#/holds`**（原文是字串陣列，2 行）

- 放：這位使用者的長期偏好——語言、分支慣例、哪些事直接做不用問、哪些一定先問、回覆風格、時區。
- 不放：always-on 鐵律（在工作區的 `AGENTS.md`，條文見 `wf/knowledge/iron-rules.json#/rules`）；一次性的當下指示。

---

**`#/fields`**（物件，2 個鍵：`item`、`setting`）

**`#/fields/item`**：項目名

**`#/fields/setting`**：設定：這位使用者的說法；有原話就附日期與原文。

---

**`#/items`**（陣列，6 項；每項是同一組鍵的小物件，排成表：第 i 列＝`#/items/i`）

| i | `item` | `meaning` | `examples` |
|---|---|---|---|
| 0 | 語言 | 回覆與文件用什麼語言；程式註解用什麼語言。 | 繁中；程式註解英文 |
| 1 | 分支慣例 | commit 與分支怎麼走。 | 直接 commit main／開 branch 走 PR |
| 2 | 直接做、不用問 | agent 可以自己動手的事。 | 改文件、加測試、跑唯讀指令 |
| 3 | 一定先問 | 動手前一定要問的事；push 與對外動作另由鐵律管（`wf/knowledge/iron-rules.json#/rules/authorization`）。 | 刪檔、動 DB、安裝依賴 |
| 4 | 回覆風格 | 這位使用者對回覆風格的偏好。 | 不要每段都 bullet |
| 5 | 時區 | 使用者的時區。 | Asia/Taipei |

---

**`#/rules`**（原文是字串陣列，4 行）

- `prefs` 寫成物件陣列，用 json 工具讀寫；一項一筆，表外的長期偏好新增一筆。
- `items` 的 `examples` 只是常見寫法示範，不是事實；沒問過使用者就留空，不要照填。
- 改一項時，同檔裡跟新偏好矛盾的舊值一併改掉。
- `skeleton` 裡的路徑是工作區裡的路徑。

**`#/glossary`**：領域詞彙常猜錯、術語多了 → 開工作區的 `wf/knowledge/glossary.json`（用到才建）：物件陣列，每筆 `term`（詞）、`meaning`（意思）、`aliases`（別名）；建了在工作區的 `wf/knowledge/_index.json` 加一條。

---

**`#/skeleton`**（物件，2 個鍵：`_description`、`prefs`）

**`#/skeleton/_description`**：使用者偏好與確認邊界：agent 不用重猜的事。always-on 鐵律在 `AGENTS.md`，這裡是這位使用者的偏好——改了改這裡，不改鐵律。怎麼記見 `wf/workflows/user.json`。

---

**`#/skeleton/prefs`**（陣列，6 項；每項是同一組鍵的小物件，排成表：第 i 列＝`#/skeleton/prefs/i`）

| i | `item` | `setting` |
|---|---|---|
| 0 | 語言 |  |
| 1 | 分支慣例 |  |
| 2 | 直接做、不用問 |  |
| 3 | 一定先問 |  |
| 4 | 回覆風格 |  |
| 5 | 時區 |  |
