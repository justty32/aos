---
name: aos-tool-apprentice
description: 開發 aos 工具包時，遵守明確範圍、唯讀要求、實質測試與交付格式，並依核對回饋修正行為。
triggers: aos-tool、aos、工具包、唯讀、郵局、測試、交付
---

## 踩過的坑

- 實作看似完成但 CLI 退出 1 → 下次先用指定測試跑完整入口，查看 traceback，修正後重跑測試與獨立核對。
- 引用尚未初始化的解析狀態 → 下次檢查正常資料路徑中每個變數都已賦值，並以有效樣本實際測試。
- 只掃描 inbox 直屬檔案 → 下次依需求遞迴掃描個人信箱的非隱藏子資料夾，納入歸檔信件。
- 把資料夾下所有內容都當成個人信箱 → 下次依資料用途辨認信箱，只掃描符合預期結構的個人資料夾，明確排除團隊資料。
- 把隱藏暫存檔或資料夾當成信 → 下次略過名稱以 `.` 開頭的項目。
- 用信件全文搜尋欄位 → 下次只解析信頭起訖標記之間的內容，忽略信頭外文字。
- 用模糊字串搜尋解析欄位 → 下次逐行解析 `鍵: 值`，只在第一個 `: ` 分割，並精確判定欄位名稱。
- 忽略輸入格式或檔案類型 → 下次明確限定預期檔案類型，並對不合格式的信頭採一致處理。
- 忽略空信箱或零件數 → 下次依規格確認輸出是否包含零計數項目，不自行增刪鍵。
- 只測正常輸出 → 下次涵蓋排序、空資料、巢狀目錄、隱藏項目、信頭邊界，以及不存在路徑和檔案路徑的退出碼與空 stdout。
- 只測函式、不測命令列介面 → 下次以子程序測試實際入口，核對 stdout 行數、JSON 結構、型別與退出碼。
- 把 `bool` 當成整數驗收 → 下次明確檢查欄位型別；規格要求整數時，確認布林值不被接受。
- 假設執行成功就代表唯讀 → 下次比較輸入與父目錄項目的內容、型別、大小、權限與 `mtime_ns`，並確認沒有建立或刪除項目。
- 忽略唯讀輸入或系統狀態副作用 → 下次只讀取輸入，不呼叫寫入、復原或鎖定路徑，也不依賴系統時鐘。
- 把測試通過當成獨立核對通過 → 下次分別執行指定測試和獨立核對，記錄實際結果；未執行就明確標示未驗證。
- 超出允許範圍修改檔案 → 下次先列出授權路徑與件數上限，只修改指定包內檔案及索引列。
- 交付漏掉索引、report 或章節 → 下次核對 README 指定章節、唯一索引列、report 驗證狀態與交接工具清單，並確保指定結尾是全文最後內容。

## 驗過的骨架

入口以精簡 Python 啟動器載入同包模組，並遵守行數上限：

```python
#!/usr/bin/env python3
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aos7_mailstatus import main
if __name__ == "__main__":
    raise SystemExit(main())
```

模組使用標準函式庫。`main(argv=None)` 負責參數與退出碼；錯誤路徑不輸出，成功才輸出單行 JSON：

```python
import json
import os
import sys


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1 or not os.path.isdir(args[0]):
        return 2
    print(json.dumps(result, ensure_ascii=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

測試從檔案位置推導包根目錄與 CLI 入口，透過子程序驗證命令列行為，並提供 `unittest` discover 可載入的測試類別：

```python
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTRY = os.path.join(ROOT, "bin", "aos7-mailstatus")


class MailstatusTests(unittest.TestCase):
    def run_cli(self, path):
        return subprocess.run(
            [sys.executable, ENTRY, path], capture_output=True, text=True
        )
```

README 要有指定章節與可執行入口範例，只描述已實作且已驗證的行為：

```markdown
## 第一次跑

```sh
python3 packs/mailstatus/bin/aos7-mailstatus <郵局資料夾>
```
```

索引只新增一列並連到 README：

```markdown
| `packs/mailstatus/` | 唯讀彙總郵局信件狀態與件數；[第一次跑](packs/mailstatus/README.md) |
```

report 記錄實際完成的測試、核對與限制；未執行的驗證不得宣稱通過。全文以指定標題和工具清單收尾，不在其後添加內容：

```markdown
## 以後交接書該點名的工具
- `python3 proto7-2/tests/run_all.py packs/mailstatus/tests`
- `python3 check_answer.py <proto7-2> fixture`
```