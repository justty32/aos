# `knowledge/aos/tools/jsonx_search.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/tools/jsonx_search.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**`#/_description`**

# 工具 jsonx_search

像 `json_search`，給用了 `$ref`/`$env` 的 aos 設定檔用。一般資料用 `json_search`。

- `"follow": true`：在往 `path` 的路上穿過 `$ref` 物件，然後在它底下照寫的原樣搜尋。
- `"resolve": true`：在 `$ref`/`$env` 解開後的值裡搜尋（`$ref` 指向的檔案裡的命中也找得到）。
- 命中是你給的那個檔案裡的路徑；用 `jsonx_get` 加 `"follow": true` 讀它。
- `"up": true` 不能跟 `follow` 或 `resolve` 一起用（`ArgumentsBad`）：`$ref` 上面的那幾層在另一個檔案裡。`key`、`value`、`contains`、`limit`：跟 json_search 一樣。

路徑：`aos/tools/json_get.json#/path`。錯誤：`aos/tools/jsonx_set.json#/errors`。
