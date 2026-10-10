---
name: aos-tool-apprentice
description: 建立受限範圍內的 aos 唯讀工具，核對郵局資料布局、輸出契約、測試與交付格式。
triggers: aos-tool、唯讀工具、郵局統計
---

## 踩過的坑

- 症狀：只掃 `inbox/` 頂層，信件歸檔後答案變空。→ 下次同時讀取每人的 `inbox/` 與 `inbox/done/`，測試全部歸檔後答案不變。
- 症狀：掃描過廣，將暫存檔或團隊信件算入。→ 下次排除以 `.` 開頭的項目及 `teams/`，分別測隱藏檔、隱藏目錄與團隊信箱。
- 症狀：將正文的 `status` 或 `re` 誤作信頭。→ 下次要求首行為 `---`，在下一個獨立 `---` 行停止，只以第一個 `: ` 拆欄位。
- 症狀：把 PROGRESS 當結案，或只看同一人的回信。→ 下次先收集所有人信箱中的 REQUEST id 與終態回信的 re，再做集合差；終態限 DONE、BLOCKED、NEEDS-USER、FAILED。
- 症狀：固定樣本正確，增減信件後答案錯誤。→ 下次測新增、刪除、空信箱及排序；核對鍵集合、字串陣列與整數 `v`，不能讓布林值冒充整數。
- 症狀：只比對檔案內容就宣稱唯讀。→ 下次連輸入及父目錄一起拍前後快照，核對型別、大小、權限、`mtime_ns` 與內容；測唯讀輸入。
- 症狀：未執行命令卻宣稱驗收通過。→ 下次在報告區分測試設計與實際結果，未執行就明列未驗證。

## 驗過的骨架

入口保持精簡，從包目錄匯入模組並傳回退出碼：

```python
#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from aos7_mailopen import main

if __name__ == "__main__":
    sys.exit(main())
```

模組只用標準庫自行讀取信頭，不匯入寫入、復原或鎖定路徑；只掃個人信箱的指定位置：

```python
import json
import sys
from pathlib import Path

CLOSED = {"DONE", "BLOCKED", "NEEDS-USER", "FAILED"}

def header(path):
    with path.open(encoding="utf-8") as stream:
        if stream.readline().rstrip("\r\n") != "---":
            return {}
        fields = {}
        for line in stream:
            line = line.rstrip("\r\n")
            if line == "---":
                return fields
            key, separator, value = line.partition(": ")
            if separator:
                fields[key] = value
    return {}

def letters(inbox):
    for folder in (inbox, inbox / "done"):
        if folder.is_dir():
            for path in folder.iterdir():
                if (not path.name.startswith(".") and path.suffix == ".md"
                        and path.is_file()):
                    yield path

def open_requests(root):
    requests, closed = set(), set()
    for person in root.iterdir():
        if person.name.startswith(".") or person.name == "teams" or not person.is_dir():
            continue
        inbox = person / "inbox"
        if not inbox.is_dir():
            continue
        for letter in letters(inbox):
            fields = header(letter)
            if fields.get("status") == "REQUEST" and fields.get("id"):
                requests.add(fields["id"])
            if fields.get("status") in CLOSED and fields.get("re"):
                closed.add(fields["re"])
    return sorted(requests - closed)

def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1 or not Path(args[0]).is_dir():
        return 2
    print(json.dumps({"v": 1, "open": open_requests(Path(args[0]))},
                     ensure_ascii=False, separators=(",", ":")))
    return 0
```

測試檔以 `test_` 命名供 discover 收集；用子程序測入口，不依賴工作目錄，並核對退出碼、stdout 與唯讀快照：

```python
import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

ENTRY = Path(__file__).resolve().parents[1] / "bin" / "aos7-mailopen"

def snapshot(root):
    result = {}
    for path in (root.parent, root, *root.rglob("*")):
        info = path.lstat()
        result[str(path)] = (
            stat.S_IFMT(info.st_mode), info.st_size,
            stat.S_IMODE(info.st_mode), info.st_mtime_ns,
            path.read_bytes() if path.is_file() else None,
        )
    return result

class MailopenTest(unittest.TestCase):
    def run_cli(self, path):
        return subprocess.run(
            [sys.executable, str(ENTRY), str(path)],
            capture_output=True, text=True, check=False,
        )

    def assert_open(self, root, expected):
        result = self.run_cli(root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.count("\n"), 1)
        data = json.loads(result.stdout)
        self.assertEqual(set(data), {"v", "open"})
        self.assertIs(type(data["v"]), int)
        self.assertEqual(data, {"v": 1, "open": expected})

if __name__ == "__main__":
    unittest.main()
```

README、索引及報告維持可核對的交付格式；報告只記實際執行結果：

```text
README.md:
# 工具名稱
## 第一次跑
入口命令、成功輸出、無效路徑退出碼、測試與核對命令

INDEX.md:
| `packs/<名稱>/` | [工具名稱](packs/<名稱>/README.md)：一句話用途。 |

REPORT:
交付檔案與索引列、測試涵蓋範圍、實際執行及獨立核對結果。
## 以後交接書該點名的工具
`python3 proto7-2/tests/run_all.py packs/<名稱>/tests`
`python3 check_answer.py <proto7-2> fixture`
```