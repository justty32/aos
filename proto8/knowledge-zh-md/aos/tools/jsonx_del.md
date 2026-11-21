# `knowledge/aos/tools/jsonx_del.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/tools/jsonx_del.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**`#/_description`**

# 工具 jsonx_del

像 `json_del`，給用了 `$ref`/`$env` 的 aos 設定檔用。一般資料用 `json_del`。

- 沒有 `follow` 時，路上的 `$ref`/`$env` 物件受保護：`FollowMissing`，什麼都不刪。路徑正好停在一個指示詞（directive）上，就刪掉那個指令。
- `"follow": true`：穿過 `$ref`，刪它指向的那個檔案裡的東西（每個合併進來的部分裡對應的鍵也刪）。

```json
{"path": "fsm.json#/states/think/n", "follow": true}
```
印出 `ok fsm.json#/states/think/n`；這個鍵從 lib.json 消失了，也就是那個 `$ref` 指向的地方。

不能是整個檔案（`TargetBad`）。路徑：`aos/tools/json_get.json#/path`。錯誤：`aos/tools/jsonx_set.json#/errors`。
