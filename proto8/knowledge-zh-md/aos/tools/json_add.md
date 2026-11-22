# `knowledge/aos/tools/json_add.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/tools/json_add.md`，跟到正本 commit `fe053b828`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/tools/json_add.md#/…` 對的就是它。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

**`#/Tool json_add`**

# 工具 json_add

在 JSON 檔裡加新東西；永遠不覆蓋。印出 `ok FILE#/POINTER`。

- 在物件裡：加上這個鍵。已經有了 = `KeyExists`（要改它用 json_set）。
- 在陣列裡：`.../2` 插在第 2 項前面（後面的項往後挪）；`.../-` 接在最後。
- 只給 FILE 會建立這個檔；檔案已存在 = `KeyExists`。
- `"parents": true` 會建立路上缺的物件。

```json
{"path": "cfg.json#/tags/0", "value": "first"}
```
印出 `ok cfg.json#/tags/0`；原本的第 0 項現在是第 1 項。
`max` 已經在時，`{"path": "cfg.json#/max", "value": 3}` 會失敗：`json_add: error: KeyExists cfg.json#/max already exists; use json_set to change it`。

`value` 照給的原樣存，跟 json_set 一樣。路徑：`aos/tools/json_get.md#/JSON tools: the path`。錯誤：`aos/tools/json_set.md#/json_set, json_add, json_del: errors`。
