# aos_agent/hints.py - 讀 agent 狀態、queue 數量與接續操作提示。
import aos_ws
import daemon_ctl as dc
import json
import os
from .common import call_dc, daemon_path, row_named


def loop_state(a):
    """子 loop 自己的 state.json（stack 裡 loop.json〔窗上的 procs_loop〕的 state 那格，沒寫＝state.json）→ 物件；讀不到＝{}。"""
    try:
        with open(os.path.join(a.stack, call_dc(dc.names_of, daemon_path())["procs_loop"]), encoding="utf-8") as f:
            name = json.load(f).get("state")
    except (OSError, ValueError, AttributeError):
        name = None
    try:
        with open(os.path.join(a.stack, name if isinstance(name, str) and name else "state.json"), encoding="utf-8") as f:
            st = json.load(f)
    except (OSError, ValueError):
        return {}
    return st if isinstance(st, dict) else {}


def loop_paused(a):
    """表上 running 時讀子窗是否 paused，不靠行程身分。"""
    return loop_state(a).get("phase") == "paused"


def comes_back_paused(a):
    """stopped／sleeping 的那隻起來會不會先暫停（aos-loop：舊 state.json 的 paused 是 true＝起來先暫停）。"""
    return loop_state(a).get("paused") is True


def label(a):
    """狀態（procs § 0 名詞表）：running／paused／stopping／stopped／sleeping。paused＝表上 running、子 loop 的 state.json 是 paused。"""
    if a.phase == "running":
        return "paused" if loop_paused(a) else "running"
    return a.phase or "-"


def queued(a):
    """queue 排幾封（new/＋cur/）；stack 沒 queue/＝None。"""
    if not os.path.isdir(os.path.join(a.stack, "queue")):
        return None
    return len(aos_ws.waiting(a.stack))


# ---------------------------------------------------------------- 誰在跑（搬自 extras/human/bin/aos_human.py）

def _same(a, b):
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def on_table(a):
    """重讀這隻在 daemon 表上的狀態。"""
    row = row_named(a.name)
    if row is not None:
        a.__init__(a.name, row)
    return row is not None and a.phase in ("running", "stopping")


def daemon_held(a):
    """表上留著、行程不在的那一列（stopped 或 sleeping）＝phase；不是＝None。"""
    return a.phase if a.phase in ("stopped", "sleeping") else None


def off_table(a):
    """表上已經沒有這隻（身體退 0 結束、下了表；出錯結束的 daemon 留 stopped＋reason）＝一句怎麼接著用；還在＝None。"""
    if row_named(a.name) is not None:
        return None
    return ("it is no longer on the daemon table (its body exited 0 and left the table; its last output is in %s/%s); aos-agent ctl add with the same name "
            "picks it up again (the stack is kept; some bodies resume where they stopped, others drop that batch, so say it again)"
            % (a.stack, call_dc(dc.names_of, daemon_path())["procs_stderr"]))


def restart_how(d):
    """重起 daemon 的兩種起法（11-05 晚：從 stack 看不出當初是 aos-exec 定義還是直接 AOS_STACK=… aos-daemon，兩種都列）。"""
    return "the way it was started, aos-exec <daemon folder> or AOS_STACK=%s/ aos-daemon <daemon.json>" % d


def run_hint(a):
    gone = off_table(a)
    if gone:
        return gone
    held = daemon_held(a)
    if held == "sleeping":
        return "it is asleep on the daemon (%s is sleeping); wake it: aos-agent ctl wake --target %s (if the daemon itself is down, restarting it wakes %s too: %s)" % (a.name, a.name, a.name, restart_how(daemon_path()))
    if held:
        why = "; reason recorded by the daemon: %s" % a.reason if a.reason else ""
        return "it is stopped on the daemon table (%s is stopped%s); start it: aos-agent ctl start --target %s" % (a.name, why, a.name)
    return "see its error line: %s/%s, or aos-agent ctl state --target %s" % (a.stack, call_dc(dc.names_of, daemon_path())["procs_stderr"], a.name)


def stuck_hint(a, sig):
    if "cur" in aos_ws.where(a.stack, sig):
        return "%s is in queue/cur/ (taken, not answered yet), but nothing is running %s now; %s" % (sig, a.name, run_hint(a))
    return "%s is still in queue/new/, but nothing is running %s now; %s" % (sig, a.name, run_hint(a))
