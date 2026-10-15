"""子程序的行程群組：等結束、整群送訊號、收屍。loop 收 aos_inst、daemon 收 loop 都用這組。純標準庫。

起的人把子程序起在新 session（`start_new_session=True`），群組號碼＝它的 pid；收屍前整群補 SIGKILL 清孫程式，
群組號碼收屍前不會被拿走。
"""
import os
import signal
import time

__all__ = ["kill", "reap", "stop"]


def _exited(pid, timeout):
    """等 pid 結束、不收屍，最多 timeout 秒（None＝不限），回結束了沒。"""
    end = None if timeout is None else time.monotonic() + timeout
    while os.waitid(os.P_PID, pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is None:
        if end is not None and time.monotonic() >= end:
            return False
        time.sleep(0.01)
    return True


def _killpg(pid, sig):
    try:
        os.killpg(pid, sig)
    except (ProcessLookupError, PermissionError):
        pass


def reap(proc):
    """proc 已經結束（還沒收屍）：對整群補 SIGKILL 清掉孫程式，再收屍，回 returncode。群組號碼收屍前不會被拿走。"""
    _killpg(proc.pid, signal.SIGKILL)
    return proc.wait()


def stop(proc):
    """整群 SIGTERM，等它自己結束（aos_inst 保證過它的 grace_ms 會收掉子程式並結束，C-53 出口保證），收屍，回 returncode。"""
    _killpg(proc.pid, signal.SIGTERM)
    _exited(proc.pid, None)
    return reap(proc)


def kill(proc, grace_ms):
    """整群 SIGTERM，等 grace_ms 還沒結束就整群 SIGKILL，收屍，回 returncode（daemon 收子 loop 用）。"""
    _killpg(proc.pid, signal.SIGTERM)
    _exited(proc.pid, grace_ms / 1000)
    return reap(proc)
