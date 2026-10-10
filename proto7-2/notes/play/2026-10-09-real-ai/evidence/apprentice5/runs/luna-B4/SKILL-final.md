---
name: aos-tool-apprentice
description: 建立範圍明確、唯讀且可驗證的 aos 工具，交付程式、測試、索引與報告。
triggers: aos-tool、唯讀工具、郵局統計、AOS 套件、交付驗收
---

## 踩過的坑

- 核心路徑第一次遇到正常資料就失敗→先初始化解析狀態，再用有效輸入跑測試；不要只依賴錯誤路徑測試。
- 只掃信箱頂層→信件可能在 `inbox/done/` 等歸檔子資料夾；遞迴掃描，並明確排除隱藏檔案與資料夾。
- 把所有目錄都當成個人信箱→根目錄可能有團隊資料；依資料格式辨識個人信箱，排除非個人資料夾。
- 從檔名或正文猜狀態→只解析信頭，驗證起始分隔線、獨立結束分隔線及欄位格式。
- 以成功開啟檔案作為唯讀保證→不呼叫寫入、復原或鎖定路徑；不跟隨符號連結，並確認遍歷不會改動輸入及父目錄的內容、權限或 metadata。
- 忽略輸出契約細節→逐項核對 JSON 鍵集合、值型別、排序、行數與退出碼；布林值不符合整數要求。
- 只測固定樣本→涵蓋歸檔信、暫存檔、團隊資料、空信箱、排序、資料變動及無效路徑。
- 測試通過就宣稱交付完成→執行指定測試與獨立檢查；無法執行就如實記錄，不宣稱通過。
- 交付超出允許範圍→先確認可修改路徑與檔案數上限，只交付必要檔案及索引列。

## 驗過的骨架

命令列入口保持精簡，將模組所在目錄加入匯入搜尋路徑，再呼叫 `main`：

```python
#!/usr/bin/env python3
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aos7_mailstatus import main
if __name__ == "__main__":
    raise SystemExit(main())
```

模組提供可測試的核心函式與命令列入口；無效路徑不輸出，成功只輸出一行 JSON：

```python
import json
import os
import sys


def count_mailbox(root):
    # 回傳符合工具契約的彙總結果。
    ...


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1 or not os.path.isdir(args[0]):
        return 2
    result = count_mailbox(args[0])
    print(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

測試檔直接匯入套件模組，放在 runner 可 discover 的測試目錄，並以標準測試框架覆蓋核心行為與 CLI：

```python
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from aos7_mailstatus import count_mailbox


class MailstatusTests(unittest.TestCase):
    def test_counts_expected_cases(self):
        ...


if __name__ == "__main__":
    unittest.main()
```

README 說明用途、首次使用方式、成功輸出與無效路徑行為：

```markdown
# aos7-mailstatus

唯讀彙總郵局資料並輸出 JSON。

## 第一次跑

```sh
python3 packs/mailstatus/bin/aos7-mailstatus /path/to/mailbox
```

成功時輸出至 stdout；無效路徑依工具契約回傳退出碼且不輸出。
```

索引只新增一列，簡述功能並連到套件 README：

```markdown
| `packs/mailstatus/` | 唯讀彙總郵局信件狀態；詳見 [README](packs/mailstatus/README.md)。 |
```

報告記錄交付檔案與驗證結果；未執行的檢查不得寫成通過，並以指定標題及工具清單結尾：

```markdown
# REPORT

- 交付檔案與索引列：……
- 測試與獨立檢查結果：如實記錄執行結果及未完成事項。

## 以後交接書該點名的工具
- `python3 proto7-2/tests/run_all.py packs/mailstatus/tests`
- `python3 check_answer.py <proto7-2> fixture`
```