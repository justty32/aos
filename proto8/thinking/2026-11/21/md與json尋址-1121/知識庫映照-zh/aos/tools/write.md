# `knowledge/aos/tools/write.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/tools/write.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**`#/_description`**

# 工具 write

寫一整個檔案：`content` 就變成整個檔案。不存在的檔案會被建立，連同它的上層資料夾。已存在的檔案會被整個取代（它的權限，例如 exec，會保留）。

用在新檔案，或你打算整個重寫一個檔案時。不適用於：只改檔案的一部分（`edit`；JSON 檔用 `json_set`）、複製檔案（`copy`）。write 不會先問：舊內容就沒了。如果你可能還需要它，先 `copy` 一份。

```json
{"path": "out/hello.txt", "content": "hello\nworld\n"}
```
印出 `Wrote out/hello.txt (12 bytes)`。

- 什麼都不會自動加：如果檔案應該以換行結尾，`content` 就要以 `\n` 結尾。
- 是連結的路徑，會寫到它指向的那個檔案。
- 檔案會先寫成旁邊的 `.NAME.tmp`，再改名，所以不會留下寫到一半的檔案。

錯誤：`aos/tools/write.json#/errors`。

---

**`#/errors`**

# write：錯誤

- `FileBad`：這條路徑是資料夾。
- `MkdirFailed`：有一層上層資料夾建不起來：有個檔案擋在那裡（`cfg.json` 是檔案時的 `cfg.json/x`），或沒有權限。用 `stat` 檢查路徑。
- `WriteFailed`：系統拒絕了這次寫入（權限、磁碟滿了）。舊檔案（如果有的話）不變。
- `ArgumentsBad`：也包括 `content` 沒給或不是字串。
- `WsMissing`：`aos/errors/common.json#/files`。錯誤或不認得的鍵（`ArgumentsBad`）：`aos/errors/common.json#/input`。
