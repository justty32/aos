# `knowledge/aos/tools/edit.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/tools/edit.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**`#/_description`**

# 工具 edit

用精確取代的方式改一個文字檔的一部分。`edits` 的每一項是 `{"old_text": "...", "new_text": "..."}`。

規則：每個 `old_text` 都拿去比對這次呼叫之前的檔案。它必須剛好出現一次，一字不差（空格、tab、換行也算）。各項不能重疊。只要有一項失敗，什麼都不改。

用在：你讀過的檔案裡改幾處。不要用在：新檔案或整份重寫（`write`）、JSON 檔裡的值（`json_set` 比較安全）。

```json
{"path": "out/hello.txt", "edits": [{"old_text": "world", "new_text": "there"}]}
```
印出 `In out/hello.txt, replaced 1 places (first at line 2)`。

- 先 `read` 這個檔案，從裡面一字不差地抄 `old_text`。
- `old_text` 要短但唯一：出現不只一次時，把它前一行或後一行加進來。
- 刪掉文字：`"new_text": ""`。
- Windows 行尾（CRLF）的檔案也行：`old_text` 用 `\n` 寫；CRLF 行尾會保留（只要有一個行尾是 CRLF，全部都寫成 CRLF）。
- 連結：改的是它指向的那個檔案。

錯誤：`aos/tools/edit.json#/errors`。

---

**`#/errors`**

# edit：錯誤

發生下面任何一種時，什麼都不改。

- `TextMissing`：有個 `old_text` 不在檔案裡。常見原因：空格或縮排不同、tab 對上空格、行尾，或是你讀過之後檔案改了。再 `read` 一次，一字不差地抄。
- `TextBad`：有個 `old_text` 出現 N 次（把它周圍的行加進來直到唯一）；有個 `old_text` 是空的；兩項重疊（合成一項）；或檔案會保持不變。
- `FileMissing`：沒有這個檔案，或路徑是資料夾（新檔案用 `write`）。`FileBad`：不是 UTF-8 文字檔。
- `ArgumentsBad`：也包括 `edits` 是空的，或某一項沒有那兩個字串。
- `ReadFailed`、`WriteFailed`、`WsMissing`：`aos/errors/common.json#/files`。鍵寫錯或不認得的鍵（`ArgumentsBad`）：`aos/errors/common.json#/input`。
