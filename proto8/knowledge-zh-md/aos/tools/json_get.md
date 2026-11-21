# `knowledge/aos/tools/json_get.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/tools/json_get.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**`#/_description`**

# 工具 json_get

取得 JSON 檔裡某一個位置的值，印成一行精簡的 JSON。

用它讀一個值。不確定裡面有什麼：先 `json_ls`。找一個鍵或值：`json_search`。原始文字：`read`。

```json
{"path": "cfg.json#/states/think"}
```
印出 `{"next":"act"}`。

比 `max_bytes` 大時（預設 8000，或環境變數 `AOS_JSON_MAX_BYTES`）：改印一行
```text
[too big] object, 5 keys, 113 bytes (max_bytes 20). List it: json_ls cfg.json. Or get a deeper path, or give "full": true.
```
`"full": true` 不管多大都印。`$ref`/`$env` 物件照寫的原樣回來，不會穿過去（那是 `jsonx_get` 的事）。

路徑（`FILE#/POINTER`）：`aos/tools/json_get.json#/path`。錯誤：`aos/tools/json_get.json#/errors`。

---

**`#/path`**

# JSON 工具：路徑

每個 json_* 和 jsonx_* 工具都收 `path`：一個字串 `FILE#/POINTER`，例如 `cfg.json#/states/think/next`。

- 只有 FILE 就是整份文件（`FILE#` 後面什麼都沒有是錯誤 `SpecBad`）。`FILE#/` 是名字為空字串的最上層鍵（RFC 6901，跟 `$ref` 和 aos-json 一樣）。相對的 FILE 從你的工作區開始。
- `#` 之後的指標以 `/` 開頭：鍵用 `/` 接起來，陣列項目用編號（`/tags/0`，不能有前導零）。鍵裡面 `~1` = `/`、`~0` = `~`（json_ls 就是這樣印鍵的）。
- 以 `/-` 結尾（json_set、json_add）：陣列最後一項之後。
- 照給的原樣寫：引號不會被拿掉（`cfg.json#"/max"` 是 `PointerBad`）。

---

**`#/errors`**

# json_get、json_ls、json_search：錯誤

- `PointerBad`：`#` 前面沒東西，或 `#` 後面的指標不是以 `/` 開頭。
- `PointerMissing`：沒有這個鍵或陣列項目；原因會指出缺它的那一層（`cfg.json has no zzz`）。用 `json_ls` 看上一層。路上遇到的 `$ref`/`$env` 物件不會穿過去；原因會這樣說（用 `jsonx_get` 加 `follow`）。
- `FileMissing`：沒有這個檔案。`FileBad`：是資料夾、讀不了，或不是有效的 JSON。
- `ArgumentsBad`：還包括 `max_bytes`、`limit` 或 `depth` 不是正整數、`key` 不是字串、`offset` 是負的、json_search 既沒給 `key` 也沒給 `value`。
- `LaunchFailed`：輔助程式 `aos-json` 起不來（安裝設定問題：回報它）。`CommandFailed`：`aos-json` 失敗了但沒有原因行。
- `WsMissing`：`aos/errors/common.json#/files`。錯的或不認得的鍵（`ArgumentsBad`）：`aos/errors/common.json#/input`。
