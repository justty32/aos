---
name: aos-tool-apprentice
description: 新增 aos 唯讀工具時，對齊資料語意、CLI 契約與獨立核對，保留可重用的交付骨架。
triggers: aos-tool、唯讀工具、郵局資料統計
---

## 踩過的坑

- 症狀：只掃 `inbox/` 頂層時，歸檔後的信全部漏算。→ 下次怎麼做：先確認有效資料是否涵蓋子目錄，再以實際資料邊界設計遞迴走訪測試。
- 症狀：把隱藏草稿或暫存目錄當成信，件數偏高。→ 下次怎麼做：檢查相對路徑的每個部分，排除以 `.` 開頭的檔案與目錄。
- 症狀：把團隊資料夾當成人名，輸出多出不該有的信箱。→ 下次怎麼做：區分根目錄下的人員信箱與其他用途的資料夾，測試兩者並存。
- 症狀：主樣本看似接近，辦結、增減或唯讀情境仍得出錯誤答案。→ 下次怎麼做：用會改變答案的邊界樣本驗證走訪與計數規則，不背固定結果；跑完實質測試，再跑獨立核對。
- 症狀：程式讀取時留下快取或改動輸入及父目錄 metadata。→ 下次怎麼做：入口在匯入本地模組前停用 bytecode；測試前後比對型別、內容、權限、大小與 `mtime_ns`，並核對唯讀環境。

## 驗過的骨架

入口保持精簡，先設定匯入路徑，再載入同包模組；讓模組的 `main()` 決定退出碼：

```python
#!/usr/bin/env python3
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from aos7_mailcount import main

if __name__ == "__main__":
    raise SystemExit(main())
```

模組只用標準函式庫讀取資料；無效目錄回傳 `2` 且不輸出，成功時只印一行 JSON。信頭解析在第二個獨立的 `---` 行停止，只把信頭中精確的 `status: REQUEST` 算作請求；輸出鍵與型別依契約固定。

```python
import json
import sys
from pathlib import Path

def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        return 2
    root = Path(args[0])
    if not root.is_dir():
        return 2
    print(json.dumps(count(root), ensure_ascii=False, separators=(",", ":")))
    return 0
```

測試由入口實際啟動 CLI，並以 `-B` 避免測試執行產生 bytecode；測試檔命名為 `test_*.py`，供測試 discover：

```python
import subprocess
import sys
from pathlib import Path

ENTRY = Path(__file__).resolve().parents[1] / "bin" / "aos7-mailcount"

def run(path):
    return subprocess.run(
        [sys.executable, "-B", str(ENTRY), str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
```

README 保留首次執行章節與驗證指令；索引只加一列：

```markdown
## 第一次跑

    python3 packs/mailcount/bin/aos7-mailcount <郵局資料夾>

    python3 proto7-2/tests/run_all.py packs/mailcount/tests
    python3 check_answer.py <proto7-2> fixture
```

```markdown
| `packs/mailcount/` | [aos7-mailcount：唯讀郵局信件統計](packs/mailcount/README.md) |
```

Report 記錄改動、測試與核對的實際結果；沒有執行就明確標示未驗證。結尾保留工具清單：

```markdown
## 以後交接書該點名的工具

- `python3 proto7-2/tests/run_all.py packs/mailcount/tests`
- `python3 check_answer.py <proto7-2> fixture`
```