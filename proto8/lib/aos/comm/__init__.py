"""comm - comm/1 協議的共用庫（board-1114 批 1：布告欄）：錯誤類別與共用常數；讀寫布告欄在 board.py，時間在 times.py，找 stack 在 root.py，走表在 walk.py。

不是工具（沒有 _entry）。圖紙：proto8/thinking/2026-11/14/board-1114/（02 稿＋03 計劃＋05 採納表；衝突時 05 優先）。
CLI 入口在 proto8/cmd/aos-comm，給腦用的 board_* 五支在 proto8/lib/agent/board_*，都只經這個庫讀寫 board.json。
用法：把 lib/aos 放上 sys.path，`from comm import board`。純標準庫。"""

LEVELS = ("urgent", "normal", "low")        # 信件三級（02 §3.1）；布告欄的 accept 多一個 none


class Fail(Exception):
    """錯誤代號＋英文原因；入口（aos-comm、工具）把它轉成 `程式: error: 代號 原因`。"""

    def __init__(self, code, reason):
        super().__init__(reason)
        self.code = code
