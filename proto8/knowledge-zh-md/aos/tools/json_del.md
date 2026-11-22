# `knowledge/aos/tools/json_del.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/tools/json_del.md`，跟到正本 commit `fe053b828`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/tools/json_del.md#/…` 對的就是它。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

**`#/Tool json_del`**

# 工具 json_del

刪除一個鍵，或一個陣列項目（後面的項目往前移）。它必須存在。印出 `ok FILE#/POINTER`。

```json
{"path": "cfg.json#/note"}
```
印出 `ok cfg.json#/note`。

不能刪整個檔案（`TargetBad`：用 `trash` 或 `remove`）。`$ref`／`$env` 物件在這裡就是一般物件：刪它裡面的東西會改到那個物件。路徑：`aos/tools/json_get.md#/JSON tools: the path`。錯誤：`aos/tools/json_set.md#/json_set, json_add, json_del: errors`。
