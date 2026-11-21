# `knowledge/aos/tools/move.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/tools/move.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**`#/_description`**

# 工具 move

移動或重新命名一個檔案、資料夾或連結。印出 `{"from", "to"}`。

- `to` 是完整的新路徑，不是要移進去的資料夾：`{"from": "a.txt", "to": "old/a.txt"}`。上層資料夾會自動建立。
- `to` 不能已經存在，不然 `FileBad`，什麼都不會移動。要取代一個檔案：先 `trash` 舊的，再 move。
- 連結是移動它本身，不是它指向的東西。跨磁碟時先複製再刪除，跟 `mv` 一樣。

用它來重新命名、搬位置，以及復原 `trash`：trash 會印出東西去了哪（`"to": ".trash/20261111-111744/out/hello.txt"`）；把它移回來：

```json
{"from": ".trash/20261111-111744/out/hello.txt", "to": "out/hello.txt"}
```
印出 `{"from":".trash/20261111-111744/out/hello.txt","to":"out/hello.txt"}`。

要連原本的也留著，用 `copy`。

錯誤：`aos/tools/move.json#/errors`。

---

**`#/errors`**

# move：錯誤

- `FileMissing`：`from` 不在。
- `FileBad`：`to` 已經存在。換一個路徑，或先 `trash` 掉 `to` 那裡的東西。
- `PathBad`：`to` 在 `from` 裡面（資料夾不能移進它自己）。
- `MoveFailed`：系統拒絕了（權限、有東西擋著）。重試前先用 `stat` 看兩個路徑。見 `aos/errors/common.json#/files`。
- `WsMissing`：`aos/errors/common.json#/files`。錯的或不認得的鍵（`ArgumentsBad`）：`aos/errors/common.json#/input`。
