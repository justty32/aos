# `knowledge/aos/tools/remove.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/tools/remove.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**`#/_description`**

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
- `WsMissing`：`aos/errors/common.json#/files`。鍵錯了或不認得（`ArgumentsBad`）：`aos/errors/common.json#/input`。
