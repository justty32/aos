# `knowledge/aos/tools/jsonx_ls.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/tools/jsonx_ls.md`，跟到正本 commit `fe053b828`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/tools/jsonx_ls.md#/…` 對的就是它。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

**`#/Tool jsonx_ls`**

# 工具 jsonx_ls

像 `json_ls`，用在有 `$ref`/`$env` 的 aos 設定檔。一般資料用 `json_ls`。

- `"follow": true`：往那個位置走的路上會穿過 `$ref` 物件（剛好在那個位置上的 `$ref` 會照寫的樣子列出：一個鍵 `$ref`）。
- `"resolve": true`：列出把裡面 `$ref`/`$env` 解開後的值，跟 aos 讀到的一樣，例如 `{"path": "tools.json#/tools", "resolve": true}` 會列出套用 `$override` 之後的每個工具。
- `long`、`depth`、`offset`、`limit`：跟 json_ls 一樣。

路徑：`aos/tools/json_get.md#/JSON tools: the path`。錯誤：`aos/tools/jsonx_set.md#/jsonx_get, jsonx_ls, jsonx_search, jsonx_set, jsonx_add, jsonx_del, jsonx_multi_get, jsonx_multi_set: errors`。
