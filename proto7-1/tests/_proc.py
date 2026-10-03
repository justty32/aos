"""測試共用：起的子程序一律先收、再刪空間（astra-5 F-11、infra-needs N-55）。

用法：Popen 成功的下一行就 `track(self, p)`（或 `self.addCleanup(reap, p)`）。unittest 的 cleanup 是後進先出，
所以在 `addCleanup(shutil.rmtree, tmp)` 之後才註冊的 reap 會**先**跑：assertion 失敗、TimeoutExpired、
其他例外都一樣。KeyboardInterrupt 讓 unittest 不跑 cleanup 時，程序結束前 atexit 也會把還沒收的收掉。
"""
import atexit
import os
import signal
import subprocess

GRACE = 3.0
_live = []          # 還沒收的 [(Popen, grace, group)]：atexit 照登記時的選項收（astra-6 G-07）
_hooked = False


def reap(p, grace=GRACE, group=False):
    """terminate → 限時 wait → kill → wait（group=True 時對整個程序群組送訊號：start_new_session 起的 daemon 用）。
    之後關掉 pipe。重複呼叫無害。"""
    _live[:] = [x for x in _live if x[0] is not p]

    def sig(s):
        try:
            if group:
                os.killpg(p.pid, s)
            else:
                p.send_signal(s)
        except (ProcessLookupError, PermissionError, OSError):
            pass
    if p.poll() is None:
        sig(signal.SIGTERM)
        try:
            p.wait(grace)
        except subprocess.TimeoutExpired:
            sig(signal.SIGKILL)
            p.wait()
    elif group:
        sig(signal.SIGKILL)   # 主程序走了，群組裡可能還有它起的 tick／tock
    for f in (p.stdin, p.stdout, p.stderr):
        if f:
            try:
                f.close()
            except OSError:
                pass


def _reap_left():
    for q, grace, group in list(_live):
        reap(q, grace, group)


def track(case, p, grace=GRACE, group=False):
    """登記 p：測試結束（不論成敗）先 reap，再跑比它早登記的 rmtree。回 p。"""
    global _hooked
    _live.append((p, grace, group))
    if not _hooked:
        # 晚於第一個 TemporaryDirectory 登記：atexit 後進先出，會比它的刪除先跑（Ctrl-C 時）。
        # 沿用每筆登記的 grace／group，和正常 cleanup 一樣收整個群組（astra-6 G-07）
        atexit.register(_reap_left)
        _hooked = True
    if case is not None:
        case.addCleanup(reap, p, grace, group)
    return p
