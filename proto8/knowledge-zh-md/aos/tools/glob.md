# `knowledge/aos/tools/glob.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/tools/glob.md`，跟到正本 commit `fe053b828`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/tools/glob.md#/…` 對的就是它。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

**`#/Tool glob`**

# 工具 glob

在一個資料夾底下照名字樣式找路徑：一行一個路徑，資料夾以 `/` 結尾。把路徑貼進 `read` 或 `ls`。

用在：在整棵樹的任何地方照名字找檔案。不要用在：搜尋檔案內容（`grep`）、單一資料夾連同類型（`ls`）、一個檔案的資訊（`stat`）。

樣式：`*` 在一層之內，`?` 一個字元，`[abc]`（`[!abc]`），`**` 任意層數（也可以是零層）。沒有 `/` 時，它在任何深度比對名字（`*.py` = 每個 .py 檔）；有 `/` 時，比對 `path` 底下的整條路徑（`src/*.py` 直接在 src 裡，`src/**/*.py` 在任何深度）。

參數：`pattern`（必填）；`path`（資料夾，預設 `.`）；`type`（`file` 預設、`dir`、`any`）；`sort`（`name` 預設、`mtime` 最新的在前）；`hidden`；`gitignore`；`offset`；`max_items`（預設 100，最多 500）。

```json
{"pattern": "src/**/*.py", "max_items": 1}
```
印出
```text
src/deep/util.py
... next_offset 1 (2 paths in all)
```

`... ` 開頭的行是附註。規則：`aos/tools/glob.md#/glob: what it looks at`。錯誤：`aos/tools/glob.md#/glob: errors`。

**`#/glob: what it looks at`**

# glob：它看哪些東西

- `"sort": "name"`：照路徑排，每一層照名字（`src/deep/util.py` 在 `src/main.py` 前面）。`"mtime"`：最新的在前。
- 以 `.` 開頭的名字，只有 `"hidden": true` 時，或樣式點名它們時（`.github/**`、`**/.env`）才會列。
- 在 git 工作樹裡，`.gitignore` 掉的路徑（`build/`、`node_modules/`）和 `.git` 會被略過；`"gitignore": false` 會留著它們。沒有 git = 一條警告，什麼都不略過。
- 指向資料夾的連結會列出（帶 `/`），但不進去看：不會繞圈。本身是連結的 `path` 會跟過去。壞掉的連結不列。其他種類（fifo、socket）只有 `"type": "any"` 時才列。
- `... next_offset N`：用 `"offset": N` 再呼叫一次。`... no matches`；`... no matches from offset N` = `offset` 超過最後一條路徑。`... skipped N unreadable`：它打不開的資料夾。
- 掃描預算：20 秒或 20000 個名字，然後 `... stopped after ...`；總數會說 `at least`。把 `path` 縮小。

**`#/glob: errors`**

# glob：錯誤

- `PatternBad`：壞掉的樣式，像是 `[` 沒有 `]`（`unclosed [ in '[a'`），或是以 `/` 開頭（把資料夾放進 `path`）。
- `FileMissing`：沒有這個資料夾。`ls` 上一層資料夾。
- `FileBad`：`path` 是檔案，不是資料夾。給它所在的資料夾，或 `stat` 這個檔案。
- `ReadFailed`：`path` 這個資料夾讀不了。更深處讀不了的資料夾只會被計數。
- `ArgumentsBad`：也包括 `type` 不是 file、dir 或 any；`sort` 不是 name 或 mtime；`max_items` 不在 1 到 500 之間；`offset` 是負的。
- `WsMissing`：`aos/errors/common.md#/Codes from file work`。鍵寫錯或不認得的鍵（`ArgumentsBad`）：`aos/errors/common.md#/Codes about what you gave`。
