# `knowledge/aos/tools/grep.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/tools/grep.md`，跟到正本 commit `fe053b828`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/tools/grep.md#/…` 對的就是它。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

**`#/Tool grep`**

# 工具 grep

用正規表示式在檔案裡面搜尋，像 `grep -rn`：每個符合一行，`PATH:LINE:TEXT`。把 PATH 貼進 `read` 當 `path`；LINE 就是它的 `offset`。

用它找一個字或模式出現在資料夾樹或一個檔案的哪裡。不適合：用名字找檔案（`glob`）、讀檔案（`read`）；管線、計數：`shell`。

參數：`pattern`（必填，Python `re`，逐行比對）；`path`（資料夾或檔案，預設 `.`）；`glob`（只看這些檔案，例如 `*.py`）；`fixed`；`ignore_case`；`context`（0 到 5）；`files`；`hidden`；`gitignore`；`offset`；`max_matches`（預設 100，最多 500）。

```json
{"pattern": "two", "path": "notes", "max_matches": 2}
```
印出
```text
notes/a.txt:2:line two
notes/b.txt:1:two words
... next_offset 2 (3 matches in 3 files in all)
... skipped 1 binary file
```

`... ` 開頭的行是附註：`next_offset N` = 用 `"offset": N` 再呼叫一次；`no matches` = 什麼都沒找到；`no matches from offset N` = `offset` 已經超過最後一個符合。`files`、`context`：`aos/tools/grep.md#/grep: files and context`。略過、`... stopped`：`aos/tools/grep.md#/grep: what it searches`。錯誤：`aos/tools/grep.md#/grep: errors`。

**`#/grep: files and context`**

# grep：files 與 context

`"files": true`：每個有符合的檔案一行，`PATH<TAB>matching lines`；`offset` 和 `max_matches` 改成算檔案數。
```json
{"pattern": "two", "path": "notes", "ignore_case": true, "files": true}
```
印出
```text
notes/a.txt	1
notes/b.txt	2
notes/old/c.md	1
... skipped 1 binary file
```

`"context": N`：每個符合的前後各 N 行，寫成 `PATH-LINE-TEXT`（用 `-` 代替 `:`）；組與組之間用一行 `--` 隔開。
```json
{"pattern": "more", "context": 1}
```
印出
```text
notes/b.txt-1-two words
notes/b.txt:2:more
notes/b.txt-3-Two again
... skipped 1 binary file
```

**`#/grep: what it searches`**

# grep：它搜尋什麼

- 順序：依路徑（每一層依名字），再依行。順序固定，所以用 `offset` 分頁不會重複。
- `... skipped`：二進位檔（前 8KB 裡有 NUL）、超過 8MB 的檔、讀不了的檔。
- 名字以 `.` 開頭的（`.git`、`.stack`）只有在 `"hidden": true`，或 `glob` 有點名它們（`.github/**`）時才搜。
- 在 git 工作樹裡，被 `.gitignore` 的路徑（`build/`、`node_modules/`）和 `.git` 會被排除；`"gitignore": false` 會保留它們。沒有 git = 一個警告，什麼都不排除。
- 指向資料夾的連結不會跟進去；指向檔案的連結用連結的路徑來搜。`path` 本身是連結或單一檔案時，照給的樣子搜（單一檔案時會忽略 `glob`）。
- 一次一行（不會跨行比對）；結尾的 `\r` 會去掉；不是 UTF-8 的位元組會變成替代字元。印出的行超過 300 個字元時，結尾會是 `…[cut]`。
- 掃描預算：20 秒或 20000 個名字，然後出現 `... stopped after ...`；總數會寫 `at least`。把 `path` 或 `glob` 縮小。

**`#/grep: errors`**

# grep：錯誤

- `PatternBad`：正規表示式編譯不過；原因裡有 Python 的訊息（`missing ), unterminated subpattern at position 5`）。修正它，或用 `"fixed": true`。壞掉的 `glob` 也是這個（`glob: unclosed [ ...`）。
- `FileMissing`：沒有這個路徑。用 `ls` 或 `glob` 確認。
- `ReadFailed`：`path` 本身讀不了，或者不是一般檔案或資料夾。樹裡更深處讀不了的檔案只會被計數。
- `ArgumentsBad`：還有 `context` 不在 0 到 5、`max_matches` 不在 1 到 500、`offset` 是負的。
- `WsMissing`：`aos/errors/common.md#/Codes from file work`。錯的或不認得的鍵（`ArgumentsBad`）：`aos/errors/common.md#/Codes about what you gave`。
