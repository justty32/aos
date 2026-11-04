---
name: aos-tool-apprentice
description: 在限定範圍內交付 aos 唯讀工具，核對資料語義、入口與測試骨架，並如實記錄驗收結果。
triggers: aos-tool、唯讀工具、郵局統計
---

## 踩過的坑

- 症狀：只統計 `inbox/` 頂層時，已歸檔的信漏算，甚至整個信箱被算成零→下次怎麼做：先確認資料生命週期，將仍屬同一信箱的歸檔子目錄納入遍歷，並用全數歸檔案例測試。
- 症狀：掃描所有路徑時，隱藏草稿、暫存資料或團隊信箱可能混入個人統計→下次怎麼做：明確排除隱藏路徑及非個人的保留目錄，以邊界案例核對。
- 症狀：樣本答案接近正確，仍漏掉個別信件或錯算 REQUEST→下次怎麼做：逐一核對信件所在路徑與信頭欄位；測試增加、移除信件及空信箱，避免背固定答案。
- 症狀：只憑程式碼與自寫測試宣稱驗收通過→下次怎麼做：執行指定的實質測試和獨立核對；無法執行時在 report 明說，不能宣稱通過。

## 驗過的骨架

入口保持精簡，從包目錄匯入主模組，並傳回退出碼：

```python
#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from aos7_mailcount import main

if __name__ == "__main__":
    sys.exit(main())
```

主模組自行唯讀解析；無效資料夾回傳 2 且不寫 stdout，成功時只印一行 JSON：

```python
def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1 or not Path(args[0]).is_dir():
        return 2
    print(json.dumps(count(Path(args[0])), ensure_ascii=False, separators=(",", ":")))
    return 0
```

測試從自身位置定位入口，以子行程檢查退出碼與 stdout；測試檔置於 `tests/`，供指定 runner discover：

```python
import subprocess
import sys
import unittest
from pathlib import Path

ENTRY = Path(__file__).resolve().parents[1] / "bin" / "aos7-mailcount"

class MailcountTests(unittest.TestCase):
    def run_cli(self, path):
        return subprocess.run(
            [sys.executable, str(ENTRY), str(path)],
            capture_output=True, text=True, check=False,
        )

if __name__ == "__main__":
    unittest.main()
```

README 保留首次執行章節與驗證命令：

```markdown
## 第一次跑

```sh
python3 packs/mailcount/bin/aos7-mailcount <郵局資料夾>
python3 proto7-2/tests/run_all.py packs/mailcount/tests
python3 check_answer.py <proto7-2> fixture
```
```

索引只新增對應包的一列：

```markdown
| `packs/mailcount/` | [aos7-mailcount：唯讀統計郵局信件](packs/mailcount/README.md) |
```

REPORT 如實寫明已執行與未執行的驗證；結尾保留交接工具段落：

```markdown
## 以後交接書該點名的工具

`python3 proto7-2/tests/run_all.py packs/mailcount/tests`；`python3 check_answer.py <proto7-2> fixture`
```