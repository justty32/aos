"""process_group - 收掉自己起的那一群子行程：先 TERM 整群、等一下、還在就 KILL；外面來的 TERM／Ctrl-C 變成例外，讓呼叫處先收拾再走。

不是工具（沒有 _entry）；shell、run_python 用 stop、Interrupted、raise_interrupted，lib/agent/cmd_call 的 kill_group 借 stop（等幾秒、吞哪種錯由參數帶）。
來由：thinking 2026-11/12/codebase-cleanup 線 F——原本 shell、run_python 各一份 stop 與 Interrupted，cmd_call 一份 kill_group。
"""
import os
import signal
import subprocess


class Interrupted(BaseException):
    """外面送來的訊號（TERM／INT）；signum＝那個訊號號。"""

    def __init__(self, signum):
        self.signum = signum


def raise_interrupted(signum, frame):
    """訊號處理器：把訊號變成 Interrupted 丟出去。"""
    raise Interrupted(signum)


def stop(p, grace_s, kill_wait_s=None, gone=ProcessLookupError):
    """先 TERM p 那一群、等 p 最多 grace_s 秒；還在就 KILL 整群、再等最多 kill_wait_s 秒（None＝等到它結束）。
    送訊號遇到 gone 這種錯＝那群已經不在，直接回。"""
    for sig, wait_s in ((signal.SIGTERM, grace_s), (signal.SIGKILL, kill_wait_s)):
        try:
            os.killpg(p.pid, sig)
        except gone:
            return
        try:
            p.wait(wait_s)
            return
        except subprocess.TimeoutExpired:
            pass
