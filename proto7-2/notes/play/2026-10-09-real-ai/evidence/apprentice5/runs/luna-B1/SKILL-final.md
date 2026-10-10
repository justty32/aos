---
name: aos-tool-apprentice
description: 新增 aos 工具時，遵守範圍、唯讀與驗收約束，並記錄可重用的通過骨架。
triggers: aos-tool、aos、新增工具、唯讀、驗收
---

## 踩過的坑

- 只處理郵件收件匣頂層→按資料模型遞迴檢查收件匣子目錄，歸檔信也屬於該信箱。
- 把團隊資料夾或隱藏項目算成人或信→明確排除 `teams/`，並排除以 `.` 開頭的檔案與目錄。
- 只測試主樣本→測試歸檔信、空信箱、暫存項目、團隊資料與增減信件，確認答案是依輸入計算而非寫死。
- 使用寫入或復原路徑處理輸入→自行唯讀解析；不建立、刪除或修改輸入，也不碰其權限與 metadata。
- 錯誤路徑仍輸出內容→先驗證參數與資料夾；失敗時回傳指定退出碼且保持 stdout 空白。
- 把 REQUEST 判定寫得含糊→只解析信頭分隔線之間的欄位，精確比對狀態值。
- 聲稱測試通過但未實際執行→分開記錄已執行的測試、獨立核對與唯讀檢查；未執行就明確說明。
- 交付範圍悄悄擴大→只改任務允許的路徑，檢查變更檔數並保留使用者既有變更。

## 驗過的骨架

入口腳本保持精簡，將套件路徑加入匯入搜尋路徑，再呼叫模組的 `main`：

```python
#!/usr/bin/env python3
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aos7_mailcount import main
if __name__ == "__main__":
    sys.exit(main())
```

模組可直接匯入標準函式庫；測試從檔案位置推導入口路徑，不依賴目前工作目錄：

```python
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTRY = os.path.join(ROOT, "bin", "aos7-mailcount")
```

測試使用 `unittest`、臨時資料夾與子程序驗證 CLI，並讓測試執行器 discover 到測試類別：

```python
class ToolTests(unittest.TestCase):
    def test_example(self):
        with tempfile.TemporaryDirectory() as root:
            result = subprocess.run(
                [sys.executable, ENTRY, root],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0)
            payload = json.loads(result.stdout)
            self.assertIs(type(payload["v"]), int)


if __name__ == "__main__":
    unittest.main()
```

README 使用清楚的第一次執行章節，說明命令與成功、失敗行為：

```markdown
## 第一次跑

```sh
python3 packs/<工具>/bin/<命令> <資料夾>
```

成功時退出碼為 `0`；無效路徑依規格回傳錯誤碼，且不輸出 JSON。
```

索引新增一列，連到套件 README：

```markdown
| `packs/<工具>/` | [工具說明](packs/<工具>/README.md) |
```

report 記錄交付範圍與驗證狀態；不能把未執行的檢查寫成通過。最後須包含交接工具標題與必用命令：

```markdown
# REPORT

交付內容與驗證結果；未實際執行的檢查須明確標示。

## 以後交接書該點名的工具
`python3 proto7-2/tests/run_all.py packs/<工具>/tests` 與 `python3 check_answer.py <proto7-2> fixture`
```