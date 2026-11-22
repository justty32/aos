# `knowledge/aos/tools/json_multi_set.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/tools/json_multi_set.md`，跟到正本 commit `fe053b828`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/tools/json_multi_set.md#/…` 對的就是它。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

**`#/Tool json_multi_set`**

# 工具 json_multi_set

一次設定好幾個地方：每個項目就像一次 `json_set`，照給的順序做。每個項目是 `{"path": "FILE#/POINTER", "value": any JSON}`；值完全照給的存，`.../-` 是附加到尾端。每個項目一行：路徑、一個 TAB，然後是 `ok ...` 或 `[error] CODE reason`。

```json
{"items": [{"path": "cfg.json#/max", "value": 30}, {"path": "cfg.json#/tags/-", "value": "c"}]}
```
印出
```text
cfg.json#/max	ok cfg.json#/max
cfg.json#/tags/-	ok cfg.json#/tags/2
```

- 項目一個一個做，不會復原任何東西：如果項目 2 失敗，項目 1 仍然寫了，項目 3 照樣會做。有任何失敗 = 最後一行 `json_multi_set: error: PlacesFailed N of M ...`，結束碼 1；只修 `[error]` 那幾行，再把它們送一次。
- 後面的項目看得到前面的寫了什麼（同一個檔也沒問題）。
- `"parents": true` 套用到每個項目（不包括 `/-` 項目：那個陣列必須存在）。只有一個地方：用 `json_set`。路徑：`aos/tools/json_get.md#/JSON tools: the path`。

**`#/json_multi_get, json_multi_set: errors`**

# json_multi_get、json_multi_set：錯誤

- 一行 `[error] CODE reason`：那個地方失敗了，代號就是 json_get 或 json_set 會給的（`aos/tools/json_get.md#/json_get, json_ls, json_search: errors`、`aos/tools/json_set.md#/json_set, json_add, json_del: errors`）；其他地方不受影響。
- `PlacesFailed`（最後一行，結束碼 1）：有幾個地方失敗。其餘的都做了；什麼都不會復原。只把失敗的再送一次。
- `ArgumentsBad`（唯一的一行）：`paths`／`items` 不是非空的陣列；什麼都沒做。不是物件的項目也是 `ArgumentsBad`，作為唯一的一行。項目裡面的問題（沒有 `path`、不認得的鍵、沒有 `value`）：那個項目的 `[error]` 行。
