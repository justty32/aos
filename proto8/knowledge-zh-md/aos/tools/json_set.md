# `knowledge/aos/tools/json_set.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/tools/json_set.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**`#/_description`**

# 工具 json_set

把 JSON 檔裡的一個位置設成 `value`：取代它，或在物件沒有這個鍵時加上去。`value` 可以是任何 JSON，照給的原樣存（字串就還是字串）。只重寫檔案的那一部分，用一次原子寫入。

```json
{"path": "cfg.json#/states/act/next", "value": "idle"}
```
印出 `ok cfg.json#/states/act/next`。

- `.../-` 接在陣列最後：`{"path": "cfg.json#/tags/-", "value": "c"}` 印出 `ok cfg.json#/tags/2`（新的那一項）。`.../0` 取代第 0 項。
- 只給 FILE 會取代整個檔，或建立它：`{"path": "new.json", "value": {}}`。
- 路上缺的層：`"parents": true` 會建立物件（像 mkdir -p）；否則 `PointerMissing`。
- `$ref`／`$env` 物件在這裡就是普通物件：在裡面設一個鍵，改的是那個物件，不是它指向的檔案（那是帶 `follow` 的 `jsonx_set`）。

只加、永不覆蓋：`json_add`。刪除：`json_del`。路徑：`aos/tools/json_get.json#/path`。錯誤：`aos/tools/json_set.json#/errors`。

---

**`#/errors`**

# json_set、json_add、json_del：錯誤

出錯時什麼都不寫。

- `PointerMissing`：路上某一層不存在（給 `"parents": true`；用 `/-` 時 `parents` 沒作用，陣列必須已經存在）；陣列索引超過結尾（寫 `/-` 來接在最後）；json_del 刪不存在的東西。
- `FileMissing`：沒有這個檔；只給 FILE 用 json_set 建立它，例如 value `{}`。
- `KeyExists`（json_add）：鍵或檔案已經在了。json_set 可以改它；`/-` 加到陣列。
- `TargetBad`：這個位置不能做那種改動：`/-` 接在不是陣列的東西後面；上層是普通值（字串或數字）；json_del 刪整個檔（用 `trash` 或 `remove`）。
- `ArgumentsBad`：`value` 沒給也是這個。`ValueBad`：這個值寫不成 JSON。
- `WriteFailed`：寫檔失敗（`aos/errors/common.json#/files`）。
- `PointerBad`、`FileBad`、`LaunchFailed`、`CommandFailed`、`WsMissing`：同 `aos/tools/json_get.json#/errors`。
