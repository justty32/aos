# aos_agent/ctl/ls.py - 列出 daemon 表上的 proc 與狀態。
import json
import os
import time
import aos_ws
from agent import cooldown
from ..common import bad_args, Agent, parse, table
from ..hints import label, queued


# ---------------------------------------------------------------- 子命令：查表類＋說話（步 4）

HELP = """aos-agent ctl ls - list every proc on the daemon table

usage: aos-agent [--daemon D] ctl ls [-j] [-l]

flags:
  -j, --json   print one JSON array instead of TAB-separated rows
  -l, --long   add the health columns QUEUE RESTARTS COOLDOWN LAST ERROR to each row
  -h, --help   show this help

Rows: NAME STATE WORKSPACE QUEUED REASON. An empty table prints nothing.
With -l each row also has: QUEUE (letters in queue/new/), RESTARTS (failures in a row,
from the stack's cooldown.json), COOLDOWN ("until HH:MM (N)" local time, "due (N)" when
it has passed, "-" none), LAST ERROR (cooldown code and reason, else the table reason).
--json rows always carry auto_restart, queue, cooldown and busy (think, act, cli or null).
exit codes: 0 listed; 1 error (DaemonMissing...).
more: proto8/cmd/aos-agent/README.md
"""

ERR_W = 60                                      # -l 的 LAST ERROR 截到幾個字


# ---------------------------------------------------------------- 看狀況（11-10 two-machines：aos-image status 作廢，改加在 ls 上）

def new_count(a):
    """queue/new/ 裡還沒收的信（. 開頭的不算）；stack 沒 queue/＝None（跟 queued 同一個判法）。"""
    if not os.path.isdir(os.path.join(a.stack, "queue")):
        return None
    return len(aos_ws.names(a.stack, "new"))


def cooling(a):
    """cooldown.json → None 或 {failures, until, code, reason, dropped, state}；讀寫格式只經 lib/agent/cooldown。"""
    st, rec = cooldown.state(a.stack)
    if rec is None:
        return None
    return {"failures": rec["failures"], "until": rec["until"], "code": rec.get("code"),
            "reason": rec.get("reason"), "dropped": rec["dropped"], "state": st}


def busy(a):
    """在忙什麼：think/pending.txt 在＝think（fsm 等腦回信）；stage.txt 是 act＝act；eca 小格（stack 本身或 tools/<名>/）有 busy.txt＝cli。"""
    s = a.stack
    if os.path.exists(os.path.join(s, "think", "pending.txt")):
        return "think"
    if (aos_ws.read(os.path.join(s, "stage.txt"), "") or "").strip() == "act":
        return "act"
    if os.path.exists(os.path.join(s, "busy.txt")):
        return "cli"
    try:
        tools = sorted(os.listdir(os.path.join(s, "tools")))
    except OSError:
        tools = []
    if any(os.path.exists(os.path.join(s, "tools", t, "busy.txt")) for t in tools if not t.startswith(".")):
        return "cli"
    return None


def one_line(s):
    return " ".join(str(s).split())


def clip(s, n=ERR_W):
    return s if len(s) <= n else s[:n - 3] + "..."


def long_cols(a):
    """-l 多的四欄：QUEUE RESTARTS COOLDOWN LAST-ERROR。"""
    q, c = new_count(a), cooling(a)
    if c is None:
        cd, err = "-", (one_line(a.reason) if a.reason else "")
    else:
        if c["state"] == "cooling":
            cd = "until %s (%d)" % (time.strftime("%H:%M", time.localtime(cooldown.parse(c["until"]))), c["failures"])
        else:
            cd = "due (%d)" % c["failures"]
        err = one_line(" ".join(x for x in (c["code"] or "", c["reason"] or "") if x))
    return ["-" if q is None else str(q), str(c["failures"] if c else 0), cd, clip(err) if err else "-"]


def cmd(argv):
    opts, rest = parse(argv, {}, {"--json": "json", "--long": "long"}, help=HELP,
                       short={"-j": "--json", "-l": "--long"})
    if rest:
        raise bad_args(HELP, "ls takes no arguments: %s" % rest[0])
    rows = [Agent(n, r) for n, r in table().items()]
    if opts.get("json"):
        print(json.dumps([dict(name=a.name, state=label(a), phase=a.phase, ws=a.row.get("ws") or "", stack=a.stack,
                               queued=queued(a), reason=a.reason, auto_restart=a.row.get("auto_restart") is True,
                               queue=new_count(a), cooldown=cooling(a), busy=busy(a)) for a in rows],
                         ensure_ascii=False))
        return
    for a in rows:
        q = queued(a)
        cols = [a.name, label(a), a.row.get("ws") or "-", "-" if q is None else str(q),
                " ".join(str(a.reason).splitlines()) if a.reason else "-"]
        if opts.get("long"):
            cols += long_cols(a)
        print("\t".join(cols))
