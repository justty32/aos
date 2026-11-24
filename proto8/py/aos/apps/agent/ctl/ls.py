# aos/apps/agent/ctl/ls.py - 列出 daemon 表上的 proc 與狀態。
import datetime
import json
import os
import time
from aos import comm
from aos import daemon_ctl as dc
from aos import flags as aos_flags
from aos import ws as aos_ws
from aos.agentlib import cooldown
from aos.comm import walk
from ..common import PROG, bad_args, Agent, daemon_path, parse, table
from ..hints import label, queued
from .shared import query_opt


# ---------------------------------------------------------------- 子命令：查表類＋說話（步 4）

HELP = """aos-agent ctl ls - list every proc on the daemon table

usage: aos-agent [--daemon D] ctl ls [-j] [-l] [--deep] [--timeout-s S]

flags:
  -j, --json   print one JSON array instead of TAB-separated rows
  -l, --long   add the health columns QUEUE RESTARTS COOLDOWN LAST ERROR to each row
  --deep       also list the tables below: rows whose stack is a daemon (has procs_state.json)
  --timeout-s S  seconds to wait for AOS_KERNEL's answer about the table (default 3)
  -h, --help   show this help

Rows: NAME STATE WORKSPACE QUEUED REASON. An empty table prints nothing.
With -l each row also has: QUEUE (letters in queue/new/), RESTARTS (failures in a row,
from the stack's cooldown.json), COOLDOWN ("until HH:MM (N)" local time, "due (N)" when
it has passed, "-" none), LAST ERROR (cooldown code and reason, or the cooldown code and the
lower layer's error when the cooldown records one, else the table reason).
--json rows always carry auto_restart, queue, cooldown and busy (think, act, cli or null);
cooldown also has retry and error when the stack's cooldown.json has them.
--deep walks breadth first (at most 5 levels and 500 procs; a table that cannot be read is a
warning on stderr) and prints PATH STATE PID STAGE QUEUED LAST-ACTIVE REASON (then the -l
columns): PATH = parent/child names down the tree; PID = the row's pid and "alive", "dead",
"exited" (a zombie) or "reused" (another process now has that pid), "-" without one; STAGE =
the first line of the stack's stage.txt (agent-fsm), else busy (cli for eca), else "-";
LAST-ACTIVE = newest mtime of the stack folder and its direct files, local "MM-DD HH:MM".
--deep --json rows also carry path, depth, table (the daemon stack of their table), pid,
pid_state, stage and last_active (UTC ISO or null).
With $AOS_KERNEL set (and no --daemon) it first asks AOS_KERNEL where the table is (a
procs_state_path letter) and reads that file; no answer within --timeout-s = KernelFailed
(AOS_DAEMON is not read instead).
exit codes: 0 listed; 1 error (DaemonMissing, KernelFailed...).
more: proto8/py/aos/apps/agent/README.md
"""

ERR_W = 60                                      # -l 的 LAST ERROR 截到幾個字


# ---------------------------------------------------------------- 看狀況（11-10 two-machines：aos-image status 作廢，改加在 ls 上）

def new_count(a):
    """queue/new/ 裡還沒收的信（. 開頭的不算）；stack 沒 queue/＝None（跟 queued 同一個判法）。"""
    if not os.path.isdir(os.path.join(a.stack, "queue")):
        return None
    return len(aos_ws.names(a.stack, "new"))


def cooling(a):
    """cooldown.json → None 或 {failures, until, code, reason, dropped, state}，檔裡有選配的 retry、error 就照帶（cooldown-1118）；
    讀寫格式只經 py/cooldown。"""
    st, rec = cooldown.state(a.stack)
    if rec is None:
        return None
    out = {"failures": rec["failures"], "until": rec["until"], "code": rec.get("code"),
           "reason": rec.get("reason"), "dropped": rec["dropped"], "state": st}
    out.update({k: rec[k] for k in ("retry", "error") if k in rec})
    return out


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
        low = c.get("error")                    # 下層的原話比 fsm 那句「aos-llm recv exited 1」有用：有就接在代號後面
        said = "%s %s" % (low["code"], low.get("msg", "")) if low else c["reason"] or ""
        err = one_line(" ".join(x for x in (c["code"] or "", said) if x))
    return ["-" if q is None else str(q), str(c["failures"] if c else 0), cd, clip(err) if err else "-"]


# ---------------------------------------------------------------- --deep（11-24）：整棵樹，每列多 pid 活不活、stage、最後活動

def _proc_stat(pid):
    """/proc/pid/stat 的（狀態字母, starttime）；讀不到丟 OSError／ValueError／IndexError。"""
    with open("/proc/%d/stat" % pid, encoding="utf-8") as fh:
        text = fh.read()
    fields = text[text.rindex(")") + 1:].split()
    return fields[0], int(fields[19])


def pid_state(row):
    """表上那列的 pid → (pid 或 None, alive／dead／exited／reused／unknown／None)。started_at_ticks 有記才比對。"""
    pid = row.get("pid")
    if type(pid) is not int or pid <= 0:
        return None, None
    try:
        letter, ticks = _proc_stat(pid)
    except FileNotFoundError:
        return pid, "dead"
    except (OSError, ValueError, IndexError):
        return pid, "unknown"
    want = row.get("started_at_ticks")
    if type(want) is int and want != ticks:
        return pid, "reused"
    return pid, "exited" if letter in ("Z", "X") else "alive"


def stage_of(a):
    """stage.txt 第一行（agent-fsm）；沒有＝busy（eca 的 cli）；都沒有＝None。"""
    text = (aos_ws.read(os.path.join(a.stack, "stage.txt"), "") or "").strip()
    return text.splitlines()[0].strip() if text else busy(a)


def last_active(a):
    """stack 本身與直接底下檔案的最新 mtime（epoch 秒；跟 aos-daemon-ctl prune 同一套）；讀不到＝None。"""
    try:
        return dc.last_change(a.stack)
    except dc.Fail:
        return None


def deep_rows():
    """照 aos.comm.walk 往下走：頂層＝這次讀的表（照 --daemon／AOS_DAEMON／AOS_KERNEL），下層＝stack 有 procs_state.json 的列的表。"""
    def list_table(d):
        if d is None:
            got = table()
        else:
            try:
                got = {n: r for n, r in dc.rows(os.path.realpath(d)).items() if isinstance(r, dict)}
            except dc.Fail as e:
                raise comm.Fail(e.code, str(e)) from None
        return [dict(r, name=n) for n, r in got.items()]
    top = daemon_path()
    got = walk.walk(list_table, deep=True, top=top)
    for s in got["skipped"]:
        aos_flags.warn(PROG, "could not list the table %s: %s %s" % (s["table"], s["code"], s["reason"]))
    if got["truncated"]:
        aos_flags.warn(PROG, "the tree is bigger than %d levels or %d procs; the rest is not listed"
                       % (walk.MAX_DEPTH, walk.MAX_PROCS))
    return got["rows"]


def deep_cmd(opts):
    rows = deep_rows()
    out = []
    for r in rows:
        name = r["name"]
        row = {k: v for k, v in r.items() if k not in ("name", "path", "depth", "table")}
        a = Agent(name, row)
        pid, alive = pid_state(row)
        out.append((r, a, pid, alive, stage_of(a), last_active(a)))
    if opts.get("json"):
        def iso(t):
            return None if t is None else datetime.datetime.fromtimestamp(t, datetime.timezone.utc).isoformat()
        print(json.dumps([dict(name=a.name, path=r["path"], depth=r["depth"], table=r["table"], state=label(a),
                               phase=a.phase, ws=a.row.get("ws") or "", stack=a.stack, queued=queued(a),
                               reason=a.reason, auto_restart=a.row.get("auto_restart") is True, queue=new_count(a),
                               cooldown=cooling(a), busy=busy(a), pid=pid, pid_state=alive, stage=st, last_active=iso(t))
                          for r, a, pid, alive, st, t in out], ensure_ascii=False))
        return
    for r, a, pid, alive, st, t in out:
        q = queued(a)
        cols = [r["path"], label(a), "-" if pid is None else "%d %s" % (pid, alive), one_line(st) if st else "-",
                "-" if q is None else str(q), "-" if t is None else time.strftime("%m-%d %H:%M", time.localtime(t)),
                one_line(a.reason) if a.reason else "-"]
        if opts.get("long"):
            cols += long_cols(a)
        print("\t".join(cols))


def cmd(argv):
    opts, rest = parse(argv, {"--timeout-s": "timeout_s"}, {"--json": "json", "--long": "long", "--deep": "deep"},
                       help=HELP, short={"-j": "--json", "-l": "--long"})
    if rest:
        raise bad_args(HELP, "ls takes no arguments: %s" % rest[0])
    query_opt(opts, HELP)
    if opts.get("deep"):
        return deep_cmd(opts)
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
