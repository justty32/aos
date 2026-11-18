# aos/apps/agent/hints.py - 讀 agent 狀態（含仍活著的 stuck）、queue 數量與接續操作提示。
from aos import flags as aos_flags
from aos import ws as aos_ws
from aos import daemon_ctl as dc
import json
import os
from .common import call_dc, daemon_path, row_named, table_ref


def loop_state(a):
    """子 loop 自己的 state.json（stack 裡 loop.json〔窗上的 procs_loop〕的 state 那格，沒寫＝state.json）→ 物件；讀不到＝{}。"""
    try:
        with open(os.path.join(a.stack, call_dc(dc.names_of, table_ref())["procs_loop"]), encoding="utf-8") as f:
            name = json.load(f).get("state")
    except (OSError, ValueError, AttributeError):
        name = None
    path = os.path.join(a.stack, name if isinstance(name, str) and name else "state.json")
    return aos_flags.read_window("aos-agent", path) or {}


def loop_paused(a):
    """表上 running 時讀子窗是否 paused，不靠行程身分。"""
    return loop_state(a).get("phase") == "paused"


def comes_back_paused(a):
    """stopped／sleeping 的那隻起來會不會先暫停（aos-loop：舊 state.json 的 paused 是 true＝起來先暫停）。"""
    return loop_state(a).get("paused") is True


def label(a):
    """狀態（procs § 0 名詞表）：running／stuck／paused／stopping／stopped／sleeping。paused＝表上 running、子 loop 的 state.json 是 paused。"""
    if a.phase == "running":
        return "paused" if loop_paused(a) else "running"
    return a.phase or "-"


def brain_hint(a):
    """只讀問腦記錄；確認 llm kernel 沒在跑才給提示，任何錯都不影響原本操作。"""
    try:
        from aos.agentlib import cooldown

        if a.phase != "running" or label(a) != "running":
            return None
        try:
            with open(os.path.join(a.stack, "think", "pending.txt"), encoding="utf-8") as f:
                letter = f.readline().strip()
        except FileNotFoundError:
            letter = ""
        if not letter:
            rec = cooldown.read(a.stack)
            if rec and rec.get("code") == "SendFailed":
                reason = rec.get("reason")
                if isinstance(reason, str) and "(llm kernel folder not found)" in reason:
                    return "%s cannot reach its brain: %s; it retries by itself once the folder appears" % (a.name, reason)
            return None
        with open(os.path.join(a.stack, "think", "brain_wait.json"), encoding="utf-8") as f:
            wait = json.load(f)
        if not isinstance(wait, dict) or wait.get("letter") != letter or not isinstance(wait.get("kernel"), str):
            return None
        replies = os.path.join(a.stack, "think", "reply", "new")
        if os.path.isdir(replies) and any(not name.startswith(".") for name in os.listdir(replies)):
            return None
        kernel = wait["kernel"]
        try:
            with open(os.path.join(kernel, "state.json"), encoding="utf-8") as f:
                state = json.load(f)
        except FileNotFoundError:
            why = "no llm daemon there (no state.json)"
        else:
            if not isinstance(state, dict):
                return None
            phase = state.get("phase")
            why = "the llm daemon is not running (state.json phase %s)" % (phase or "?")
            if phase in ("running", "waiting", "stopping"):
                pid = state.get("pid")
                if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
                    why += ", pid gone"
                else:
                    try:
                        os.kill(pid, 0)
                    except ProcessLookupError:
                        why += ", pid gone"
                    except PermissionError:
                        return None
                    else:
                        return None
        return ("%s is waiting for its brain, but the llm kernel at %s is not running (%s); start that llm kernel, "
                "or if AOS_LLM_KERNEL points to the wrong place, add %s again with the right one"
                % (a.name, kernel, why, a.name))
    except Exception:
        return None


def queued(a):
    """queue 排幾封（new/＋cur/）；stack 沒 queue/＝None。"""
    if not os.path.isdir(os.path.join(a.stack, "queue")):
        return None
    return len(aos_ws.waiting(a.stack))


# ---------------------------------------------------------------- 誰在跑（搬自 extras/human/bin/aos_human.py）

def on_table(a):
    """重讀這隻在 daemon 表上的狀態。"""
    row = row_named(a.name)
    if row is not None:
        a.__init__(a.name, row)
    return row is not None and a.phase in ("running", "stuck", "stopping")


def daemon_held(a):
    """表上留著、行程不在的那一列（stopped 或 sleeping）＝phase；不是＝None。"""
    return a.phase if a.phase in ("stopped", "sleeping") else None


def off_table(a):
    """表上沒這隻可能是退 0、被 rm 或 adopt 接回後結束碼不明；已知非 0 留 stopped＋reason。回一句怎麼接著用；還在＝None。"""
    if row_named(a.name) is not None:
        return None
    return ("it is no longer on the daemon table (a body that exits 0 leaves the table; known nonzero exits stay stopped with a reason; removal or an adopted exit with unknown status can also leave it off the table; its last output is in %s/%s); aos-agent ctl add with the same name "
            "picks it up again (the stack is kept; some bodies resume where they stopped, others drop that batch, so say it again)"
            % (a.stack, call_dc(dc.names_of, table_ref())["procs_stderr"]))


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
    return "see its error line: %s/%s, or aos-agent ctl state --target %s" % (a.stack, call_dc(dc.names_of, table_ref())["procs_stderr"], a.name)


def stuck_hint(a, sig):
    if "cur" in aos_ws.where(a.stack, sig):
        return "%s is in queue/cur/ (taken, not answered yet), but nothing is running %s now; %s" % (sig, a.name, run_hint(a))
    return "%s is still in queue/new/, but nothing is running %s now; %s" % (sig, a.name, run_hint(a))
