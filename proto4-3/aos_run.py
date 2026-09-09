"""aos-run：aos-exec 的連續執行版——同一個目標一直跑，跑到某個停止條件成立為止。

    aos-run xxx [--dir-target REL] [--timeout-ms N] [--interval-ms N] [--from-start]
                [--max-runs N] [--time-limit-ms N] [--stop-exit CODE]...

執行那一段**完全不重寫**：核心就是反覆呼叫 `aos_exec.run_target()`。這支只管三件事——
下一次什麼時候開始（`--interval-ms`／`--from-start`）、什麼時候停（四個停止條件）、
每跑完一次印一行到自己的 stderr。

**不寫任何紀錄檔、不注入任何 `AOS_*` 環境變數**，跟 aos-exec 一樣乾淨（proto4 筆記 §12.1）。
之後整合進 aos-daemon 時，cpu 的「跑一次」那段就是 import 這裡的 `run_loop()`。
"""
import argparse
import os
import signal
import sys
import time

import aos_exec

DEFAULT_INTERVAL_MS = 1000      # 時間旗標一律毫秒整數，跟 aos-exec 的 --timeout-ms 一致
STEP = 0.05     # 睡覺的小步：訊號與硬時限最多晚這麼久被發現，不能一睡五秒不理人
SIGNALS = (signal.SIGTERM, signal.SIGINT)


class _State:
    """訊號跟「正在跑的那個子行程」擺在一起，因為第二次訊號要砍的就是它。"""

    def __init__(self):
        self.stop = False       # 收到過訊號＝這次跑完就退
        self.counts = {}        # 每個訊號各自數，「第二次」是指同一個訊號
        self.child = None       # aos_exec 剛開起來的那個 Popen（跑完會被清成 None）

    def on_signal(self, signum, frame):
        n = self.counts.get(signum, 0) + 1
        self.counts[signum] = n
        self.stop = True
        if n >= 2:              # 第二次同一個訊號：不等了，砍掉正在跑的那次
            _killpg(self.child)

    def hold(self, child):
        """給 `aos_exec.run_target()` 的鉤子：子行程一開起來就記著，跑完傳 None 清掉。"""
        self.child = child


def _killpg(child):
    """砍整個 process group（跟 aos-exec 逾時同一個砍法）。已經死了＝ESRCH，無害。"""
    if child is None:
        return
    try:
        os.killpg(os.getpgid(child.pid), signal.SIGKILL)
    except OSError:
        pass


def _stderr(msg):
    sys.stderr.write(msg + "\n")
    sys.stderr.flush()


def run_loop(xxx, *, dir_target=aos_exec.DEFAULT_DIR_TARGET, timeout_ms=0,
             interval_ms=DEFAULT_INTERVAL_MS, from_start=False, max_runs=0,
             time_limit_ms=0, stop_exits=(), log=None, install_signals=True):
    """一直跑 `xxx`，回 `(退出碼, 停止原因)`。四種停止都是退出碼 0。

    - `timeout_ms`：**每一次**執行的上限，原樣傳給 `run_target()`；0＝不限。
    - `interval_ms`：兩次執行之間的間隔（毫秒）。
    - `from_start`：間隔從上一次**開始**的時刻算；預設是從上一次**結束**算。
      一次跑超過 interval 時下一次立刻開始、不補跑錯過的格。
    - `max_runs`／`time_limit_ms`／`stop_exits`：三個停止條件，0／空＝不設。
    - `log`：吃一個字串的函式，預設印到 stderr（daemon 之後可以換掉）。
    - `install_signals`：接管 SIGTERM／SIGINT。當函式庫用、不想被接管就傳 False。

    退出碼 1（inst.json 壞掉）**不停**，照 interval 一直試——壞了也活著，要停就 `stop_exits`。
    """
    log = log or _stderr
    stop_exits = set(stop_exits or ())
    state = _State()
    restore = _install(state) if install_signals else None
    interval = interval_ms / 1000.0             # 對外毫秒、對內秒（time.monotonic 的單位）
    begin = time.monotonic()
    deadline = (begin + time_limit_ms / 1000.0) if time_limit_ms else None
    n = 0
    next_at = begin                      # 第一次不等，馬上跑
    try:
        while True:
            reason = _sleep_until(next_at, deadline, state)
            if reason:
                return _stop(log, reason)
            started = time.monotonic()
            eff = _effective_timeout(timeout_ms, deadline, started)
            if eff == 0 and deadline is not None:
                return _stop(log, "time_limit")     # 剩不到 1 毫秒，那就別開了
            code = aos_exec.run_target(xxx, dir_target, eff, on_spawn=state.hold)
            state.child = None
            n += 1
            log("aos-run: #%d exit=%d %.1fs" % (n, code, time.monotonic() - started))
            if state.stop:
                return _stop(log, "signal")
            if code in stop_exits:
                return _stop(log, "stop_exit")
            if max_runs and n >= max_runs:
                return _stop(log, "max_runs")
            if deadline is not None and time.monotonic() >= deadline:
                return _stop(log, "time_limit")
            # 從開始算＝上次起點＋interval（已經過頭就是立刻）；從結束算＝現在＋interval
            next_at = (started if from_start else time.monotonic()) + interval
    finally:
        if restore:
            restore()


def _stop(log, reason):
    log("aos-run: stop %s" % reason)
    return 0, reason


def _effective_timeout(timeout_ms, deadline, now):
    """整體時限是**硬**的：正在跑的那次也要被砍，所以把它折成這一次的 timeout_ms。

    不另開執行緒——min(原本的或無限, 剩下的毫秒) 交給 aos-exec 本來就有的那套砍法。
    """
    if deadline is None:
        return timeout_ms
    left = int((deadline - now) * 1000)
    if left <= 0:
        return 0
    return left if not timeout_ms else min(timeout_ms, left)


def _sleep_until(next_at, deadline, state):
    """睡到 `next_at`，回停止原因（可以跑就回 None）。小步睡，才叫得醒。"""
    while True:
        if state.stop:
            return "signal"
        now = time.monotonic()
        if deadline is not None and now >= deadline:
            return "time_limit"         # 睡覺中撞到整體時限＝醒來就退
        left = next_at - now
        if left <= 0:
            return None
        if deadline is not None:
            left = min(left, deadline - now)
        time.sleep(min(STEP, left))


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


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="aos-run", description="把一個目標（檔案／.json／資料夾）一直執行下去")
    ap.add_argument("xxx", help="要執行的東西：普通檔案、.json 檔，或資料夾")
    ap.add_argument("--dir-target", default=aos_exec.DEFAULT_DIR_TARGET,
                    help="xxx 是資料夾時要跑的相對路徑（預設 .aos/inst.json）")
    ap.add_argument("--timeout-ms", type=int, default=0,
                    help="每一次執行的上限（毫秒），0 或不給＝不限")
    ap.add_argument("--interval-ms", type=int, default=DEFAULT_INTERVAL_MS, metavar="N",
                    help="兩次執行之間的間隔（毫秒，預設 1000）")
    ap.add_argument("--from-start", action="store_true",
                    help="間隔從上一次開始的時刻算（不加＝從上一次結束算）")
    ap.add_argument("--max-runs", type=int, default=0, metavar="N",
                    help="跑滿 N 次就停，0＝不限")
    ap.add_argument("--time-limit-ms", type=int, default=0, metavar="N",
                    help="從起跑算的整體時限（毫秒；硬的：正在跑的那次會被砍），0＝不限")
    ap.add_argument("--stop-exit", type=int, action="append", default=[],
                    metavar="CODE", help="某一次的退出碼是 CODE 就停（可以給很多次）")
    a = ap.parse_args(argv)

    for name, v in (("--timeout-ms", a.timeout_ms), ("--interval-ms", a.interval_ms),
                    ("--max-runs", a.max_runs), ("--time-limit-ms", a.time_limit_ms)):
        if v < 0:
            ap.error("%s 不能是負數" % name)         # argparse 的用法錯＝退出碼 2
    for c in a.stop_exit:
        if c < 0:
            ap.error("--stop-exit 不能是負數（退出碼不會是負的）")
    if not os.path.exists(a.xxx):
        sys.stderr.write("aos-run: 找不到 %s\n" % a.xxx)
        return 2

    code, _reason = run_loop(a.xxx, dir_target=a.dir_target, timeout_ms=a.timeout_ms,
                             interval_ms=a.interval_ms, from_start=a.from_start,
                             max_runs=a.max_runs, time_limit_ms=a.time_limit_ms,
                             stop_exits=a.stop_exit)
    return code


if __name__ == "__main__":
    sys.exit(main())
