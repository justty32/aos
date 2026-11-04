"""aos-exec 底層的「等與砍」：等子行程（逾時／取消）、送訊號給它的 process group 與後代（從 aos_exec_run.py 拆出）。

`_spawn()`（aos_exec_run）逾時就 `terminate()`：快照後代 groups、TERM，GRACE 秒後 KILL；cpu 專用的
`_wait_full()` 只處理一個 pgid、控制回呼不中斷。對外照舊經 aos_exec_run（及 aos_exec）re-export。
"""
import os
import select
import signal
import time

GRACE = 2.0             # 逾時：SIGTERM 之後給整個 process group 這麼久，還在就 SIGKILL


def _pidfd(p):
    """子行程的 pidfd（Linux 5.3＋）：它一結束就可讀，等的人不必睡滿一個 poll。拿不到回 None（改用睡）。
    子行程還沒收屍，pid 不會被別人重用，所以這時開的 pidfd 一定指它。"""
    try:
        return os.pidfd_open(p.pid)
    except (AttributeError, OSError):
        return None


def _nap(fd, pause):
    """睡 pause 秒；有 pidfd 就在子行程結束那一刻醒（09-24 tick-gap：以前平均多睡半個 poll_ms）。"""
    if fd is None:
        time.sleep(pause)
        return
    try:
        select.select([fd], [], [], pause)
    except (OSError, ValueError):
        time.sleep(pause)


def _wait_full(p, timeout_ms, details):
    """cpu 專用等待：取消／逾時都只處理一個 pgid，控制回呼不中斷。"""
    fd = _pidfd(p)
    try:
        _wait_loop(p, timeout_ms, details, fd)
    finally:
        if fd is not None:
            os.close(fd)


def _wait_loop(p, timeout_ms, details, fd):
    deadline = time.monotonic() + timeout_ms / 1000 if timeout_ms else None
    until = None
    while True:
        alive = p.poll() is None
        if until is None and not alive:
            return
        cancel = bool(details["on_poll"](p)) if details["on_poll"] else False
        now = time.monotonic()
        if cancel and p.poll() is None:
            details["stopped"] = True
        if until is None and p.poll() is None:
            expired = deadline is not None and now >= deadline
            if cancel or expired:
                details["timed_out"] = expired
                _signal_groups({p.pid}, signal.SIGTERM)
                until = now + GRACE
        if until is not None:
            if not _group_exists(p.pid):
                p.wait()
                return
            if now >= until:
                _signal_groups({p.pid}, signal.SIGKILL)
                p.wait()
                return
        pause = details["poll"]
        limit = until if until is not None else deadline
        if limit is not None:
            pause = min(pause, max(0, limit - time.monotonic()))
        _nap(fd if until is None else None, pause)


def terminate(p):
    """第一次取消：快照後代 groups、TERM；_spawn 在兩秒期限後 KILL 並收屍。

    Linux /proc 補上 nested run_inst 的 setsid 邊界；其他 POSIX 至少處理原 group。
    不追捕終止開始後才新生或已脫離親子樹的 daemon。
    """
    if getattr(p, "_aos_stop", None):
        return
    groups = {p.pid}
    parents = {}
    try:
        for name in os.listdir("/proc"):
            if not name.isdigit():
                continue
            try:
                with open("/proc/%s/stat" % name) as f:
                    fields = f.read().rsplit(")", 1)[1].split()
                parents[int(name)] = (int(fields[1]), int(fields[2]))
            except (OSError, ValueError, IndexError):
                continue
    except OSError:
        pass
    descendants = {p.pid}
    while True:
        added = {pid for pid, (parent, _) in parents.items() if parent in descendants} - descendants
        if not added:
            break
        descendants.update(added)
    groups.update(parents[pid][1] for pid in descendants if pid in parents)
    groups.discard(os.getpgrp())
    p._aos_stop = (time.monotonic() + GRACE, groups)
    _signal_groups(groups, signal.SIGTERM)


def _signal_groups(groups, sig):
    for group in groups:
        try:
            os.killpg(group, sig)
        except ProcessLookupError:
            pass


def _group_exists(group):
    try:
        os.killpg(group, 0)
        return True
    except ProcessLookupError:
        return False

