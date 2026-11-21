# `knowledge/aos/tools/shell.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/tools/shell.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**`#/_description`**

# 工具 shell

執行一行 bash 指令。目前的資料夾是你的工作區。stdout 和 stderr 合在一起回來；最後一行一定是 `[exit code N]`。

用它來計數（`wc -l`）、執行程式和測試、用 git 或管線。不適合：搜尋（檔案內容用 `grep`，檔名用 `glob`：它們的輸出有分頁，不會把你淹沒）、讀檔案（`read`、`view`）、列出一個資料夾（`ls`）、改檔案（`write`、`edit`、`json_set` 精確而且有檢查）。Python 程式碼：`run_python`。

```json
{"command": "grep -rn two notes"}
```
印出
```text
notes/b.txt:2:line two
notes/a.txt:2:line two

[exit code 0]
```

非零的 `[exit code N]` 是你的指令的結果，不是工具錯誤：找不到東西的 `grep` 會印出 `(no output)` 和 `[exit code 1]`。讀輸出，那就是答案。

怎麼執行：`aos/tools/shell.json#/rules`。錯誤：`aos/tools/shell.json#/errors`。

---

**`#/rules`**

# shell：怎麼執行

- `timeout_s`：預設 30，最多 300。超過時整個行程群組會被停掉，呼叫以 `CommandFailed` 失敗。
- 輸出太長時保留最後 2000 行或 50KB，並加一行附註 `[output too long; kept the last N lines (limit 2000 lines or 50KB)]`。接管線到 `head` 或 `tail` 來選要哪一段。
- stdin 是空的：會問問題的指令得不到回答。用它 `-y` 或 `--yes` 那類的旗標。
- 每次呼叫都是新的 bash：`cd` 和變數不會延續。在一個指令裡寫 `cd notes && ls`。
- 被訊號 N 殺掉：`[exit code 128+N]`。更多結束碼：`aos/errors.json#/exits`。
- 它不是沙盒：指令能動到你的 Linux 使用者能動的任何東西。小心 `rm`；優先用 `trash` 工具。

---

**`#/errors`**

# shell：錯誤

- `CommandFailed`：指令跑超過 `timeout_s` 被停掉了（`ran over 30 s; stopped the whole process group`）。到目前為止的輸出會在錯誤行前面。給大一點的 `timeout_s`（最多 300），或讓指令做少一點。
- `LaunchFailed`：bash 啟動不了。是設定的問題：回報它。
- `LogFailed`：你 stack 裡的指令紀錄寫不進去（`aos/errors/common.json#/files`）。
- `ArgumentsBad`：還有 `command` 是空的，或 `timeout_s` 不是大於 0 且最多 300（0 會被拒絕）。
- `WsMissing`：`aos/errors/common.json#/files`。錯的或不認得的鍵（`ArgumentsBad`）：`aos/errors/common.json#/input`。
