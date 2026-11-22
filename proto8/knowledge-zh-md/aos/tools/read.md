# `knowledge/aos/tools/read.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/tools/read.md`，跟到正本 commit `fe053b828`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/tools/read.md#/…` 對的就是它。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

**`#/Tool read`**

# 工具 read

讀一個文字檔。你拿到的是它的各行純文字（不加行號）。

用在：你想讀的文字檔，整份或分段。不要用在：資料夾（`ls`）、檔案的大小和類型（`stat`）、要先看地圖的大檔案（`view` 給大綱）、JSON 檔裡的一個值（`json_get`）。

參數：`path`（相對於你的工作區，或絕對路徑）；`offset`（第一行，第一行是 1）；`max_lines`。空檔案印出 `(empty file)`。

```json
{"path": "notes/a.txt", "offset": 2, "max_lines": 1}
```
印出
```text
line two

[1 more lines in the file. Use offset=3 to continue.]
```

一次呼叫最多顯示 2000 行或 50KB。輸出被截斷時，最後一行會說從哪裡接著讀，像 `[lines 1-2000 of 2500. Use offset=2001 to continue.]`：用那個 `offset` 再呼叫一次。

錯誤：`aos/tools/read.md#/read: errors`。

**`#/read: errors`**

# read：錯誤

- `FileMissing`：沒有這個路徑。在它的資料夾用 `ls` 檢查名字。
- `FileBad`：路徑是資料夾（用 `ls`）、二進位檔（不會讀），或要印的第一行超過 50KB（原因裡會給一個印出其中一部分的 `shell` 指令）。
- `ArgumentsBad`：也包括 `offset` 或 `max_lines` 小於 1 或不是整數；以及 `offset` 超過檔案結尾時；原因會給行數。
- `ReadFailed`、`WsMissing`：`aos/errors/common.md#/Codes from file work`。鍵寫錯或不認得的鍵（`ArgumentsBad`）：`aos/errors/common.md#/Codes about what you gave`。
