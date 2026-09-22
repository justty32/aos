#!/usr/bin/env python3
"""aos-run：完成後隔固定時間再跑；可用家裡的 JSON 觀察及控制。"""
import argparse
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import time

import aos_exec

__all__ = ["main", "parser"]


def parser():
    ap = argparse.ArgumentParser(prog="aos-run", description="反覆執行同一個目標")
    ap.add_argument("target", nargs="?", default=".")
    ap.add_argument("--interval-ms", type=int, default=1000)
    ap.add_argument("--timeout-ms", type=int, default=0)
    ap.add_argument("--max-runs", type=int, default=0)
    ap.add_argument("--stop-exit", type=int, action="append", default=[])
    ap.add_argument("--home")
    ap.add_argument("--kill-tree", action="store_true")
    return ap


def _sleep(seconds, stopped):
    until = time.monotonic() + seconds
    while not stopped() and time.monotonic() < until:
        time.sleep(min(0.05, max(0, until - time.monotonic())))


def _write(home, state):
    fd, tmp = tempfile.mkstemp(prefix=".run-", suffix=".tmp", dir=home)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, home / "run.json")
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _control(home):
    try:
        obj = json.loads((home / "ctl.json").read_text(encoding="utf-8"))
        return obj.get("op") if isinstance(obj, dict) else None
    except (OSError, ValueError, UnicodeError):
        return None


def main(argv=None):
    ap = parser()
    a = ap.parse_args(argv)
    if any(value < 0 for value in (a.interval_ms, a.timeout_ms, a.max_runs)):
        ap.error("FieldTypeMismatch: interval-ms／timeout-ms／max-runs 必須是非負整數")
    if any(code < 0 or code > 255 for code in a.stop_exit):
        ap.error("FieldTypeMismatch: stop-exit 必須在 0～255")
    home = Path(a.home).resolve() if a.home is not None else None
    state = dict(pid=os.getpid(), busy=False, target=None, runs=0,
                 last_exit=None, last_kind=None, last_ms=None, held=False)
    signals = [0]
    active = [None]
    terminating = [False]

    def save(**changes):
        state.update(changes)
        if home is not None:
            _write(home, state)

    def cancel(p):
        if a.kill_tree:
            if not terminating[0]:
                terminating[0] = True
                aos_exec.terminate(p)
        elif signals[0] >= 2:
            try:
                os.killpg(p.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass

    def stop(signum, frame):
        signals[0] += 1
        if active[0] is not None:
            cancel(active[0])

    def spawned(p):
        active[0] = p
        if p is not None and signals[0]:
            cancel(p)

    previous = {sig: signal.signal(sig, stop) for sig in (signal.SIGTERM, signal.SIGINT)}
    reason, result = "signal", 0
    try:
        if home is not None:
            home.mkdir(parents=True, exist_ok=True)
            save()
        while not signals[0]:
            op = _control(home) if home is not None else None
            if op == "stop":
                reason = "ctl"
                break
            if op == "hold":
                save(held=True)
                _sleep(a.interval_ms / 1000, lambda: bool(signals[0]))
                continue
            # 保證：尚未讀目標前先 busy/null；exec 選定檔後、load 前再公布絕對路徑。
            save(busy=True, target=None, held=False)
            started = time.monotonic()
            code, kind = aos_exec.run_target(a.target, timeout_ms=a.timeout_ms, on_spawn=spawned,
                                            on_target=lambda path: save(target=path))
            if kind == aos_exec.AOS:
                code = aos_exec.EXIT_AOS
            save(busy=False, runs=state["runs"] + 1, last_exit=code, last_kind=kind,
                 last_ms=round((time.monotonic() - started) * 1000))
            if signals[0]:
                break
            if kind == aos_exec.USAGE:
                reason, result = "usage", 2
                break
            if code in a.stop_exit:
                reason = "stop-exit"
                break
            if a.max_runs and state["runs"] >= a.max_runs:
                reason = "max-runs"
                break
            _sleep(a.interval_ms / 1000, lambda: bool(signals[0]))
    except OSError as e:
        sys.stderr.write("aos-run: ReadFailed: %s\n" % " ".join(str(e).split()))
        result = 2
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    return result


if __name__ == "__main__":
    sys.exit(main())
