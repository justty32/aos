# `knowledge/aos/tools/jsonx_multi_get.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/tools/jsonx_multi_get.md`，跟到正本 commit `fe053b828`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/tools/jsonx_multi_get.md#/…` 對的就是它。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

**`#/Tool jsonx_multi_get`**

# 工具 jsonx_multi_get

跟 `json_multi_get` 一樣，但每個地方都像 `jsonx_get` 那樣讀：給用了 `$ref`/`$env` 的 aos 設定檔用。一般資料用 `json_multi_get`。

- `"follow": true`、`"resolve": true`、`max_bytes`、`full`：跟 jsonx_get 一樣，一個設定套用到每個地方。
- 每條路徑一行：路徑、一個 TAB，然後是值（或 `[too big] ...`，或 `[error] CODE reason`）；有任何一個失敗＝最後一行 `jsonx_multi_get: error: PlacesFailed ...`，結束碼 1。

```json
{"paths": ["fsm.json#/states/think/exec", "fsm.json#/states/act/next"], "follow": true}
```
印出
```text
fsm.json#/states/think/exec	["python3","x.py"]
fsm.json#/states/act/next	"think"
```

選項：`aos/tools/jsonx_get.md`。各行和 `PlacesFailed`：`aos/tools/json_multi_get.md`。錯誤：`aos/tools/json_multi_set.md#/json_multi_get, json_multi_set: errors`、`aos/tools/jsonx_set.md#/jsonx_get, jsonx_ls, jsonx_search, jsonx_set, jsonx_add, jsonx_del, jsonx_multi_get, jsonx_multi_set: errors`。
