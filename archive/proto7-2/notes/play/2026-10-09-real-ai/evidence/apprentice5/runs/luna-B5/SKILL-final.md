---
name: aos-tool-apprentice
description: 新增 aos 工具包時，遵守範圍限制、唯讀要求、測試與交付格式。
triggers: aos-tool、aos、工具包、郵局、唯讀、INDEX.md、REPORT
---

## 踩過的坑

- 只統計 inbox 直接子項會漏掉歸檔信→遞迴掃描每個人的 inbox，並確認巢狀歸檔仍計入。
- 將所有目錄都當成人員會誤計團隊信箱→排除 `teams/`，也排除隱藏檔與隱藏資料夾。
- 信頭解析到結尾分隔線仍回傳空結果→逐行解析起始 `---` 到下一個獨立 `---`，並回傳已解析的寄件者。
- 只測統計函式會漏掉 CLI 行為→涵蓋成功時恰一行 JSON，以及錯誤路徑回傳 2 且 stdout 為空。
- 以可寫目錄測唯讀不足以驗證唯讀→以唯讀輸入核對內容、權限、mtime_ns 及目錄狀態前後不變；留意執行可能建立 `__pycache__`。
- 測試只涵蓋固定答案會漏掉邊界→驗證排序、空信箱、巢狀歸檔、排除項目、無效信頭及增減信件後的動態結果。
- 未執行指定驗收便宣稱通過→如實記錄執行結果；無法執行時，註明驗收與獨立核對尚未確認。
- 超出允許範圍或檔案數會造成交付失敗→先確認檔案範圍與件數 gate，只修改明確允許的項目。
- README 缺少指定章節會造成文件驗收失敗→使用精確章節標題 `## 第一次跑`。
- 漏掉索引列或 report 必備結尾會讓交付不完整→提供一列 INDEX 項目，並以「以後交接書該點名的工具」作為 report 結尾。
- 交付格式要求只回文件時加上解說或外層圍欄會造成失敗→直接輸出完整文件，依規定保留標題、程式碼圍欄與結尾。

## 驗過的骨架

入口：

```python
#!/usr/bin/env python3
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aos7_mailcount import main
if __name__ == "__main__":
    raise SystemExit(main())
```

模組匯入與測試匯入：

```python
# CLI 模組位於包目錄，啟動器將該目錄加入匯入路徑。
from aos7_mailcount import main

# 測試從包目錄匯入被測模組。
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from aos7_mailcount import count_senders
```

測試 discover 入口：

```python
if __name__ == "__main__":
    unittest.main()
```

README 必要章節與首次執行範例：

```markdown
# aos7-mailcount

## 第一次跑

```sh
python3 packs/mailcount/bin/aos7-mailcount /path/to/R
```
```

INDEX.md 單列形式：

```markdown
| `packs/mailcount/` | 唯讀統計郵局信箱信件數 | `packs/mailcount/README.md` |
```

REPORT 結尾形式：

```markdown
## 以後交接書該點名的工具

- `python3 proto7-2/tests/run_all.py packs/mailcount/tests`
- `python3 check_answer.py <proto7-2> fixture`
```