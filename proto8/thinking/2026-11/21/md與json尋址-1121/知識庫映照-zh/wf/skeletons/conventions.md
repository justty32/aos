# `knowledge/wf/skeletons/conventions.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/wf/skeletons/conventions.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

**`#/_description`**：寫碼慣例的記憶骨架：碰原始碼的工作流（feature-dev、refactor、investigation）共用的規矩——寫碼時要遵守什麼、怎麼檢查。落在工作區的 `wf/knowledge/conventions.json`。

---

**`#/holds`**（原文是字串陣列，2 行）

- 放：這個專案的寫碼慣例，一條一列、附怎麼檢查。
- 不放：哪個檔負責什麼、測試在哪、真相層優先序（工作區的 `wf/knowledge/code-map.json`）；工作文檔的組織原則（本庫 `wf/` 頂層的 `layers.json`、`nodes.json`、`tidying.json`）；使用者個人偏好（工作區的 `wf/knowledge/user.json`）。

---

**`#/fields`**（物件，1 個鍵：`conventions`）

**`#/fields/conventions`**：物件陣列：`item`（項目）、`rule`（規矩）、`check`（怎麼檢查：指令、grep、或「目視」）。

---

**`#/suggested_items`**（陣列，6 項；每項是同一組鍵的小物件，排成表：第 i 列＝`#/suggested_items/i`）

| i | `item` | `example` |
|---|---|---|
| 0 | 檔案拆分 | 按領域拆 module；檔太大照 `wf/tidying.json#/split` 檢視 |
| 1 | 命名 | 檔名 kebab-case、型別 PascalCase |
| 2 | 註解語言 | 程式碼註解英文、文件繁中 |
| 3 | 破壞相容的變更（breaking change） | 改公開介面前先全域 grep 受影響處，同一 commit 一起改 |
| 4 | 型別／schema 同步 | 改 schema 要同步產生檔與測試 fixture |
| 5 | 相依 | 新增套件前先確認，版本鎖進 lockfile |

---

**`#/rules`**（原文是字串陣列，3 行）

- 一條一列，**寫得出「怎麼檢查」的才留**；寫不出檢查方式的（「程式碼要乾淨」）不是慣例，別放。
- `suggested_items` 只是常見項目與例子，照專案實況寫，用不到的不列。
- 記錄是物件陣列，用 json 工具讀寫（`aos/packs.json#/json`）。

---

**`#/skeleton`**（物件，1 個鍵：`conventions`）

**`#/skeleton/conventions`**：`[]`（空陣列）
