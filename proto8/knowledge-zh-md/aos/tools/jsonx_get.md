# `knowledge/aos/tools/jsonx_get.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/tools/jsonx_get.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**`#/_description`**

# 工具 jsonx_get

跟 `json_get` 一樣，但用在有 `$ref`/`$env` 的 aos 設定檔（定義的 fsm.json、tools.json、llm.json）。一般的資料用 `json_get`。

- `"follow": true`：往值走的路上，穿過 `$ref` 物件。
- `"resolve": true`：值裡面的 `$ref`/`$env` 都解開後的樣子，就像 aos 讀到的那樣。
- `max_bytes`、`full`、`[too big]` 那行：跟 json_get 一樣。

fsm.json `{"states": {"think": {"$ref": "lib.json"}, "act": {"next": "think"}}}`，lib.json `{"exec": ["python3", "x.py"], "n": 1}`：
```json
{"path": "fsm.json#/states/think/exec", "follow": true}
```
印出 `["python3","x.py"]`（json_get 會說 `PointerMissing`：路上有一個指示詞（directive））。`{"path": "fsm.json#/states", "resolve": true}` 印出 `{"think":{"exec":["python3","x.py"],"n":1},"act":{"next":"think"}}`。

路徑：`aos/tools/json_get.json#/path`。錯誤：`aos/tools/jsonx_set.json#/errors`。
