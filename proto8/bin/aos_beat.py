"""aos_beat：跑「一拍」——loop.json 的 run、fsm.json 格的 val（同一套寫法 C-55）。aos-loop、aos-fsm 共用。純標準庫。

    import aos_beat
    aos_beat.block()        程式一開始呼叫：之後 SIGINT／SIGTERM／SIGHUP 不打死這支程式，記下來
    aos_beat.take()         拍與拍之間：有記下的訊號就回第一個（沒有＝0）
    aos_beat.run(x, ref_base, args)  跑一拍，回 {"code", "signal", "timed_out", "ms", "received"}（ref_base＝單子裡 $ref 的起點）

x 是字串＝子行程 `aos-exec -- <x> args...`（照 PATH 找；`--` 讓 - 開頭的目標不被當旗標，10-21 plan L10；
args 只有字串那條路用；跟呼叫者同一個行程群組，同 subprocess.call）；跑的期間收到的三個訊號
os.kill 給那個子行程（不另設 SIGKILL 期限）。x 是物件＝inst 單子，行程內 aos_inst.run()（它轉給整群、grace 後 SIGKILL）——10-21 起只剩 aos-fsm 用（loop 的 run 只收字串）。
received＝跑的期間收到、轉給那拍的第一個訊號（沒有＝None）；呼叫者收完這拍要以 128＋它結束（CONVENTION P-36
「先收好自己起的子程式、寫好狀態再結束，結束碼非 0」）。單子壞丟 aos_inst.InstError。
對齊 impls 的 aos-loop（aos/loop.hpp 的 block_signals／take_signal／run_beat，ideas § 24）。
"""
import os
import signal
import subprocess
import time

import aos_inst

_SIGNALS = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)
_got = []          # 拍外（或字串那拍期間）收到的，依序
_child = [None]    # 字串那拍正在跑的子行程
_pending = []      # 子行程還沒記進 _child 時收到的，起來後補轉


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


def run(x, ref_base=None, args=()):
    # 收到任何一個訊號，呼叫者這拍收完就結束，所以 _got 在第一拍之前是空的、之後也只會有這一拍收到的
    if not isinstance(x, str):
        res = aos_inst.run(x, ref_base=ref_base)   # 跑的期間換上它自己的轉送（收到的放在 res["received"]），回來換回 _on_signal
        out = {k: res[k] for k in ("code", "signal", "timed_out", "ms")}
        out["received"] = res["received"] or (_got[0] if _got else None)
        return out
    t0 = time.monotonic()
    try:
        _child[0] = p = subprocess.Popen(["aos-exec", "--", x] + list(args))
    except OSError as e:
        _child[0] = None
        raise aos_inst.InstError("起不了 aos-exec：%s" % e)
    while _pending:   # 子行程記進 _child 之前收到的，補轉
        try:
            os.kill(p.pid, _pending.pop(0))
        except ProcessLookupError:
            pass
    rc = p.wait()     # 訊號處理完 wait 自己會接著等（PEP 475）
    _child[0] = None
    return {"code": rc if rc >= 0 else 128 - rc, "signal": -rc if rc < 0 else None, "timed_out": False,
            "ms": round((time.monotonic() - t0) * 1000), "received": _got[0] if _got else None}
