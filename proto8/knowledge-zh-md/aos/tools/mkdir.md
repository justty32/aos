# `knowledge/aos/tools/mkdir.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/tools/mkdir.md`，跟到正本 commit `fe053b828`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/tools/mkdir.md#/…` 對的就是它。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

**`#/Tool mkdir`**

# 工具 mkdir

建立一個資料夾，連同缺少的上層資料夾。資料夾已經在也沒關係。印出 `{"path", "created"}`。

```json
{"path": "a/b/c"}
```
印出 `{"path":"a/b/c","created":true}`；同樣的呼叫再一次會印出 `{"path":"a/b/c","created":false}`。

你常常不需要它：`write`、`copy` 和 `move` 會自己建立上層資料夾。mkdir 用在要一個空資料夾，或在大量寫入前確認某個資料夾存在。

錯誤：

- `FileBad`：那個路徑上是一個檔案（`cfg.json is already a file`）。
- `MkdirFailed`：資料夾建不起來：路徑中間有一個檔案（`cfg.json/sub: Not a directory`），或沒有權限。用 `stat` 檢查路徑。
- `WsMissing`：`aos/errors/common.md#/Codes from file work`。鍵錯了或不認得（`ArgumentsBad`）：`aos/errors/common.md#/Codes about what you gave`。
