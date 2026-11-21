# `knowledge/aos/tools/json_len.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/tools/json_len.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**`#/_description`**

# 工具 json_len

JSON 檔中一個位置的長度，一個整數：物件 = 有幾個鍵，陣列 = 有幾項，字串 = 有幾個字元（不是位元組；`"小明ab"` 是 4）。

```json
{"path": "cfg.json#/tags"}
```
印出 `2`。

- 數字、布林或 null 沒有長度：`TargetBad`（`cfg.json#/max is a number; only objects, arrays and strings have a length`）。
- 鍵或項目也想要：`json_ls`（它的第一行是類型和長度）。

路徑：`aos/tools/json_get.json#/path`。錯誤：`aos/tools/json_get.json#/errors`，再加上 `TargetBad`。
