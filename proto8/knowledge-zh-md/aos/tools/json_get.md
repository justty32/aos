# `knowledge/aos/tools/json_get.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/tools/json_get.md`，跟到正本 commit `fe053b828`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/tools/json_get.md#/…` 對的就是它。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

**`#/Tool json_get`**

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

路徑（`FILE#/POINTER`）：`aos/tools/json_get.md#/JSON tools: the path`。`.md` 檔：`aos/tools/json_get.md#/JSON tools: reading markdown`。錯誤：`aos/tools/json_get.md#/json_get, json_ls, json_search: errors`。

**`#/JSON tools: the path`**

# JSON 工具：路徑

每個 json_* 和 jsonx_* 工具都收 `path`：一個字串 `FILE#/POINTER`，例如 `cfg.json#/states/think/next`。

- 只有 FILE 就是整份文件（`FILE#` 後面什麼都沒有是錯誤 `SpecBad`）。`FILE#/` 是名字為空字串的最上層鍵（RFC 6901，跟 `$ref` 和 aos-json 一樣）。相對的 FILE 從你的工作區開始。
- `#` 之後的指標以 `/` 開頭：鍵用 `/` 接起來，陣列項目用編號（`/tags/0`，不能有前導零）。鍵裡面 `~1` = `/`、`~0` = `~`（json_ls 就是這樣印鍵的）。
- 以 `/-` 結尾（json_set、json_add）：陣列最後一項之後。
- 照給的原樣寫：引號不會被拿掉（`cfg.json#"/max"` 是 `PointerBad`）。

**`#/JSON tools: reading markdown`**

# JSON 工具：讀 markdown

會讀的 json 工具（json_get、json_ls、json_len、json_search、json_multi_get）也收 `.md` 檔。markdown 裡不會多加任何東西：路徑照著檔裡本來就有的結構走。它們從不寫 markdown：要改 `.md` 檔用 `edit` 或 `write`。

- 只有 `FILE.md` 就是整份文字。
- `FILE.md#/Heading` 是那個標題底下的段落：標題那一行、它的文字和它的子段落。取第一個是那段文字的標題，不管哪一層（`#`、`##` ...）；先找一字不差的，再找不分大小寫的。要指定是哪一個，就先給上層：`FILE.md#/Parent/Heading`。標題裡的 `/` 寫成 `~1`。
- `FILE.md#/Heading/_` 只是標題自己的文字：沒有標題那一行，也沒有子段落。`FILE.md#/_` 是第一個標題之前的文字。
- `FILE.md#/Heading/0` 是標題自己的文字裡第一個清單的第 0 項（從 0 算起）；`/0/1` 進到那一項的子清單。寫成 `key: value` 的項目也可以用鍵取：`FILE.md#/Heading/key` 給出那個值。
- 那裡沒有清單、但有表格：`FILE.md#/Heading/2/0` 是第 2 列、第 0 欄。標題列是第 0 列；每一格都是字串，空格子是 `""`。同一段文字裡有清單也有表格時，數字指的是清單。
- 一個標題底下除了一個圍起來的 `json` 區塊什麼都沒有時，它就是那個 JSON 值：`FILE.md#/Heading/key/0` 繼續往裡面走。
- 在同一個位置，順序是：`_`，再來是標題，再來是數字，再來是清單的鍵。
- 對 `FILE.md` 或 `FILE.md#/Heading` 用 `json_ls`，會列出它底下有什麼：`_`（有自己的文字時）、子標題，然後是清單項目（鍵，或編號）或表格列。
- 那裡沒東西 = `PointerMissing`；原因會列出那裡有的名字。標題改了名，舊路徑就不能用了：用 `json_ls` 看。

**`#/json_get, json_ls, json_search: errors`**

# json_get、json_ls、json_search：錯誤

- `PointerBad`：`#` 前面沒東西，或 `#` 後面的指標不是以 `/` 開頭。
- `PointerMissing`：沒有這個鍵或陣列項目；原因會指出缺它的那一層（`cfg.json has no zzz`）。用 `json_ls` 看上一層。路上遇到的 `$ref`/`$env` 物件不會穿過去；原因會這樣說（用 `jsonx_get` 加 `follow`）。
- `FileMissing`：沒有這個檔案。`FileBad`：是資料夾、讀不了，或不是有效的 JSON。
- `ArgumentsBad`：還包括 `max_bytes`、`limit` 或 `depth` 不是正整數、`key` 不是字串、`offset` 是負的、json_search 既沒給 `key` 也沒給 `value`。
- `LaunchFailed`：輔助程式 `aos-json` 起不來（安裝設定問題：回報它）。`CommandFailed`：`aos-json` 失敗了但沒有原因行。
- `WsMissing`：`aos/errors/common.md#/Codes from file work`。錯的或不認得的鍵（`ArgumentsBad`）：`aos/errors/common.md#/Codes about what you gave`。
