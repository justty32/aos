# `knowledge/aos/tools/jsonx_multi_set.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/tools/jsonx_multi_set.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**`#/_description`**

# 工具 jsonx_multi_set

像 `json_multi_set`，但每一項都照 `jsonx_set` 的方式做：給用了 `$ref`/`$env` 的 aos 設定檔用。一般資料用 `json_multi_set`。

- 每一項：`{"path": "FILE#/POINTER"}` 再加上下面剛好一個：`value`（任何 JSON）、`text`（一段 JSON 文字，會被解析）、`from`（要複製的 `FILE#/POINTER`）。給兩個、一個都沒有、或有任何其他鍵 = 那一項 `[error] ArgumentsBad`；其他項目照樣做。
- `resolve`、`follow`、`check`、`parents`：同 jsonx_set，一個設定套用到每一項（不放在項目裡面）。
- 照順序做，做過的不復原；每項一行（`ok ...` 或 `[error] CODE reason`）；有任何一項失敗 = 最後一行 `jsonx_multi_set: error: PlacesFailed ...`，結束碼 1。

```json
{"items": [{"path": "fsm.json#/states/think/n", "value": 2}, {"path": "fsm.json#/states/act/exec", "from": "lib.json#/exec"}], "follow": true}
```
印出
```text
fsm.json#/states/think/n	ok fsm.json#/states/think/n
fsm.json#/states/act/exec	ok fsm.json#/states/act/exec
```

選項：`aos/tools/jsonx_set.json`。錯誤：`aos/tools/json_multi_set.json#/errors`、`aos/tools/jsonx_set.json#/errors`。
