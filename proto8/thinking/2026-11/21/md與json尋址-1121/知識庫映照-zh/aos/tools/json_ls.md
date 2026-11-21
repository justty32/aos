# `knowledge/aos/tools/json_ls.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/tools/json_ls.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**`#/_description`**

# 工具 json_ls

列出 JSON 檔中一個位置裡面有什麼，像 `ls`。第一行：那個位置的類型和長度。接著每個鍵（或陣列索引）一行，可以直接接在路徑後面。

```json
{"path": "cfg.json"}
```
印出
```text
object, 5 keys
name
states
max
tags
note
```

`"long": true` 會加上 TYPE 和 SIZE，用 TAB 隔開（物件、陣列和字串還有它們寫成一行 JSON 時的大小；數字、布林和 null 顯示值）：
```text
object, 5 keys
name	string	4 chars	6 bytes
states	object	2 keys	47 bytes
max	number	20
```
陣列的開頭是 `array, 2 items (index 0..1)`，接著 `0`、`1`。單純的值是一行，例如 `number 20`。

`"depth": 2`（預設 1）也會列出下一層，每行是相對於 `path` 的路徑（`states`、`states/think`、`states/act`、...），照檔案裡的順序；`offset` 和 `limit` 算的是這些行。

分頁：`limit`（預設 200，或環境變數 `AOS_JSON_MAX_ITEMS`）和 `offset`。還有剩 = 最後一行 `[more] 0 to 1 of 5 shown; next: "offset": 2`。

路徑：`aos/tools/json_get.json#/path`。錯誤：`aos/tools/json_get.json#/errors`。
