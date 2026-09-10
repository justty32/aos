"""daemon 測試的共用基底：一個 `Daemon`（家在 /tmp）、三份 inst.json 的內容、`pump()`。

檔名底線開頭＝`unittest discover` 不會去撿它。真正的測試在 `test_daemon.py`（key、查）
與 `test_daemon_ops.py`（暫停／刪／restart／請求）。

七個動作**都是立刻回**（送個訊號、標個狀態），真的等它退／等它睡著是 `tick()` 的事，
所以測試的寫法都是「下指令 → 一直 tick 到看見結果」。真的會開 aos-run 子進程（value 就是
它），所以每條測試最後 `shutdown()` 收乾淨。
"""
import os
import time

from _util import ExecCase
import aos_daemon
from aos_home import Home

FAST = {"argv": ["sh", "-c", "exit 3"]}         # 一下就跑完，退出碼 3
SLOW = {"argv": ["sh", "-c", "sleep 1"]}        # 跑一秒，拿來測「跑完手上那次」
HALF = {"argv": ["sh", "-c", "sleep 0.5"]}      # 跑 0.5 秒，拿來測 pause 等它睡著
MS100 = ["--interval-ms", "100"]
MS300 = ["--interval-ms", "300"]


class DaemonTest(ExecCase):
    def setUp(self):
        super().setUp()
        self.home = Home(os.path.join(self.d, "home"))
        self.dmn = aos_daemon.Daemon(self.home)
        self.addCleanup(self.dmn.shutdown)      # 收工：全部 SIGTERM／SIGKILL，不留孤兒

    def pump(self, cond, secs=8.0):
        """主迴圈的替身：一直 tick 到 cond 成立（或超時）。"""
        t0 = time.monotonic()
        while time.monotonic() - t0 < secs:
            self.dmn.tick()
            if cond():
                return True
            time.sleep(0.02)
        self.dmn.tick()
        return cond()

    def work(self, obj=FAST, rel="work/inst.json"):
        """寫一份 inst.json 當目標，回它的路徑（key 就是它的 realpath）。"""
        return self.inst(obj, rel)

    def entry(self, w):
        return self.dmn.table[os.path.realpath(w)]

    def log(self):
        with open(self.home.logf, encoding="utf-8") as f:
            return f.read()
