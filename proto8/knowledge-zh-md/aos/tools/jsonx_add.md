# `knowledge/aos/tools/jsonx_add.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/tools/jsonx_add.md`，跟到正本 commit `fe053b828`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/tools/jsonx_add.md#/…` 對的就是它。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

**`#/Tool jsonx_add`**

# 工具 jsonx_add

像 `json_add`（新增，絕不覆寫），用於 aos 設定檔，帶著 `jsonx_set` 的選項：值來自 `value`、`text`、`from` 三者中剛好一個；`resolve`、`follow`、`check`、`parents`。一般資料用 `json_add`。

```json
{"path": "fsm.json#/states/act/x", "text": "{\"a\": true}"}
```
印出 `ok fsm.json#/states/act/x`。已經存在＝`KeyExists`。

路徑：`aos/tools/json_get.md#/JSON tools: the path`。錯誤：`aos/tools/jsonx_set.md#/jsonx_get, jsonx_ls, jsonx_search, jsonx_set, jsonx_add, jsonx_del, jsonx_multi_get, jsonx_multi_set: errors`。
