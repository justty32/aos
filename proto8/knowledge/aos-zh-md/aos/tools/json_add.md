# `knowledge/aos/tools/json_add.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/tools/json_add.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**`#/_description`**

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

`value` 照給的原樣存，跟 json_set 一樣。路徑：`aos/tools/json_get.json#/path`。錯誤：`aos/tools/json_set.json#/errors`。
