# comm/1 協議的共用庫：布告欄讀寫與四步算法、時間、找 stack、走表（aos-comm 與 board_* 工具共用）。

不是工具（沒有 _entry）。圖紙：[board-1114](../../../../thinking/2026-11/14/board-1114.md)（02 稿＋03 計劃＋05 採納表；衝突時 05 優先）。

| 檔 | 做什麼 |
|---|---|
| `__init__.py` | 錯誤類別與共用常數 |
| `board.py` | 讀、寫（flock＋暫存檔 rename）、06 §7.3 四步算法 |
| `times.py` | ISO 8601 時間與 30m／8h／2d 長度 |
| `root.py` | 自己的 stack 根（tools/<名> 認回根）、使用者專區 |
| `walk.py` | 走 daemon 表（含 --deep 的嵌套、上限、防繞圈） |
