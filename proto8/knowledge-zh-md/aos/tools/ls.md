# `knowledge/aos/tools/ls.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/tools/ls.md`，跟到正本 commit `fe053b828`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/tools/ls.md#/…` 對的就是它。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

**`#/Tool ls`**

# 工具 ls

列出一個資料夾：每個項目一行，`NAME<TAB>TYPE`（type 是 `file`、`dir` 或 `link`）。資料夾在前，檔案在後，各自照名字排序。

用它看一個資料夾裡有什麼。不適用於：看單一項目的細節（`stat`）、看檔案裡面有什麼（`read`、`view`）、在整棵樹裡照名字找檔案（`glob`）、在檔案裡面搜尋（`grep`）。

參數，全部可選：`path`（預設 `.`＝你的工作區）、`long`、`json`、`hidden`、`offset`、`max_items`（預設 100，最多 500）。

```json
{"path": "notes", "max_items": 1}
```
印出
```text
a.txt	file
... next_offset 1 (2 items in all)
... 1 hidden (names starting with .)
```

`... next_offset N`：還有更多；用 `"offset": N` 再呼叫一次。名字以 `.` 開頭的（像 `.trash`）會被隱藏，除非給 `"hidden": true`。一頁沒有項目也沒有隱藏的名字時（空資料夾，或 `offset` 超過結尾），印出 `... empty`。

`long` 的各欄和 `json`：`aos/tools/ls.md#/ls: long and json`。錯誤：`aos/tools/ls.md#/ls: errors`。

**`#/ls: long and json`**

# ls：long 和 json

`"long": true` 多加三欄：SIZE（位元組；只有檔案有，其他是 `-`）、MTIME（UTC）、INFO。

```text
my_tool	dir	-	2026-11-11T03:17:02.222+00:00	children 2 aos _entry,_tooldef.json
notes	dir	-	2026-11-11T03:17:02.222+00:00	children 1
cfg.json	file	82	2026-11-11T03:17:02.222+00:00	keys name,states,max
```

資料夾的 INFO：`children N`，裡面有 aos 檔案（`_entry`、`_tooldef.json`、`loop.json`、`tools.json` 等等：這時這個資料夾是一個工具或一個 agent 定義）時再加 `aos ...`。檔案的話：`exec`，`.json` 檔再加上它最上層的鍵（不是合法 JSON 時是 `json broken`；最上層不是物件時是 `json array` 或 `json value`）。只列出前 12 個鍵，之後是 `+N`。超過 1MB 的 .json 檔不會打開：沒有鍵。列出時消失的名字，TYPE 是 `missing`。連結的話：`-> target`。

`"json": true` 印出一個 JSON 物件而不是一行行：`path`、`counter_items`（所有項目；名字以 `.` 開頭的只有加 `hidden` 時才算）、`items`（name、type、size、mtime 和 INFO 的那些資訊）、`next_offset`、`counter_hidden`。

**`#/ls: errors`**

# ls：錯誤

- `FileMissing`：沒有這個資料夾。列出它上一層的資料夾。
- `FileBad`：這條路徑是檔案，不是資料夾。對它用 `stat` 或 `read`。
- `ArgumentsBad`：也包括 `max_items` 不在 1 到 500 之間，或 `offset` 是負的。
- `ReadFailed`、`WsMissing`：`aos/errors/common.md#/Codes from file work`。錯誤或不認得的鍵（`ArgumentsBad`）：`aos/errors/common.md#/Codes about what you gave`。
