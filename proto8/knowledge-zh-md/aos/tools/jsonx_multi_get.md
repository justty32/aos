# `knowledge/aos/tools/jsonx_multi_get.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/tools/jsonx_multi_get.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**`#/_description`**

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

選項：`aos/tools/jsonx_get.json`。各行和 `PlacesFailed`：`aos/tools/json_multi_get.json`。錯誤：`aos/tools/json_multi_set.json#/errors`、`aos/tools/jsonx_set.json#/errors`。
