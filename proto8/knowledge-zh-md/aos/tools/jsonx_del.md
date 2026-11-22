# `knowledge/aos/tools/jsonx_del.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/tools/jsonx_del.md`，跟到正本 commit `fe053b828`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/tools/jsonx_del.md#/…` 對的就是它。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

**`#/Tool jsonx_del`**

# 工具 jsonx_del

像 `json_del`，給用了 `$ref`/`$env` 的 aos 設定檔用。一般資料用 `json_del`。

- 沒有 `follow` 時，路上的 `$ref`/`$env` 物件受保護：`FollowMissing`，什麼都不刪。路徑正好停在一個指示詞（directive）上，就刪掉那個指令。
- `"follow": true`：穿過 `$ref`，刪它指向的那個檔案裡的東西（每個合併進來的部分裡對應的鍵也刪）。

```json
{"path": "fsm.json#/states/think/n", "follow": true}
```
印出 `ok fsm.json#/states/think/n`；這個鍵從 lib.json 消失了，也就是那個 `$ref` 指向的地方。

不能是整個檔案（`TargetBad`）。路徑：`aos/tools/json_get.md#/JSON tools: the path`。錯誤：`aos/tools/jsonx_set.md#/jsonx_get, jsonx_ls, jsonx_search, jsonx_set, jsonx_add, jsonx_del, jsonx_multi_get, jsonx_multi_set: errors`。
