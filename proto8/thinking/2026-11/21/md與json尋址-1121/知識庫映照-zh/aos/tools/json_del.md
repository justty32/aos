# `knowledge/aos/tools/json_del.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/tools/json_del.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**`#/_description`**

# 工具 json_del

刪除一個鍵，或一個陣列項目（後面的項目往前移）。它必須存在。印出 `ok FILE#/POINTER`。

```json
{"path": "cfg.json#/note"}
```
印出 `ok cfg.json#/note`。

不能刪整個檔案（`TargetBad`：用 `trash` 或 `remove`）。`$ref`／`$env` 物件在這裡就是一般物件：刪它裡面的東西會改到那個物件。路徑：`aos/tools/json_get.json#/path`。錯誤：`aos/tools/json_set.json#/errors`。
