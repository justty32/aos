# `knowledge/aos/tools/jsonx_search.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/tools/jsonx_search.md`，跟到正本 commit `fe053b828`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/tools/jsonx_search.md#/…` 對的就是它。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

**`#/Tool jsonx_search`**

# 工具 jsonx_search

像 `json_search`，給用了 `$ref`/`$env` 的 aos 設定檔用。一般資料用 `json_search`。

- `"follow": true`：在往 `path` 的路上穿過 `$ref` 物件，然後在它底下照寫的原樣搜尋。
- `"resolve": true`：在 `$ref`/`$env` 解開後的值裡搜尋（`$ref` 指向的檔案裡的命中也找得到）。
- 命中是你給的那個檔案裡的路徑；用 `jsonx_get` 加 `"follow": true` 讀它。
- `"up": true` 不能跟 `follow` 或 `resolve` 一起用（`ArgumentsBad`）：`$ref` 上面的那幾層在另一個檔案裡。`key`、`value`、`contains`、`limit`：跟 json_search 一樣。

路徑：`aos/tools/json_get.md#/JSON tools: the path`。錯誤：`aos/tools/jsonx_set.md#/jsonx_get, jsonx_ls, jsonx_search, jsonx_set, jsonx_add, jsonx_del, jsonx_multi_get, jsonx_multi_set: errors`。
