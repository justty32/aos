# `knowledge/aos/tools/json_ls.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/tools/json_ls.md`，跟到正本 commit `fe053b828`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/tools/json_ls.md#/…` 對的就是它。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

**`#/Tool json_ls`**

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

路徑：`aos/tools/json_get.md#/JSON tools: the path`。用在 `.md` 檔上時，它會列出標題（以及清單項或表格列）：`aos/tools/json_get.md#/JSON tools: reading markdown`。錯誤：`aos/tools/json_get.md#/json_get, json_ls, json_search: errors`。
