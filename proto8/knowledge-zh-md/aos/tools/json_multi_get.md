# `knowledge/aos/tools/json_multi_get.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/tools/json_multi_get.md`，跟到正本 commit `fe053b828`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/tools/json_multi_get.md#/…` 對的就是它。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

**`#/Tool json_multi_get`**

# 工具 json_multi_get

一次取好幾個地方：像對每個路徑各做一次 `json_get`，照給的順序。每個路徑一行：路徑、一個 TAB，然後是 `json_get` 會印的東西（值寫成一行 JSON，或 `[too big] ...` 那一行）。

```json
{"paths": ["cfg.json#/name", "cfg.json#/states/think/next", "cfg.json#/nope"]}
```
印出
```text
cfg.json#/name	"bob"
cfg.json#/states/think/next	"act"
cfg.json#/nope	[error] PointerMissing no such pointer: cfg.json#/nope (cfg.json has no nope)
json_multi_get: error: PlacesFailed 1 of 3 places failed (lines with [error] above); the others were done, nothing was undone
```

- 各個地方互相獨立：一個失敗不會擋住其他的。有任何一個失敗＝最後一行是 `PlacesFailed`、結束碼是 1；其他行仍然是好的。
- `max_bytes`、`full`：跟 json_get 一樣，每個地方各自套用。路徑可以在不同檔案裡。
- 只有一個地方：用 `json_get`。路徑：`aos/tools/json_get.md#/JSON tools: the path`。錯誤：`aos/tools/json_multi_set.md#/json_multi_get, json_multi_set: errors`。
