# `knowledge/aos/tools/mkdir.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/tools/mkdir.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**`#/_description`**

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
- `WsMissing`：`aos/errors/common.json#/files`。鍵錯了或不認得（`ArgumentsBad`）：`aos/errors/common.json#/input`。
