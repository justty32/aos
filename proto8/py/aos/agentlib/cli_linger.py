# cli_linger - eca 停下時由 tmux 計時延後關畫面，起來撤單，到期核 token、畫面與本機 loop 身分。
import json
import os
from pathlib import Path
import secrets
import shlex
import signal
import sys
import time

from aos.agentlib import cli_cell

ORDER = "screen_close.json"
KINDS = ("claude", "codex")
ENTRY = str(Path(__file__).resolve().parents[2] / "tools/agent/screen_linger/_entry")


def warn(text):
    try:
        sys.stderr.write("screen_linger: warning: %s\n" % " ".join(str(text).splitlines()))
    except BrokenPipeError:
        pass


def read(path):
    try:
        doc = json.loads(Path(path).read_text())
        return doc if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        return {}


def put(cell, doc):
    path = Path(cell.file(ORDER))
    tmp = path.with_name(".%s.%s" % (ORDER, secrets.token_hex(8)))
    tmp.write_text(json.dumps(doc) + "\n")
    os.replace(tmp, path)


def drop(cell, token=None):
    if token is not None and read(cell.file(ORDER)).get("token") != token:
        return
    try:
        os.unlink(cell.file(ORDER))
    except FileNotFoundError:
        pass


def delay_s(cell):
    try:
        tool = cell.read("tool.txt")
        if not tool:
            raise ValueError("tool.txt is missing")
        cfg = json.loads((Path(cell.path) / tool / "cli.json").read_text())
        value = cfg.get("screen_close_after_s", 600)
        if not (isinstance(value, int) and not isinstance(value, bool) and value >= 0):
            raise ValueError("screen_close_after_s must be a non-negative integer")
        return value
    except (OSError, ValueError, AttributeError) as error:
        warn("cannot read screen_close_after_s; using 600 s: %s" % error)
        return 600


def loop_id(stack):
    doc = read(Path(stack) / "state.json")
    return {key: doc.get(key) for key in ("pid", "started_at_ticks", "boot_id")}


def loop_alive(stack):
    """回 True／False／None；None 是 pid 在但身分資料不足，保守留畫面。"""
    identity = loop_id(stack)
    pid = identity["pid"]
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return False
    try:
        text = Path("/proc/%d/stat" % pid).read_text()
        fields = text[text.rindex(")") + 1:].split()
        if fields[0] in ("Z", "X"):
            return False
        boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        if (not isinstance(identity["started_at_ticks"], int) or isinstance(identity["started_at_ticks"], bool)
                or not isinstance(identity["boot_id"], str) or not identity["boot_id"]):
            return None
        return int(fields[19]) == identity["started_at_ticks"] and boot == identity["boot_id"]
    except FileNotFoundError:
        return False
    except (OSError, ValueError, IndexError):
        return None


def screen_id(cell):
    if not cell.alive():
        return None
    result = cell.tmux("list-sessions", "-F", "#{session_name} #{pid} #{session_created}")
    try:
        _, pid, created = next(line.split() for line in result.stdout.splitlines() if line.startswith("cli "))
        return {"pid": int(pid), "created": int(created)} if result.returncode == 0 else None
    except (ValueError, StopIteration):
        return None


def schedule(cell, stack, kind, token, seconds):
    command = shlex.join([sys.executable, ENTRY, "reap", os.path.abspath(stack), kind, token])
    command += " </dev/null >/dev/null 2>&1 &"
    try:
        result = cell.tmux("run-shell", "-b", "-d", str(seconds), command)
        if result.returncode:
            warn("cannot schedule screen close: %s" % (result.stderr.strip() or "tmux run-shell failed"))
    except OSError as error:
        warn("cannot schedule screen close: %s" % error)


def cancel(stack):
    for kind in KINDS:
        drop(cli_cell.Cell(os.path.join(stack, kind), make=False))


def arm(stack):
    for kind in KINDS:
        cell = cli_cell.Cell(os.path.join(stack, kind), make=False)
        screen = screen_id(cell)
        if screen is None:
            drop(cell)
            continue
        seconds = delay_s(cell)
        token = secrets.token_hex(16)
        now = time.time()
        put(cell, {"token": token, "by": "after_stop", "down_at": now, "due_at": now + seconds,
                   "delay_s": seconds, "loop": loop_id(stack), "screen": screen, "retries": 0})
        if seconds == 0:
            reap(stack, kind, token)
        else:
            schedule(cell, stack, kind, token, seconds)


def obsolete(cell, stack, doc):
    if screen_id(cell) != doc.get("screen"):
        return True
    alive = loop_alive(stack)
    return alive is True and loop_id(stack) != doc.get("loop")


def reap(stack, kind, token):
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    if kind not in KINDS:
        raise ValueError("kind must be claude or codex")
    cell = cli_cell.Cell(os.path.join(stack, kind), make=False)
    doc = read(cell.file(ORDER))
    if doc.get("token") != token:
        return
    stale = obsolete(cell, stack, doc)
    lock, acquired = cell.lock()
    with lock:
        if stale:
            if acquired:
                drop(cell, token)
            return
        doc = read(cell.file(ORDER))
        if doc.get("token") != token:
            return
        if not acquired:
            if obsolete(cell, stack, doc):
                return
            retries = doc.get("retries", 0)
            if retries < 10 and read(cell.file(ORDER)).get("token") == token:
                put(cell, dict(doc, retries=retries + 1))
                schedule(cell, stack, kind, token, 30)
            return
        if obsolete(cell, stack, doc):
            drop(cell, token)
            return
        if loop_alive(stack) is None:
            warn("loop pid is present but its identity cannot be verified; screen close order kept")
            return
        cli_cell.close(cell)
        drop(cell, token)
