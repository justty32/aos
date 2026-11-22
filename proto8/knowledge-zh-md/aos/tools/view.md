# `knowledge/aos/tools/view.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/tools/view.md`，跟到正本 commit `fe053b828`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/tools/view.md#/…` 對的就是它。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

**`#/Tool view`**

# 工具 view

一步一步看進一個檔案。回覆是一個 JSON 物件。

- JSON 檔：看 `pointer` 那一層（空的 = 整個檔）。小的值（寫成 JSON 最多 1000 個字元）整個放在 `value`。超過 80 個字元的字串給 `counter_chars` 和 `head`（前 60 個字元）。大的物件或陣列給 `children`（每個的鍵和型別，加上大小：`counter_keys`、`counter_items`，長字串則是 `counter_chars` 和 `head`；短的普通值直接給 `value`；只給前 200 個，`counter_children_more` 說還有幾個）再加一個 `hint`：把某個子鍵接到 `pointer` 後面再呼叫一次。
- 文字檔：小的（最多 200 行且 8KB）整個放在 `text`。大的先給 `outline`（Python 的 class 和 def、Markdown 標題，附行號；其他檔案、或 outline 是空的：給前 40 行當 `head`；Python 語法錯誤會多一個 `syntax_error`）。然後用 `start` 和 `end` 要你需要的那幾行。

用它看你還不熟的檔案，或大檔案。要照順序讀文字用 `read`，要列出某個 JSON 位置的鍵用 `json_ls`，要拿一個值用 `json_get`，只要大小和型別用 `stat`。

附真實輸出的例子：`aos/tools/view.md#/view: examples`。錯誤：`aos/tools/view.md#/view: errors`。

**`#/view: examples`**

# view：例子

大的 Markdown 檔會給 outline：
```json
{"path": "doc.md"}
```
-> `{"path":"doc.md","format":"markdown","counter_lines":303,"outline":[{"line":1,"level":1,"name":"Title"},{"line":3,"level":2,"name":"Part"}],"hint":"use start/end (line numbers) to view the part you need"}`

接著要一段行：
```json
{"path": "doc.md", "start": 1, "end": 2}
```
-> `{"path":"doc.md","format":"text","counter_lines":303,"start":1,"end":2,"text":"# Title\ntext\n"}`

JSON 檔的一層：
```json
{"path": "cfg.json", "pointer": "/states"}
```
-> `{"path":"cfg.json","format":"json","pointer":"/states","type":"object","counter_keys":2,"value":{"think":{"next":"act"},"act":{"next":"think"}}}`

給了 `start` 或 `end`（從 1 起的整數），`pointer` 會被忽略，任何檔案（JSON 也是）都以行顯示。一段最多 2000 行或 50KB；被截斷時，`hint` 會說 `use start=N to continue`。

**`#/view: errors`**

# view：錯誤

- `FileMissing`：沒有這個檔。`FileBad`：是資料夾（用 `ls`）、二進位檔，或對不是 JSON 的檔案給了 `pointer`（用 `start` 和 `end`）。
- `PointerMissing`：那個鍵不在；原因裡會寫出它的名字。往上一層，看 `children`。
- `ArgumentsBad`：`pointer` 不是以 `/` 開頭，或 `start` 超過檔案結尾，也是這個。
- `ReadFailed`、`WsMissing`：`aos/errors/common.md#/Codes from file work`。鍵錯了或不認得（`ArgumentsBad`）：`aos/errors/common.md#/Codes about what you gave`。
