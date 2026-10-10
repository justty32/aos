---
name: aos-tool-apprentice
description: 新增 aos 工具時遵守範圍、唯讀、安全、測試與交付規範。
triggers: aos-tool、AOS、郵局、唯讀工具、獨立核對
---

## 踩過的坑

- 漏掉仍屬於信箱的歸檔資料→依資料契約確認歸檔位置；若在 `inbox/` 子資料夾內，遞迴掃描該信箱的 inbox。
- 把暫存檔或團隊資料算進個人信件→只排除契約明定的項目；不可把其他專案的規則直接套用，並以測試驗證各類資料。
- 只按副檔名或檔案數彙總，沒有解析指定欄位→依契約解析信頭，確認起始標記、終止標記與欄位格式，再統計欄位值。
- 信頭不完整或編碼錯誤時中斷整個掃描→明確定義無效資料的處理方式；遵守任務契約，不改寫輸入，也不擅自計入無法解析的欄位。
- 使用未經契約允許的掃描範圍或排除規則→先釐清輸入格式和範圍，只實作有依據的行為，並用代表性測試防止過度排除。
- 驗證路徑後仍可能在掃描時遇到 I/O 錯誤→明確定義錯誤行為，避免輸出部分結果；區分無效輸入與成功輸出。
- 無效路徑時印出錯誤或 JSON→先驗證參數與路徑；依契約退出並保持 stdout 空。
- 跟隨符號連結或特殊檔案而越出允許範圍→明確檢查檔案類型與 symlink 行為，不要不加判斷地走訪。
- 唯讀工具意外改動輸入→自行解析資料，不呼叫寫入、復原或鎖定路徑；確保內容、型別、權限與 metadata 不變，並涵蓋唯讀輸入測試。
- 依賴系統時鐘或匯入會造成副作用的程式碼→只讀取完成任務所需的資料，避免時鐘與不必要依賴。
- 輸出看似正確但鍵、型別、排序或行數不符→逐項測試鍵集合、精確型別、排序、單行輸出及退出碼；Python 的 `bool` 不可視為整數通過驗證。
- 只寫單元測試就宣稱驗收完成→執行指定實質測試及獨立唯讀核對；未執行時明確標示未驗證，不得宣稱通過。
- 忽略檔案數或修改範圍限制→開始前確認允許路徑和件數 gate；交付前核對變更，只新增或修改明確允許的項目。
- README 或索引缺少實際使用資訊→README 提供指定章節、可執行命令、輸出和錯誤行為；索引只新增契約允許的一列。
- REPORT 把預期結果寫成已驗證結果→記錄實際修改和實際執行的檢查；未執行就註明未驗證，並以指定標題列出交接工具。

## 驗過的骨架

入口腳本保持精簡，加入工具目錄後匯入模組的 `main`；控制在任務要求的行數內：

```python
#!/usr/bin/env python3
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aos7_mailstatus import main

if __name__ == "__main__":
    raise SystemExit(main())
```

模組自行解析輸入，不依賴 aos 寫入、復原或鎖定路徑。依任務契約實作路徑驗證、欄位解析、彙總與排序；無效路徑不輸出 stdout，成功只輸出一行 JSON：

```python
import json
import os
import stat
import sys


def count_statuses(root):
    counts = {}
    # Scan only the data described by the contract and parse the required fields.
    return {"v": 1, "statuses": dict(sorted(counts.items()))}


def main():
    if len(sys.argv) != 2:
        return 2
    try:
        mode = os.stat(sys.argv[1], follow_symlinks=False).st_mode
        if not stat.S_ISDIR(mode):
            return 2
        result = count_statuses(sys.argv[1])
    except OSError:
        return 2
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

測試放在工具的 `tests/`，透過入口驗證外部行為，並可由指定 runner discover；檢查結果值、鍵集合、排序、精確型別與無效路徑：

```python
# tests/test_mailstatus.py
import json
import os
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTRY = os.path.join(ROOT, "bin", "aos7-mailstatus")


class MailstatusTests(unittest.TestCase):
    def test_counts_and_output_contract(self):
        # Build a temporary input tree; assert counts, keys, ordering and exact types.
        ...

    def test_invalid_paths_are_silent(self):
        # Assert missing paths and regular files exit 2 with empty stdout.
        ...


if __name__ == "__main__":
    unittest.main()
```

README 必須包含 `## 第一次跑`，說明用途、可直接執行的命令、成功輸出契約及無效路徑行為：

```markdown
# <工具名稱>

簡述用途。

## 第一次跑

提供可直接執行的命令、成功輸出契約、無效路徑行為及必要資料範圍。
```

索引只新增一列：

```text
| `packs/<tool>/` | <簡短用途說明> |
```

REPORT 記錄實際修改與驗證結果；未執行的檢查必須標示未驗證。結尾須點名交接工具：

```text
# REPORT
- 說明實作範圍與唯讀保證。
- 列出實質測試與獨立核對的實際結果；未執行則標示未驗證。

## 以後交接書該點名的工具

- `python3 proto7-2/tests/run_all.py packs/<tool>/tests`
- `python3 check_answer.py <proto7-2> fixture`
```