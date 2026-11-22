# `knowledge/aos/tools/jsonx_multi_set.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/tools/jsonx_multi_set.md`，跟到正本 commit `fe053b828`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/tools/jsonx_multi_set.md#/…` 對的就是它。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

**`#/Tool jsonx_multi_set`**

# 工具 jsonx_multi_set

像 `json_multi_set`，但每一項都照 `jsonx_set` 的方式做：給用了 `$ref`/`$env` 的 aos 設定檔用。一般資料用 `json_multi_set`。

- 每一項：`{"path": "FILE#/POINTER"}` 再加上下面剛好一個：`value`（任何 JSON）、`text`（一段 JSON 文字，會被解析）、`from`（要複製的 `FILE#/POINTER`）。給兩個、一個都沒有、或有任何其他鍵 = 那一項 `[error] ArgumentsBad`；其他項目照樣做。
- `resolve`、`follow`、`check`、`parents`：同 jsonx_set，一個設定套用到每一項（不放在項目裡面）。
- 照順序做，做過的不復原；每項一行（`ok ...` 或 `[error] CODE reason`）；有任何一項失敗 = 最後一行 `jsonx_multi_set: error: PlacesFailed ...`，結束碼 1。

```json
{"items": [{"path": "fsm.json#/states/think/n", "value": 2}, {"path": "fsm.json#/states/act/exec", "from": "lib.json#/exec"}], "follow": true}
```
印出
```text
fsm.json#/states/think/n	ok fsm.json#/states/think/n
fsm.json#/states/act/exec	ok fsm.json#/states/act/exec
```

選項：`aos/tools/jsonx_set.md`。錯誤：`aos/tools/json_multi_set.md#/json_multi_get, json_multi_set: errors`、`aos/tools/jsonx_set.md#/jsonx_get, jsonx_ls, jsonx_search, jsonx_set, jsonx_add, jsonx_del, jsonx_multi_get, jsonx_multi_set: errors`。
