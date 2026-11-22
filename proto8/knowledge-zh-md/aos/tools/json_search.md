# `knowledge/aos/tools/json_search.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/tools/json_search.md`，跟到正本 commit `fe053b828`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/tools/json_search.md#/…` 對的就是它。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

**`#/Tool json_search`**

# 工具 json_search

在 JSON 檔裡找鍵和／或值，範圍是 `path` 底下的所有地方，照檔案順序。每個命中一行：`FILE#/POINTER<TAB>TYPE<TAB>SIZE`；沒有 = `[no match]`。把命中的那行貼進 `json_get` 或 `json_set` 當 `path`。

- `key`：完全相同的鍵名。`value`：型別相同、完全相同的 JSON 值（`1` 不是 `"1"`）。兩個都給：那個鍵而且是那個值。
- `"contains": true`：鍵、以及字串的 `value`，用子字串比對（分大小寫）。不支援正規表示式。
- `"up": true`：不往下找，改成找 `path` 上面每一層的鍵，從最近的一層開始（我周圍最近的 `max` 在哪？）。
- `limit`（預設 200，或環境變數 `AOS_JSON_MAX_ITEMS`）；命中更多 = 最後一行 `[more] ...`：把 `path` 縮小，或調高 `limit`。

```json
{"path": "cfg.json", "key": "next"}
```
印出
```text
cfg.json#/states/think/next	string	3 chars	5 bytes
cfg.json#/states/act/next	string	5 chars	7 bytes
```

路徑：`aos/tools/json_get.md#/JSON tools: the path`。錯誤：`aos/tools/json_get.md#/json_get, json_ls, json_search: errors`。
