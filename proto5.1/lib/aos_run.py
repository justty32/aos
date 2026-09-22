#!/usr/bin/env python3
"""aos-run：完成後隔固定時間，再用 aos_exec 跑同一目標；沒有家目錄。"""
from contextlib import contextmanager
import argparse
import fcntl
import os
import signal
import sys
import time

import aos_exec

__all__ = ["main", "parser"]


def parser():
    """aos-run 的唯一命令列入口。"""
    ap = argparse.ArgumentParser(prog="aos-run", description="反覆執行同一個目標")
    ap.add_argument("target", nargs="?", default=".")
    ap.add_argument("--interval-ms", type=int, default=1000)
    ap.add_argument("--timeout-ms", type=int, default=0)
    ap.add_argument("--max-runs", type=int, default=0)
    ap.add_argument("--stop-exit", type=int, action="append", default=[])
    ap.add_argument("--status-fd", type=int)
    return ap


def _sleep(seconds, stopped):
    until = time.monotonic() + seconds
    while not stopped() and time.monotonic() < until:
        time.sleep(min(0.05, max(0, until - time.monotonic())))


@contextmanager
def _target_lock(target, stopped):
    """kernel 預建的 sidecar；只有存在時才用，普通 target 不建任何檔。"""
    try:
        f = open(os.path.abspath(target) + ".lock", "rb", buffering=0)
    except FileNotFoundError:
        yield True
        return
    with f:
        while not stopped():
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                f.seek(0)
                if f.read(1) != b"Y":
                    break
                # kernel 請求讓位：本次已跑完，停在兩格之間，讓它有穩定的換槽窗口。
                fcntl.flock(f, fcntl.LOCK_UN)
                _sleep(0.05, stopped)
            except BlockingIOError:
                _sleep(0.05, stopped)
        if stopped():
            yield False
        else:
            try:
                yield True
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)


def main(argv=None):
    ap = parser()
    a = ap.parse_args(argv)
    if any(value < 0 for value in (a.interval_ms, a.timeout_ms, a.max_runs)):
        ap.error("FieldTypeMismatch: interval-ms／timeout-ms／max-runs 必須是非負整數")
    if any(code < 0 or code > 255 for code in a.stop_exit):
        ap.error("FieldTypeMismatch: stop-exit 必須在 0～255")
    if a.status_fd is not None:
        try:
            if a.status_fd < 0 or fcntl.fcntl(a.status_fd, fcntl.F_GETFL) & os.O_ACCMODE == os.O_RDONLY:
                raise OSError("不是可寫的 fd")
        except (OSError, ValueError) as e:
            ap.error("FieldTypeMismatch: status-fd 不可用：%s" % e)

    stopped = [False]
    active = [None]
    status_fd = [a.status_fd]

    def emit(line):
        if status_fd[0] is not None:
            try:
                os.write(status_fd[0], (line + "\n").encode("ascii"))
            except OSError:
                status_fd[0] = None       # 觀察者離開，不讓 broken pipe 留下子程式

    def stop(signum, frame):
        if not stopped[0]:
            stopped[0] = True
            if active[0] is not None:
                aos_exec.terminate(active[0])

    def spawned(p):
        active[0] = p
        if p is not None and stopped[0]:
            aos_exec.terminate(p)

    previous = {sig: signal.signal(sig, stop) for sig in (signal.SIGTERM, signal.SIGINT)}
    reason, result, runs = "signal", 0, 0
    try:
        emit("ready")
        while not stopped[0]:
            with _target_lock(a.target, lambda: stopped[0]) as acquired:
                if not acquired or stopped[0]:
                    break
                runs += 1
                emit("start #%d" % runs)
                code, kind = aos_exec.run_target(a.target, timeout_ms=a.timeout_ms, on_spawn=spawned)
                if kind == aos_exec.AOS:
                    code = aos_exec.EXIT_AOS
                emit("done #%d exit=%d kind=%s" % (runs, code, kind))
            if stopped[0]:
                break
            if kind == aos_exec.USAGE:
                reason, result = "usage", 2
                break
            if code in a.stop_exit:
                reason = "stop-exit"
                break
            if a.max_runs and runs >= a.max_runs:
                reason = "max-runs"
                break
            _sleep(a.interval_ms / 1000, lambda: stopped[0])
        emit("stop " + reason)
    except OSError as e:
        sys.stderr.write("aos-run: ReadFailed: %s\n" % " ".join(str(e).split()))
        emit("stop usage")
        result = 2
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    return result


if __name__ == "__main__":
    sys.exit(main())
