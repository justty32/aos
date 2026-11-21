# `knowledge/aos/tools/trash.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/tools/trash.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**`#/_description`**

# 工具 trash

刪掉一個檔案、資料夾或連結，而且可以復原：它會被搬到你工作區裡的 `.trash/<time>/<its path>`。印出 `{"path", "to"}`；`to` 是它現在的位置。

刪東西時預設用 trash。只有真的必須消失時才用 `remove`（很大的暫存資料夾、清空垃圾桶）。

```json
{"path": "out/hello.txt"}
```
印出 `{"path":"out/hello.txt","to":".trash/20261111-111744/out/hello.txt"}`。

- 同一秒內再丟同一個路徑，會到 `.trash/<time>-1/<its path>`，再來 `-2`，依此類推；同一秒內不同的路徑共用 `.trash/<time>/`。
- 復原：用 `move`，`"from"`＝那個 `to`，`"to"`＝原來的路徑（`aos/tools/move.json`）。
- `<time>` 是本地時間 `YYYYMMDD-HHMMSS`。工作區外的路徑保留完整的絕對路徑：`/tmp/b1out/f.txt` 會到 `.trash/<time>/tmp/b1out/f.txt`。
- 垃圾桶永遠不會自己清空。要清空它：用 `remove`，`{"path": ".trash", "recursive": true}`（不能復原）。`ls` 會藏起 `.trash`，除非 `"hidden": true`。

錯誤：`aos/tools/trash.json#/errors`。

---

**`#/errors`**

# trash：錯誤

- `FileMissing`：那個路徑什麼都沒有。
- `PathBad`：工作區本身、已經在 `.trash` 裡的東西，或包含 `.trash` 的資料夾。
- `MoveFailed`：系統拒絕了搬移（`aos/errors/common.json#/files`）。
- `WsMissing`：垃圾桶一定在你的工作區裡，所以就算是絕對路徑，trash 也需要工作區。錯的或不認得的鍵（`ArgumentsBad`）：`aos/errors/common.json#/input`。
