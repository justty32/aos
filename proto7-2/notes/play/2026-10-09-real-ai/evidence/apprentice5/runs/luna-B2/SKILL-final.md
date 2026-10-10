---
name: aos-tool-apprentice
description: 為 aos 建立範圍明確、可驗證的工具包，並遵守唯讀、測試與交付要求。
triggers: aos-tool、aos、工具包、唯讀、郵局
---

## 踩過的坑

- 測試匯入失敗→測試執行器不一定把工具模組所在目錄加入 `sys.path`；測試檔應以自身位置推導包目錄，再匯入模組。
- 只掃描 `inbox/` 頂層→歸檔信件可能位於子目錄；遞迴掃描信箱，同時排除名稱以 `.` 開頭的檔案與目錄。
- 把所有非隱藏目錄都當成人→資料根目錄可能包含團隊等非個人資料；依資料格式明確排除非個人目錄。
- 把每個 `.md` 都計為請求→只有信頭分隔區內 `status: REQUEST` 才算；需確認第一行與結束分隔行，並只解析第一個 `: ` 前的鍵。
- 無效路徑仍輸出訊息→CLI 對錯誤路徑應在輸出前回傳指定退出碼，保持 stdout 空白。
- 聲稱測試或獨立檢查已通過→未實際執行不得宣稱通過；交付報告應如實記錄結果與未完成的核驗。
- 忽略唯讀驗收的副作用→只讀取輸入，不呼叫寫入、復原或鎖定路徑；在驗收前後核對內容、型別、大小、權限及 mtime 等要求涵蓋的 metadata。
- 不符範圍或件數限制→改動前先確認允許的路徑與檔案上限；只提交列明的檔案及索引列。

## 驗過的骨架

入口以短 Python 腳本將包目錄加入匯入路徑，再呼叫模組的 `main`：

```python
#!/usr/bin/env python3
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aos7_mailcount import main
if __name__ == "__main__":
    raise SystemExit(main())
```

測試用檔案位置推導模組目錄，避免依賴執行器的工作目錄：

```python
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aos7_mailcount import count_mailbox, main
```

以指定執行器實際發現並執行測試；測試涵蓋資料統計、信頭解析、邊界路徑及 CLI 輸出：

```sh
python3 proto7-2/tests/run_all.py packs/mailcount/tests
```

README 至少提供指定章節與基本執行方式：

```markdown
## 第一次跑

```sh
python3 packs/mailcount/bin/aos7-mailcount /path/to/mailbox
```
```

索引新增一列，連到包內 README：

```markdown
| `packs/mailcount/` | Read-only mailbox letter and REQUEST counts; [README](packs/mailcount/README.md) |
```

Report 說明交付內容與實際驗證狀態；末尾必須點名交接工具：

```markdown
## 以後交接書該點名的工具
- `python3 proto7-2/tests/run_all.py packs/mailcount/tests`
- `python3 check_answer.py <proto7-2> fixture`
```