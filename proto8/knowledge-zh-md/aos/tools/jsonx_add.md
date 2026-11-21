# `knowledge/aos/tools/jsonx_add.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/tools/jsonx_add.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**`#/_description`**

# 工具 jsonx_add

像 `json_add`（新增，絕不覆寫），用於 aos 設定檔，帶著 `jsonx_set` 的選項：值來自 `value`、`text`、`from` 三者中剛好一個；`resolve`、`follow`、`check`、`parents`。一般資料用 `json_add`。

```json
{"path": "fsm.json#/states/act/x", "text": "{\"a\": true}"}
```
印出 `ok fsm.json#/states/act/x`。已經存在＝`KeyExists`。

路徑：`aos/tools/json_get.json#/path`。錯誤：`aos/tools/jsonx_set.json#/errors`。
