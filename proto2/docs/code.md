# code 工具包

這包先只管 Python 專案。
世界資料夾就是專案根目錄。
agent 的 home 建議放在專案裡的 `.aos-agent/`。

## 工具

- `code_outline(path)`：看一個 Python 檔的類別、函式、方法與行號。第一次碰檔案時先用。
- `code_search(query, path=".", context=2, limit=20)`：找原樣文字。最多 50 筆。先把 `path` 縮小再找。
- `code_check(path)`：用 `py_compile` 檢查 Python 語法。每次小改後用。
- `code_checkpoint(paths)`：修改前存檔。檔案放在 `<home>/.aos-undo/<編號>/`。
- `code_diff()`：把現在的檔案跟最近一次存檔比較。
- `code_undo()`：還原最近一次存檔。原本不存在的檔案會移除。存檔本身不刪。

改檔仍用 `fs` 包的 `edit` 或 `write`。
跑小測試仍用 `fs` 包的 `sh`。
這包不提供 patch。

## 設定

在 agent 的 `tools.json` 加上：

```json
{"packs": ["code", "fs"], "tools": []}
```

如果 `fs` 還沒裝好，可暫時開 `shell` 包跑指令。

## 坑

- 路徑都從世界資料夾算。跑到世界外面的路徑會被擋下。
- 搜尋會跳過 `.git`、`.aos-agent`、`.aos-undo` 與 `__pycache__`。
- `code_search` 只找完全相同的文字。它不懂正規表示式。
- `code_checkpoint` 只收檔案，不收資料夾，也不會自動清舊存檔。
- `code_undo` 只撤銷存過的檔案。它撤不回 shell 指令造成的其他變化。
- 第一版不管 Python 以外的語言、二進位檔、同時修改與超大專案。
