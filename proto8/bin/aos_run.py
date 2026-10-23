"""aos_run：跑「一次」——loop.json 的 run、fsm.json 格的 val（同一套寫法；名字不同見 C-55）。aos-loop、aos-fsm 共用。純標準庫。

    import aos_run
    aos_run.block()        程式一開始呼叫：之後 SIGINT／SIGTERM／SIGHUP 不打死這支程式，記下來
    aos_run.take()         兩次之間：有記下的訊號就回第一個（沒有＝0）
    aos_run.run(x, args)   跑一次，回 {"code", "signal", "elapsed_ms", "received"}

x 只收字串（aos-exec 的目標；10-21 plan L11、F2）：子行程 `aos-exec -- <x> args...`（照 PATH 找；`--` 讓 - 開頭的目標
不被當旗標，L10；跟呼叫者同一個行程群組，同 subprocess.call）；跑的期間收到的三個訊號 os.kill 給那個子行程
（不另設 SIGKILL 期限）。要內嵌單子就讓目標指到它（`loop.json#/body`、`fsm.json#/states/<名>/body`），
由 aos-exec 在它自己的行程裡跑、當監工（逾時與轉來的訊號打整群，N-59 第 5 件）。這一次看不到格裡有沒有逾時（C-52）：
被逾時收掉的那次就是 code 128＋15（或補 SIGKILL 的 137）、signal None——那次是 aos-exec 子行程，它收掉單子後
以子程式的碼正常結束，不是自己被訊號殺掉；signal 只在那次的那個行程（aos-exec，或它 exec 成的程式）本身被訊號殺掉時
有值（10-22 實測更正，原寫 signal 15／9）。
received＝跑的期間收到、轉給那次的第一個訊號（沒有＝None）；呼叫者收完這次要以 128＋它結束（CONVENTION P-36
「先收好自己起的子程式、寫好狀態再結束，結束碼非 0」）。起不了 aos-exec 丟 StartError。
對齊 impls 的 aos-loop（aos/loop.hpp 的 block_signals／take_signal／run_once，ideas § 24）。
"""
import os
import signal
import subprocess
import time

_SIGNALS = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)
_got = []          # 兩次之間（或那次期間）收到的，依序
_child = [None]    # 那次正在跑的子行程
_pending = []      # 子行程還沒記進 _child 時收到的，起來後補轉


class StartError(Exception):
    """起不了子程式（aos-exec、daemon 的子 loop）；呼叫者印一行「程式名: 代號 原因」、退 1。code 沒給＝LaunchFailed。"""

    def __init__(self, msg, code="LaunchFailed"):
        super().__init__(msg)
        self.code = code


def _on_signal(signum, frame):
    _got.append(signum)
    p = _child[0]
    if p is None:
        _pending.append(signum)
    elif p.returncode is None:
        try:
            os.kill(p.pid, signum)
        except ProcessLookupError:
            pass


def block():
    for s in _SIGNALS:
        signal.signal(s, _on_signal)


def take():
    return _got[0] if _got else 0


def run(x, args=()):
    # 收到任何一個訊號，呼叫者這次收完就結束，所以 _got 在第一次之前是空的、之後也只會有這一次收到的
    t0 = time.monotonic()
    try:
        _child[0] = p = subprocess.Popen(["aos-exec", "--", x] + list(args))
    except OSError as e:
        _child[0] = None
        raise StartError("起不了 aos-exec：%s" % e)
    while _pending:   # 子行程記進 _child 之前收到的，補轉
        try:
            os.kill(p.pid, _pending.pop(0))
        except ProcessLookupError:
            pass
    rc = p.wait()     # 訊號處理完 wait 自己會接著等（PEP 475）
    _child[0] = None
    return {"code": rc if rc >= 0 else 128 - rc, "signal": -rc if rc < 0 else None,
            "elapsed_ms": round((time.monotonic() - t0) * 1000), "received": _got[0] if _got else None}
