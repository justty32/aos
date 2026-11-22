# `knowledge/aos/tools/jsonx_set.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/tools/jsonx_set.md`，跟到正本 commit `fe053b828`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/tools/jsonx_set.md#/…` 對的就是它。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

**`#/Tool jsonx_set`**

# 工具 jsonx_set

像 `json_set`，用於使用 `$ref`/`$env` 的 aos 設定檔。一般資料用 `json_set`。

- 值：剛好是 `value`（任何 JSON）、`text`（一段 JSON 文字，會解析）、`from`（要複製的 `FILE#/POINTER`）其中之一。
- `"resolve": true`：存之前先把值裡的 `$ref`/`$env` 解開（預設：照寫的樣子存）。
- `"follow": true`：路上碰到 `$ref` 就穿過去，改它指向的那個檔。沒有它的話，路上的指示詞（directive）是 `FollowMissing`；路徑剛好停在指令上時，會把它整個取代。
- `"check": true`：拒絕會讓設定多出問題的改動（`CheckFailed`，什麼都不寫）。
- `parents`、`.../-`：跟 json_set 一樣。`follow` 不套用在 `from` 裡的路徑：來源讀取時不穿過（`resolve` 有套用）。

```json
{"path": "fsm.json#/states/think/n", "value": 2, "follow": true}
```
印出 `ok fsm.json#/states/think/n`；改動在 lib.json 裡，也就是那個 `$ref` 指向的地方。`{"path": "fsm.json#/states/act/exec", "from": "lib.json#/exec"}` 複製一個值。

路徑：`aos/tools/json_get.md#/JSON tools: the path`。錯誤：`aos/tools/jsonx_set.md#/jsonx_get, jsonx_ls, jsonx_search, jsonx_set, jsonx_add, jsonx_del, jsonx_multi_get, jsonx_multi_set: errors`。

**`#/jsonx_get, jsonx_ls, jsonx_search, jsonx_set, jsonx_add, jsonx_del, jsonx_multi_get, jsonx_multi_set: errors`**

# jsonx_get、jsonx_ls、jsonx_search、jsonx_set、jsonx_add、jsonx_del、jsonx_multi_get、jsonx_multi_set：錯誤

`aos/tools/json_get.md#/json_get, json_ls, json_search: errors` 和 `aos/tools/json_set.md#/json_set, json_add, json_del: errors` 裡的代號都適用（`KeyExists` 只在 jsonx_add）。另外：

- `ArgumentsBad`：`value`、`text`、`from` 不是剛好一個（set、add；在 multi_set 的某一項裡，就是那一項的 `[error]` 行）；`up` 搭配 `follow` 或 `resolve`（search）。
- `TextBad`：`text` 不是 JSON；原因裡有解析錯誤。
- `FollowMissing`（只有 set、add、del；沒有 `follow` 時讀取會得到 `PointerMissing`）：路上有一個 `$ref`/`$env` 物件；給 `"follow": true`，或指向那個指令本身來取代它。
- `DirectiveBad`：`$ref` 讀不了、指向不存在的地方或繞成一圈；有 `resolve` 時，某個 `$env` 沒設。
- `CheckFailed`：有 `check` 時，這個改動會多出問題（原因會點出它們）；什麼都不寫。
- `TargetBad`：另外，有 `follow` 時，取代一個同時由好幾個檔案合併出來的值。`PointerMissing`：另外，路上有一個 `$env`（它沒辦法穿過）。
