# repo 規矩六處：改前改後（第 25 句「2.好」；都是原字不動、加一句）

← [18-第五段](18-第五段-aos五頁與repo規矩.md)

**`AGENTS.md`**

- 改前：用 `wf/tools/tabledb.py` 讀寫、不整份讀進 context；給人點的導航連結表留 md。
- 改後：原句不動，後面加上：**新寫的文件預設寫 `.md`、用 index json（`_index.json`）當骨架；具體要用 `.md` 還是 `.json` 都可以，這條的門檻是建議、不做檢查**（使用者 11-21 晚「以後我覺得可以是新寫的就預設寫.md，然後再去用index json做骨架，當然，具體要用.md還是.json都可以」）。

**`wf/workflows/common/rules-card.md`**

- 改前：用 `wf/tools/tabledb.py` 讀寫、不整份讀進 context。
- 改後：原句不動，後面加上：新寫的預設寫 `.md`、用 index json 當骨架；要用 `.md` 還是 `.json` 都可以，門檻是建議、不做檢查（使用者 11-21）。

**`wf/workflows/common/data-files.md`**

- 改前：本檔是格式與工具的唯一契約，工具實作照這裡做。
- 改後：原句不動，後面加上：**11-21 起：新寫的預設寫 `.md`、用 index json 當骨架；具體要用 `.md` 還是 `.json` 都可以**（使用者 11-21 晚「以後我覺得可以是新寫的就預設寫.md，然後再去用index json做骨架，當然，具體要用.md還是.json都可以」）。所以上面的「> 1 KB 抽成資料檔」與下面的門檻是**建議、不是規定，不做檢查**：`find_big_lists.py` 只是把超過門檻的列出來給人參考，沒有任何交件關卡會因為它擋下來。決定抽成資料檔時，格式與工具照本檔；已經是資料檔的不用轉回 md。

**`wf/STRUCTURE/04-archive與資料檔.md`**

- 改前：抽成 `.json`／`.csv` 的門檻與格式契約 `wf-table/1` 在 [workflows/common/data-files.md](../workflows/common/data-files.md)；
- 改後：原句不動，改成：新寫的預設寫 `.md`、用 index json 當骨架，要用 `.md` 還是 `.json` 都可以（使用者 11-21；門檻是建議、不做檢查）。抽成 `.json`／`.csv` 的門檻與格式契約 `wf-table/1` 在 [workflows/common/data-files.md](../workflows/common/data-files.md)；

**`wf/STRUCTURE/02-結構整理原則.md`**

- 改前：4. **條列式區塊 > 1024 bytes**（表格／清單，每列同一組欄位）→ 抽成資料檔，不管整檔多大。
- 改後：原句不動，改成：4. **條列式區塊 > 1024 bytes**（表格／清單，每列同一組欄位）→ 抽成資料檔，不管整檔多大（11-21 起這一項是建議、不做檢查：新寫的預設寫 `.md`，要用 `.md` 還是 `.json` 都可以，見 [data-files](../workflows/common/data-files.md)）。

**`proto8/docs/NORMS/00-規範-3-指示詞-組合子-kernel.md`**

- 改前：`$ref` 換成那份 JSON 檔、接著解，
- 改後：原句不動，改成：`$ref` 換成那份 JSON 檔、接著解（11-21 起也可以指到 `.md` 檔：`x.md`＝整份文字，`x.md#/標題` 照 md 現有的標題、清單、表格、只有 json 區塊的節去尋，拿到的值不再往下解；使用者 11-21「用$ref可以」，規則 [thinking 11-21](../../thinking/2026-11/21/知識庫-骨架加md-規劃-1121/07-尋址規則.md)），
