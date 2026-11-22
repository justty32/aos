# `knowledge/aos/tools/jsonx_get.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/tools/jsonx_get.md`，跟到正本 commit `fe053b828`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/tools/jsonx_get.md#/…` 對的就是它。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

**`#/Tool jsonx_get`**

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

路徑：`aos/tools/json_get.md#/JSON tools: the path`。錯誤：`aos/tools/jsonx_set.md#/jsonx_get, jsonx_ls, jsonx_search, jsonx_set, jsonx_add, jsonx_del, jsonx_multi_get, jsonx_multi_set: errors`。
