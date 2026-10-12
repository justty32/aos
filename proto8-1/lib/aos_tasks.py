"""tasks 小程式共用的部分：找到 proto8/lib、一次讀好全部 inst、接訊號。純標準庫。

tasks 是一組小程式，每支做一件事，跟 aos_inst 一樣是獨立的命令列程式，寫在 inst.json 的 argv 裡被跑。
參數一律是 inst 的 TARGET（`.json` 檔或資料夾，同 aos_inst），相對路徑從自己的 cwd 算。
要巢狀就讓某個 inst.json 的 argv 再寫一支 tasks 程式。
"""
import os
import signal
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "proto8", "lib"))

from aos_inst import InstError, load  # noqa: E402

__all__ = ["InstError", "load_all", "Signals"]

_CAUGHT = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)


def load_all(targets, usage, least=1, most=None):
    """全部 TARGET 先讀好、驗過，回 inst 的 list；個數不在 least～most（None＝不限）印用法、
    有任何一個不對就印「代號: 白話」，都回 None（一個都不跑）。"""
    if len(targets) < least or most is not None and len(targets) > most:
        print("用法：%s" % usage, file=sys.stderr)
        return None
    insts = []
    for t in targets:
        try:
            insts.append(load(t))
        except InstError as e:
            print(e, file=sys.stderr)
            return None
    return insts


class Signals:
    """`with Signals() as sig:` 期間收到 SIGINT／SIGTERM／SIGHUP 不死：記下第一個（`sig.got`），按下 `sig.stop`。
    傳給 `run(stop=sig.stop)`，正在跑的子程式就被收掉（SIGTERM，過 grace 再 SIGKILL）。"""

    def __init__(self):
        self.got = None
        self.stop = threading.Event()

    def _catch(self, signum, frame):
        if self.got is None:
            self.got = signum
        self.stop.set()

    def __enter__(self):
        self._old = {s: signal.signal(s, self._catch) for s in _CAUGHT}
        return self

    def __exit__(self, *exc):
        for s, h in self._old.items():
            signal.signal(s, h)
