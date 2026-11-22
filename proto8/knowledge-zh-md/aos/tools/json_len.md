# `knowledge/aos/tools/json_len.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/tools/json_len.md`，跟到正本 commit `fe053b828`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/tools/json_len.md#/…` 對的就是它。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

**`#/Tool json_len`**

# 工具 json_len

JSON 檔中一個位置的長度，一個整數：物件 = 有幾個鍵，陣列 = 有幾項，字串 = 有幾個字元（不是位元組；`"小明ab"` 是 4）。

```json
{"path": "cfg.json#/tags"}
```
印出 `2`。

- 數字、布林或 null 沒有長度：`TargetBad`（`cfg.json#/max is a number; only objects, arrays and strings have a length`）。
- 鍵或項目也想要：`json_ls`（它的第一行是類型和長度）。

路徑：`aos/tools/json_get.md#/JSON tools: the path`。錯誤：`aos/tools/json_get.md#/json_get, json_ls, json_search: errors`，再加上 `TargetBad`。
