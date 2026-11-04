---
name: aos-tool-apprentice
description: 交付範圍受限的 aos 唯讀工具時，核對資料語義、CLI 契約、測試、唯讀性與交接格式。
triggers: aos-tool、唯讀工具、郵局統計
---

## 踩過的坑

- 症狀：只掃信箱頂層，信件歸檔後答案變少。→ 下次怎麼做：遞迴掃描個人 `inbox/` 的非隱藏子資料夾，測試全部歸檔後答案不變。
- 症狀：草稿、暫存或團隊信箱影響答案。→ 下次怎麼做：排除隱藏檔、隱藏目錄及 `teams/`；只讀個人信箱中的 `.md` 信件。
- 症狀：主樣本多出未結案 id，或增減信件後答案不對。→ 下次怎麼做：從當前輸入逐封解析完整信頭；收集 `status: REQUEST` 的 `id`，再扣除任何信件以結案狀態指向的 `re`。`PROGRESS` 不算結案，不靠檔名或固定答案。
- 症狀：輸出內容看似正確，卻因鍵、型別、排序或退出碼未過關。→ 下次怎麼做：核對 JSON 恰有 `v`、`open`，用 `type(value) is int` 排除布林值；檢查 id 升冪、成功 stdout 恰一行，以及無效路徑退出 2 且 stdout 為空。
- 症狀：程式宣稱唯讀，卻只比對信件內容。→ 下次怎麼做：執行前後比對輸入與父目錄的型別、大小、權限、mtime_ns 和檔案位元組；不匯入寫入、復原或鎖定路徑。
- 症狀：交接報告把未執行的核對寫成通過。→ 下次怎麼做：記錄實際執行的命令與結果；無法執行時明說未驗證，不宣稱退出 0 或 `ok true`。

## 驗過的骨架

入口從自身位置定位同包模組，保持短小；模組自行解析資料，不依賴 aos 的寫入流程。

```python
#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aos7_mailopen import main

if __name__ == "__main__":
    sys.exit(main())
```

信頭須由第一行 `---` 讀至下一個獨立的 `---`，欄位以第一個 `: ` 分割；缺少完整信頭時不計入。

```python
def header(path):
    fields = {}
    with path.open(encoding="utf-8") as mail:
        if mail.readline().rstrip("\r\n") != "---":
            return {}
        for line in mail:
            line = line.rstrip("\r\n")
            if line == "---":
                return fields
            key, separator, value = line.partition(": ")
            if separator:
                fields[key] = value
    return {}
```

掃描時先排除非個人目錄，再遞迴讀取有效信件；用集合去重，最後排序。CLI 先驗證參數與目錄，成功才印一行 JSON，不讀系統時鐘。

```python
def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1 or not Path(args[0]).is_dir():
        return 2
    print(json.dumps(
        {"v": 1, "open": open_ids(Path(args[0]))},
        ensure_ascii=False,
        separators=(",", ":"),
    ))
    return 0
```

測試檔用 `test_*.py` 命名供 discover 找到；從自身路徑定位入口，以子程序檢查真實 stdout 和退出碼，並關閉 bytecode 寫入。

```python
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ENTRY = Path(__file__).resolve().parents[1] / "bin" / "aos7-mailopen"

class MailopenTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "-B", str(ENTRY), *(str(arg) for arg in args)],
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )

if __name__ == "__main__":
    unittest.main()
```

README 說明讀取範圍，保留首次執行章節，交代成功輸出與無效路徑行為。

````markdown
# 工具名稱

一句話說明讀取範圍與輸出內容。

## 第一次跑

```sh
python3 packs/<包名>/bin/<入口> <資料夾>
```

成功輸出一行 JSON；無效資料夾退出 2，stdout 為空。
````

索引只新增對應包的一列；report 列出交付範圍與實際驗證狀態，末尾點名實質測試及獨立核對工具。

```markdown
| `packs/<包名>/` | [工具名稱](packs/<包名>/README.md)：一句話描述。 |
```

```markdown
# REPORT

交付範圍：列出包內檔案及索引列。
驗證：記錄實際執行結果；未執行則明說。

## 以後交接書該點名的工具

- `python3 proto7-2/tests/run_all.py packs/<包名>/tests`
- `python3 check_answer.py <proto7-2> fixture`
```