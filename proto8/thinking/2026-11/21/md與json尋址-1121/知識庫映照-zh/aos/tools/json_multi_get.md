# `knowledge/aos/tools/json_multi_get.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/tools/json_multi_get.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**`#/_description`**

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
- 只有一個地方：用 `json_get`。路徑：`aos/tools/json_get.json#/path`。錯誤：`aos/tools/json_multi_set.json#/errors`。
