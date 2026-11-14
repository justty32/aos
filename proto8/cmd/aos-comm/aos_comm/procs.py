# aos_comm/procs.py - aos-comm 問 daemon 表的那幾件事：誰的 stack（aos-agent ctl where）、列一張表（aos-agent ctl ls --json）、一列的機器事實（phase、busy）。
# 只叫 aos-agent 命令列、不讀它的內部；設了 AOS_KERNEL 而沒給 --daemon 時 aos-agent 自己先問 kernel（02 §2.5「不繞過」）。
import json
import os
import re
import subprocess

from comm import Fail

TIMEOUT_S = 30
ERR_RE = re.compile(r"aos-[a-z-]+: error: ([A-Z][A-Za-z]+) (.*)\Z")


def _agent(args, daemon=None):
    """aos-agent [--daemon D] args…；回 stdout。退出碼不是 0＝它最後一行錯誤行的代號與原因當我的錯（沒那行＝CommandFailed）。"""
    argv = ["aos-agent"] + (["--daemon", daemon] if daemon else []) + list(args)
    try:
        p = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=TIMEOUT_S)
    except OSError as e:
        raise Fail("LaunchFailed", "cannot run aos-agent (put it on PATH with proto8/install.sh): %s" % (e.strerror or e))
    except subprocess.TimeoutExpired:
        raise Fail("CommandFailed", "aos-agent %s took over %d s" % (" ".join(args[:2]), TIMEOUT_S))
    if p.returncode != 0:
        mine = [m for m in map(ERR_RE.match, p.stderr.splitlines()) if m]
        if mine:
            raise Fail(mine[-1].group(1), mine[-1].group(2))
        raise Fail("CommandFailed", "aos-agent %s exited %d" % (" ".join(args[:2]), p.returncode))
    return p.stdout


def stack_of(name, daemon=None):
    """名字 → 它的 stack 絕對路徑（aos-agent ctl where NAME 印的那一行）。"""
    out = _agent(["ctl", "where", "--", name] if name.startswith("-") else ["ctl", "where", name], daemon).strip()
    if not out or "\n" in out:
        raise Fail("CommandFailed", "aos-agent ctl where %s printed no single path" % name)
    return out


def table(daemon=None):
    """一張 daemon 表：aos-agent ctl ls --json 的列（每列至少 name、stack、phase、busy）。"""
    out = _agent(["ctl", "ls", "--json"], daemon)
    try:
        rows = json.loads(out)
    except ValueError:
        rows = None
    if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
        raise Fail("CommandFailed", "aos-agent ctl ls --json printed no JSON array of rows")
    return rows


def live_of(row):
    """表上一列 → 布告欄要併的機器事實 {phase, busy}（沒有那列＝None）。"""
    if not isinstance(row, dict):
        return None
    return {"phase": row.get("phase"), "busy": row.get("busy")}


def row_for(daemon=None, name=None, stack=None):
    """在表上找那一列（照名字，或照 stack 真實路徑）；表列不了、找不到＝None（不併、不報錯）。"""
    try:
        rows = table(daemon)
    except Fail:
        return None
    real = os.path.realpath(stack) if stack else None
    for r in rows:
        if name is not None and r.get("name") == name:
            return r
        if real and isinstance(r.get("stack"), str) and os.path.realpath(r["stack"]) == real:
            return r
    return None
