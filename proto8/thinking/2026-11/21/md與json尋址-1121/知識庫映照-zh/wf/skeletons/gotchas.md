# `knowledge/wf/skeletons/gotchas.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/wf/skeletons/gotchas.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

**`#/_description`**：踩坑記錄的骨架：撞過兩次以上的坑，每條寫現象與對策。落點是工作區的 `wf/knowledge/gotchas.json`；何時記、記哪段在 `wf/workflows/gotchas.json`。

---

**`#/holds`**（原文是字串陣列，3 行）

- 放：共通坑（不專屬任一工作流）；工作流專屬、還沒長出自己那份記錄的坑也可以先放成同檔的一段。
- 不放：只撞過一次的意外（門檻是第二次撞到）。
- 不放：已有自己踩坑記錄的工作流的坑——記在那份，這裡的 `routes` 只導流。

---

**`#/fields`**（物件，3 個鍵：`routes`、`common`、`<工作流名>`）

**`#/fields/routes`**：哪類坑記哪裡：物件陣列，每筆 `kind`（坑的性質）、`where`（記／查哪裡）。工作流的坑長成自己一份記錄時加一筆。

**`#/fields/common`**：共通坑：字串陣列，一條一個坑。

**`#/fields/<工作流名>`**：（選用）某工作流專屬的坑，形狀同 `common`。

---

**`#/rules`**（原文是字串陣列，4 行）

- 記錄門檻：第二次撞到、或使用者說「上次也是這樣」才記。
- 條目格式：一條一個坑，粗體標題＋一兩句現象與對策。例：`**存檔已固化**：設定值只是初值，既有存檔保留 runtime 值。`
- 用 json 工具讀寫。
- `skeleton` 裡的路徑是工作區裡的路徑。

---

**`#/skeleton`**（物件，3 個鍵：`_description`、`routes`、`common`）

**`#/skeleton/_description`**：踩坑記錄：共通坑記 `common`；工作流專屬的坑看 `routes` 導到哪。第二次撞到才記；一條一個坑，粗體標題＋一兩句現象與對策。怎麼記見 `wf/workflows/gotchas.json`。

---

**`#/skeleton/routes`**（陣列，1 項；每項是同一組鍵的小物件，排成表：第 i 列＝`#/skeleton/routes/i`）

| i | `kind` | `where` |
|---|---|---|
| 0 | 共通坑 | 本檔 `common` |

**`#/skeleton/common`**：`[]`（空陣列）
