---
name: aos-tool-apprentice
description: 從候選實作與驗收紀錄整理 aos 唯讀工具的避坑原則、交付骨架與核對方式。
triggers: aos-tool、唯讀工具、郵局統計
---

## 踩過的坑

- 症狀：只掃 `inbox/` 頂層，歸檔後的信不計入 → 下次同時掃每人的 `inbox/` 與 `inbox/done/`，並測試所有信都已歸檔的情況。
- 症狀：隱藏草稿或團隊廣播混入結果 → 下次排除以 `.` 開頭的項目與 `teams/`，只統計指定信箱位置的 `.md` 檔。
- 症狀：沿用其他郵局工具的 REQUEST 關聯邏輯，統計件數時漏信 → 下次先確認輸出語義；按 status 計數時逐封計入，不以 `id`、`re` 去重或扣除。
- 症狀：從檔名或資料夾推斷 status，結果不隨信頭變動 → 下次自行讀取 `---` 包住的信頭，以第一個 `: ` 分隔鍵值，從 `status` 欄位計數。
- 症狀：固定樣本碰巧正確，增減信件後結果錯誤 → 下次測增減信件、空信箱、歸檔、隱藏項目與團隊資料，不把預期件數寫死在實作中。
- 症狀：答案正確但格式或無效路徑不合 → 下次核對完整鍵集合、整數型別（排除 bool）、status 鍵升冪、恰一行 stdout，以及無效路徑退出碼 2 且 stdout 為空。
- 症狀：程式沒有明寫入，仍可能產生 bytecode 或改動輸入 metadata → 下次停用 bytecode，比較輸入與父目錄執行前後的型別、大小、權限、`mtime_ns` 和內容。
- 症狀：自寫測試通過，仍不能證明獨立核對通過 → 下次執行指定測試與 fixture 核對；無法執行時如實標記未確認，不宣稱驗收通過。

## 驗過的骨架

入口保持精簡：先停用 bytecode，再從包目錄匯入模組；不匯入 aos 寫入、復原或鎖定路徑。

```python
#!/usr/bin/env python3
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from aos7_mailstatus import main

if __name__ == "__main__":
    sys.exit(main())
```

模組只用標準函式庫讀取信頭；逐封累加 status，排序後輸出一行 JSON。掃描範圍只含個人信箱的頂層與歸檔目錄。

```python
import json
import sys
from pathlib import Path

def status_from(path):
    with path.open(encoding="utf-8") as stream:
        if stream.readline().rstrip("\r\n") != "---":
            return None
        for line in stream:
            line = line.rstrip("\r\n")
            if line == "---":
                break
            if line.startswith("status: "):
                return line.split(": ", 1)[1]
    return None

def statuses(root):
    counts = {}
    for person in root.iterdir():
        if person.name.startswith(".") or person.name == "teams" or not person.is_dir():
            continue
        inbox = person / "inbox"
        for folder in (inbox, inbox / "done"):
            if not folder.is_dir():
                continue
            for path in folder.iterdir():
                if path.name.startswith(".") or path.suffix != ".md" or not path.is_file():
                    continue
                status = status_from(path)
                if status is not None:
                    counts[status] = counts.get(status, 0) + 1
    return dict(sorted(counts.items()))

def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1 or not Path(args[0]).is_dir():
        return 2
    print(json.dumps({"v": 1, "statuses": statuses(Path(args[0]))},
                     ensure_ascii=False, separators=(",", ":")))
    return 0
```

測試檔採 `test_*.py`，讓 discover 找得到；以入口檔啟動子行程，不依賴安裝狀態。測固定結果與增減信件，也核對輸出型別、排序、無效路徑及執行前後快照。

```python
import json
import subprocess
import sys
import unittest
from pathlib import Path

ENTRY = Path(__file__).resolve().parents[1] / "bin" / "aos7-mailstatus"

def run(*args):
    return subprocess.run(
        [sys.executable, str(ENTRY), *(str(arg) for arg in args)],
        capture_output=True, text=True, check=False,
    )

class MailstatusTests(unittest.TestCase):
    def test_output_shape(self):
        # 在測試建立的郵局目錄上執行，並比較輸入與父目錄的前後快照。
        result = run(self.mail_root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.count("\n"), 1)
        data = json.loads(result.stdout)
        self.assertEqual(set(data), {"v", "statuses"})
        self.assertIs(type(data["v"]), int)
        self.assertEqual(data["v"], 1)
        self.assertEqual(list(data["statuses"]), sorted(data["statuses"]))
        for count in data["statuses"].values():
            self.assertIs(type(count), int)
```

README 保留首次執行章節與兩個核對指令；索引只加一列。report 記錄交付範圍及實際驗證結果，末尾點名交接工具。

```markdown
## 第一次跑

python3 packs/mailstatus/bin/aos7-mailstatus <郵局資料夾>

python3 proto7-2/tests/run_all.py packs/mailstatus/tests
python3 check_answer.py <proto7-2> fixture
```

```markdown
| `packs/mailstatus/` | [aos7-mailstatus](packs/mailstatus/README.md)：唯讀彙總個人郵局信件的 status 件數。 |
```

```markdown
# REPORT

交付範圍、實際測試結果與尚未確認的事項。

## 以後交接書該點名的工具

- `python3 proto7-2/tests/run_all.py packs/mailstatus/tests`
- `python3 check_answer.py <proto7-2> fixture`
```