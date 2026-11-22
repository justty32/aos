# `knowledge/aos/tools/stat.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/tools/stat.md`，跟到正本 commit `fe053b828`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/tools/stat.md#/…` 對的就是它。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

**`#/Tool stat`**

# 工具 stat

顯示一個檔案、資料夾或連結的基本資訊，印成一個 JSON 物件（不是內容）。

用它檢查一個路徑：在不在、是檔案還是資料夾、文字還是二進位、多大、是不是 JSON。整個資料夾用 `ls`，內容用 `read` 或 `view`。

```json
{"path": "cfg.json"}
```
-> `{"path":"cfg.json","type":"file","mtime":"2026-11-11T03:17:02.222+00:00","mode":"0644","size":82,"exec":false,"text":true,"counter_lines":1,"top":{"type":"object","counter_keys":3},"format":"json"}`

- 每個路徑：`type`（file、dir、link）、`mtime`（UTC）、`mode`。
- 檔案：`size`（位元組）、`exec`、`text`（UTF-8 且沒有零位元組）；文字檔再加 `counter_lines` 和 `format`（json、python、markdown、shell、text）；JSON 檔再加 `top`（最上層的摘要）。
- 檔案只讀前 4MB：`text`、`counter_lines` 和 `format` 都是從那部分來的。
- 資料夾：`counter_children`、`aos`（裡面的 aos 檔案，像 `["_entry", "_tooldef.json"]`）。
- 連結：`link_to`，接著是目標的資訊；指向不存在東西的連結：`{"path":"dead","type":"link","link_to":"nowhere","broken":true}`。

錯誤：`aos/tools/stat.md#/stat: errors`。

**`#/stat: errors`**

# stat：錯誤

- `FileMissing`：那個路徑什麼都沒有。`ls` 它上面那個資料夾。
- `ReadFailed`：檔案在，但讀不了（你讀不了的資料夾不是 `ReadFailed`：工具會當掉並印出 traceback；回報它）；到目前為止的資訊不會印出。`ReadFailed`、`WsMissing`：`aos/errors/common.md#/Codes from file work`。錯的或不認得的鍵（`ArgumentsBad`）：`aos/errors/common.md#/Codes about what you gave`。
