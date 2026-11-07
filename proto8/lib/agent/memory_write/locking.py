"""Acquire knowledge directory locks and inspect descendant locks through aos-lock."""
import contextlib
import datetime
import fcntl
import json
import os
import signal
import subprocess
import time

import tool_io


def run_lock(args, release=False):
    try:
        # Defer termination until the short-lived command has a known result.
        old = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM, signal.SIGINT})
        try:
            env = dict(os.environ)
            env.pop("AOS_TICK", None)
            env.pop("AOS_TICK_INTERVAL", None)
            child = subprocess.Popen(["aos-lock"] + args, stdin=subprocess.DEVNULL,
                                     stdout=subprocess.PIPE, env=env)
            out, _ = child.communicate(timeout=5)
            return child.returncode, out
        except subprocess.TimeoutExpired:
            child.kill()
            child.communicate()
            if release:
                tool_io.warn("aos-lock release did not finish within 5 seconds")
                return None, b""
            tool_io.die("LockFailed", "aos-lock did not finish within 5 seconds")
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK, old)
    except OSError as error:
        if release:
            tool_io.warn("cannot run aos-lock release: %s" % error)
            return None, b""
        tool_io.die("LaunchFailed", "cannot run aos-lock: %s" % error)


def holder(folder):
    code, out = run_lock(["show", folder + "/"])
    if code == 10:
        return None
    if code:
        tool_io.die("LockFailed", "aos-lock show exited %d for %s" % (code, folder))
    try:
        value = json.loads(out)
        if not isinstance(value, dict):
            raise ValueError("holder is not an object")
        return value
    except ValueError as error:
        tool_io.die("LockFailed", "invalid aos-lock show result: %s" % error)


def live(folder, value):
    lease = value.get("lease_ticks")
    if lease is not None:
        try:
            at = datetime.datetime.fromisoformat(value["acquired_at"].replace("Z", "+00:00"))
            if time.time() >= at.timestamp() + lease:
                return False
        except (KeyError, TypeError, ValueError):
            tool_io.die("LockFailed", "invalid lease in aos-lock show result")
    if value.get("flock") is True:
        try:
            with open(os.path.join(folder, ".lock", "holder.flock"), "rb") as stream:
                try:
                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    return False
                except BlockingIOError:
                    return True
        except FileNotFoundError:
            return False
    return True


def check_descendants(folder):
    def failed(error):
        tool_io.die("ReadFailed", "cannot scan subtree: %s" % error)
    for current, dirs, _ in os.walk(folder, followlinks=False, onerror=failed):
        # The caller holds this node's lock; only deeper locks can conflict.
        if current != folder and ".lock" in dirs:
            value = holder(current)
            if value is not None and live(current, value):
                tool_io.die("LockFailed", "%s held by %s (%s); try again later" %
                            (current, value.get("holder", "unknown"), value.get("note", "no note")))
        dirs[:] = [d for d in dirs if not d.startswith(".") and not os.path.islink(os.path.join(current, d))]


class HeldLock:
    def __init__(self, folder):
        self.folder = folder
        self.released = False

    def release(self, folder):
        self.released = True
        code, _ = run_lock(["release", folder + "/"], release=True)
        if code:
            tool_io.warn("aos-lock release exited %d for %s" % (code, folder))


@contextlib.contextmanager
def with_lock(folder, note):
    folder = os.path.realpath(folder)
    if not os.path.isdir(folder):
        tool_io.die("NodeMissing", "node was removed while waiting for its lock")
    if not os.access(folder, os.W_OK | os.X_OK):
        tool_io.die("WriteFailed", "%s: permission denied (this folder is read-only for you; write elsewhere or report)" % folder)
    # Keep signals blocked through acquired-state registration so finally can release.
    old = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM, signal.SIGINT})
    acquired = False
    held = HeldLock(folder)
    try:
        code, _ = run_lock(["acquire", "--wait-ms", "3000", "--lease-ticks", "10",
                            "--note", note, folder + "/"])
        acquired = code == 0
        signal.pthread_sigmask(signal.SIG_SETMASK, old)
        if code:
            if not os.path.isdir(folder):
                tool_io.die("NodeMissing", "node was removed while waiting for its lock")
            value = holder(folder) if code == 10 else None
            tool_io.die("LockFailed", "%s held by %s (%s); try again later (aos-lock acquire exited %d)" %
                        (folder, (value or {}).get("holder", "unknown"),
                         (value or {}).get("note", "no note"), code))
        yield held
    finally:
        signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM, signal.SIGINT})
        try:
            if acquired and not held.released:
                held.release(folder)
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK, old)
