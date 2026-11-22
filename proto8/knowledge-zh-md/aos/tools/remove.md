# `knowledge/aos/tools/remove.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/tools/remove.md`，跟到正本 commit `fe053b828`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/tools/remove.md#/…` 對的就是它。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

**`#/Tool remove`**

# 工具 remove

真的刪掉一個檔案、連結或資料夾，像 `rm`。沒有復原。

- 資料夾需要 `"recursive": true`（像 `rm -r`）。沒給：`FileBad`，什麼都不刪。
- 連結刪的是它本身；它指向的東西留著。
- 印出 `{"path", "type"}`，資料夾還有 `counter_files`（裡面刪掉的每個檔案）。

除非你確定，否則用 `trash`（trash 可以復原）。remove 用在你做出來、不再需要的東西，以及清空垃圾桶。

```json
{"path": ".trash", "recursive": true}
```
印出 `{"path":".trash","type":"dir","counter_files":4}`。

錯誤：

- `FileMissing`：那個路徑上什麼都沒有。
- `FileBad`：資料夾卻沒給 `"recursive": true`。加上它之前，先用 `ls` 看看裡面有什麼。
- `PathBad`：`.`、`..` 或 `/` 會被拒絕。
- `RemoveFailed`：系統拒絕了（例如沒有權限）。在資料夾裡，可能有一部分已經不見了：`ls` 它。
- `WsMissing`：`aos/errors/common.md#/Codes from file work`。鍵錯了或不認得（`ArgumentsBad`）：`aos/errors/common.md#/Codes about what you gave`。
