# `knowledge/aos/tools/write.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/tools/write.md`，跟到正本 commit `fe053b828`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/tools/write.md#/…` 對的就是它。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

**`#/Tool write`**

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

錯誤：`aos/tools/write.md#/write: errors`。

**`#/write: errors`**

# write：錯誤

- `FileBad`：這條路徑是資料夾。
- `MkdirFailed`：有一層上層資料夾建不起來：有個檔案擋在那裡（`cfg.json` 是檔案時的 `cfg.json/x`），或沒有權限。用 `stat` 檢查路徑。
- `WriteFailed`：系統拒絕了這次寫入（權限、磁碟滿了）。舊檔案（如果有的話）不變。
- `ArgumentsBad`：也包括 `content` 沒給或不是字串。
- `WsMissing`：`aos/errors/common.md#/Codes from file work`。錯誤或不認得的鍵（`ArgumentsBad`）：`aos/errors/common.md#/Codes about what you gave`。
