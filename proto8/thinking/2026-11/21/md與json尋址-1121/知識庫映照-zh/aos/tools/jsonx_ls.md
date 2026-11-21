# `knowledge/aos/tools/jsonx_ls.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/tools/jsonx_ls.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**`#/_description`**

# 工具 jsonx_ls

像 `json_ls`，用在有 `$ref`/`$env` 的 aos 設定檔。一般資料用 `json_ls`。

- `"follow": true`：往那個位置走的路上會穿過 `$ref` 物件（剛好在那個位置上的 `$ref` 會照寫的樣子列出：一個鍵 `$ref`）。
- `"resolve": true`：列出把裡面 `$ref`/`$env` 解開後的值，跟 aos 讀到的一樣，例如 `{"path": "tools.json#/tools", "resolve": true}` 會列出套用 `$override` 之後的每個工具。
- `long`、`depth`、`offset`、`limit`：跟 json_ls 一樣。

路徑：`aos/tools/json_get.json#/path`。錯誤：`aos/tools/jsonx_set.json#/errors`。
