"""aos-run 的訊號狀態、status-fd 事件與 handler 安裝。"""
import os
import signal

SIGNALS = (signal.SIGTERM, signal.SIGINT)


class _State:
    """訊號跟「正在跑的那個子行程」擺在一起，因為第二次訊號要砍的就是它。"""

    def __init__(self):
        self.stop = False       # 收到過訊號＝這次跑完就退
        self.counts = {}        # 每個訊號各自數，「第二次」是指同一個訊號
        self.child = None       # aos_exec 剛開起來的那個 Popen（跑完會被清成 None）
        self.forced = False     # 第二次同一個訊號＝腰斬，退出碼要跟著變
        self.signum = None      # 讓 stop（forced）的那個訊號，算 128+N 要用

    def on_signal(self, signum, frame):
        n = self.counts.get(signum, 0) + 1
        self.counts[signum] = n
        self.stop = True
        self.signum = signum
        if n >= 2:              # 第二次同一個訊號：不等了，砍掉正在跑的那次
            self.forced = True
            _killpg(self.child)

    def hold(self, child):
        """給 `aos_exec.run_target()` 的鉤子：子行程一開起來就記著，跑完傳 None 清掉。"""
        self.child = child


class _Status:
    """`--status-fd N`：給程式看的事件流，一行一個、`\n` 結尾、寫完就到。

    沒給 fd＝什麼都不寫。寫失敗（對方把管子關了）就吞掉——回報狀態不該影響執行。
    """

    def __init__(self, fd):
        self.fd = fd

    def emit(self, line):
        if self.fd is None:
            return
        try:
            os.write(self.fd, (line + "\n").encode("utf-8"))    # 沒緩衝，不用另外 flush
        except OSError:
            pass

    def close(self):
        if self.fd is None:
            return
        try:
            os.close(self.fd)
        except OSError:
            pass
        self.fd = None


def _killpg(child):
    """砍整個 process group（跟 aos-exec 逾時同一個砍法）。已經死了＝ESRCH，無害。"""
    if child is None:
        return
    try:
        os.killpg(os.getpgid(child.pid), signal.SIGKILL)
    except OSError:
        pass


def _install(state):
    """接管 SIGTERM／SIGINT，回一個把原本的裝回去的函式。

    第一次＝讓正在跑的那次跑完再退；第二次同一個訊號＝砍掉正在跑的（SIGKILL 整個群組）。
    不是主執行緒就裝不上（ValueError），那就當沒接管。
    """
    old = {}
    for s in SIGNALS:
        try:
            old[s] = signal.signal(s, state.on_signal)
        except (ValueError, OSError):
            pass

    def restore():
        for s, h in old.items():
            try:
                signal.signal(s, h)
            except (ValueError, OSError):
                pass
    return restore
