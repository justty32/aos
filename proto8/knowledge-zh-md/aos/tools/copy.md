# `knowledge/aos/tools/copy.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/tools/copy.md`，跟到正本 commit `fe053b828`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/tools/copy.md#/…` 對的就是它。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

**`#/Tool copy`**

# 工具 copy

把一個檔案或整個資料夾複製到新路徑。印出 `{"from", "to", "counter_files"}`。

- `to` 是完整的新路徑，不是要複製進去的資料夾：要把 `notes` 放進 `backup/`，給 `"to": "backup/notes"`。
- `to` 必須還不存在，否則 `FileBad`，什麼都不複製。`to` 的上層資料夾會自動建立。
- 連結照連結複製，不複製它指向的東西。時間和權限都保留。

用它在 `write` 之前留一份備份，或從一份複本開始做新東西。要改名或搬位置，用 `move`。

```json
{"from": "notes", "to": "backup/notes"}
```
印出 `{"from":"notes","to":"backup/notes","counter_files":3}`（`counter_files` 算裡面的每個檔案，子資料夾和隱藏檔也算）。

錯誤：`aos/tools/copy.md#/copy: errors`。

**`#/copy: errors`**

# copy：錯誤

- `FileMissing`：`from` 不在。
- `FileBad`：`to` 已經存在。換一個路徑；要取代它，先把舊的 `trash` 掉。
- `PathBad`：`to` 在 `from` 裡面（資料夾不能複製進自己裡面）。
- `CopyFailed`：系統拒絕（權限、磁碟滿了）；`to` 那裡不會留下任何東西。見 `aos/errors/common.md#/Codes from file work`。
- `WsMissing`：`aos/errors/common.md#/Codes from file work`。鍵錯了或不認得（`ArgumentsBad`）：`aos/errors/common.md#/Codes about what you gave`。
