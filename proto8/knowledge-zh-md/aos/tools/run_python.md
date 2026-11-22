# `knowledge/aos/tools/run_python.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/tools/run_python.md`，跟到正本 commit `fe053b828`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/tools/run_python.md#/…` 對的就是它。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

**`#/Tool run_python`**

# 工具 run_python

跑一個短的 Python 3 程式，拿到它印出的東西（stdout 和 stderr 合在一起）。最後一行一定是 `[exit code N]`。

用它來做計算、解析或改造資料，以及在 bash 裡不好做的檢查。不要用在：單一個算術式（`math`）、用 `edit` 或 `json_set` 就能做的變更、shell 指令（`shell`）。

```json
{"code": "import json\nprint(json.dumps({\"n\": 6 * 7}))"}
```
印出
```text
{"n": 42}
[exit code 0]
```

例外會印出它的 traceback 和 `[exit code 1]`。那是你程式的結果，不是工具錯誤：修好程式碼再跑一次。

怎麼跑：`aos/tools/run_python.md#/run_python: how it runs`。錯誤：`aos/tools/run_python.md#/run_python: errors`。

**`#/run_python: how it runs`**

# run_python：怎麼跑

- 目前的資料夾是你的工作區，跟 `shell` 一樣：像 `open("data/a.csv")` 這樣的相對路徑在那裡讀寫。程式本身存成你 stack 裡這個工具自己的資料夾裡的 `main.py`（`tools/run_python/`；你沒有 stack 時是一個暫存資料夾），不在工作區裡。
- 只能指望標準函式庫。它以 `python3 -I` 執行：沒有使用者的 site packages，`PYTHON*` 變數會被忽略。
- 輸出超過 8000 個字元時，保留前 3000 和後 3000，中間放 `... (N chars omitted) ...`。
- `timeout_s`：預設 60，最多 300。超過時整個程序群組會被停掉。
- 被訊號 N 殺掉：`[exit code 128+N]`。結束碼：`aos/errors.md#/Exit codes`。
- 它不是沙箱：程式碰得到你的 Linux 使用者碰得到的任何東西。

**`#/run_python: errors`**

# run_python：錯誤

- `CommandFailed`：程式跑超過 `timeout_s`，被停掉了。它到那時為止印出的東西會在錯誤行前面。給大一點的 `timeout_s`（最多 300），或一次少做一點。
- `WsMissing`：你沒有工作區（`AOS_WS` 沒設或不是資料夾）。設定問題：回報它。
- `LaunchFailed`：python3 啟動不了。設定問題：回報它。
- `LogFailed`：你 stack 裡的指令紀錄寫不了（`aos/errors/common.md#/Codes from file work`）。
- `ArgumentsBad`：也包括空的 `code`，或 `timeout_s` 不是大於 0 且最多 300（0 會被拒絕）。鍵錯了或不認得（`ArgumentsBad`）：`aos/errors/common.md#/Codes about what you gave`。
