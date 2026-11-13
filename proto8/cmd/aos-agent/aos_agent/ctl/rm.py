# aos_agent/ctl/rm.py - 拔掉 agent（預設留 stack；--purge 確認後才刪，並保護不能刪除的 stack 路徑）。
import os
import aos_flags
from .. import PROG
import shutil
from ..common import bad_args, daemon_path, find, parse, row_named, table
from .shared import ctl_wait, need_table, timeout_opt
from ..decl import close_screen_if_any


HELP = """aos-agent ctl rm - detach one agent; its stack is kept unless --purge

usage: aos-agent [--daemon D] ctl rm [--purge [-y]] [--no-wait] [--timeout-s S] NAME

NAME must be spelled out ($AOS_AGENT is not used here). Closes its screen first (answering
= SessionBad, nothing removed) and detaches it from the daemon. A workspace that is gone
does not block it (one warning line; the screen is closed from the stack). Its stack
(history, queue, overlays) stays where it is, the same as aos-daemon-ctl rm; aos-agent ctl
add with the same --stack picks it up again.

--purge also deletes the stack. A stack that covers the workspace, the definition, the
daemon, the cwd, home or another listed stack is kept even then. With --purge it asks on a
terminal; -y skips (stderr):
  aos-agent: remove NAME and delete its stack /path/to/stack? [y/N]
Only y / yes goes on; anything else, an empty line or end of input = nothing done (exit 0).
Not on a terminal (a pipe, a script, an agent) it does not ask.

--no-wait (for an agent removing itself): sends the letter and returns at once, without
closing the screen or waiting for the row to go. With --purge, a detached helper deletes the
stack once the row is gone (same protections; if it cannot outlive the agent, the stack stays).

flags:
      --purge         delete the stack too (cannot be undone)
  -y, --yes           with --purge: do not ask
      --no-wait       send it and return; do not wait for it to happen
      --timeout-s S   seconds to wait for the daemon (default 30)
  -h, --help          show this help

exit codes: 0 removed, or "aos-agent: warning: nothing done" after a no; 1 error
  (InstanceMissing, SessionBad, CtlRejected, DaemonMissing...); 130 Ctrl-C at the question.
"""

def cmd(argv):
    opts, rest = parse(argv, {"--timeout-s": "timeout_s"}, {"--yes": "yes", "--purge": "purge", "--no-wait": "no_wait"}, help=HELP, short=("-y",))
    secs = timeout_opt(opts, HELP)
    if len(rest) != 1:
        raise bad_args(HELP, "rm needs the name spelled out (no --target / AOS_AGENT)")
    if opts.get("yes") and not opts.get("purge"):
        raise bad_args(HELP, "-y only goes with --purge (without it nothing is deleted and nothing is asked)")
    need_table()
    a = find(rest[0])
    if opts.get("no_wait"):
        return no_wait(a, opts, secs)
    if not opts.get("purge"):                         # 11-10 晚 cli-sweep Q3（使用者「兩支都留 stack，要刪另外說」）：預設留 stack
        close_screen_if_any(a)
        ctl_wait("rm", {"procs_removed": [a.name]}, lambda _: row_named(a.name) is None, "the daemon has not removed %s yet" % a.name, "CtlRejected", secs=secs)
        print("removed %s; stack %s kept (delete it with aos-agent ctl rm --purge, or by hand)" % (a.name, a.stack))
        return
    others = [r.get("stack") for n, r in table().items() if n != a.name]
    keep = covers(a.stack, [a.row.get("ws"), a.row.get("def"), daemon_path(), os.getcwd(), os.path.expanduser("~")] + others)
    question = ("remove %s (its stack %s is kept)?" if keep else
                "remove %s and delete its stack %s?") % (a.name, a.stack)
    if not aos_flags.confirm(PROG, question, yes=opts.get("yes")):
        aos_flags.warn(PROG, "nothing done")
        return
    close_screen_if_any(a)
    ctl_wait("rm", {"procs_removed": [a.name]}, lambda _: row_named(a.name) is None, "the daemon has not removed %s yet" % a.name, "CtlRejected", secs=secs)
    if keep:                                          # 11-04 夜邊緣實測：add --stack . 之後 rm 會連工作區一起刪；stack 蓋住這些的不刪
        print("removed %s; stack %s kept (it is %s or above it)" % (a.name, a.stack, keep))
        return
    shutil.rmtree(a.stack, ignore_errors=True)        # 不封存（使用者 11-02 晚）
    print("removed %s (deleted stack %s)" % (a.name, a.stack))


WAITER = r"""
import os, shutil, sys, time
sys.path[:0] = sys.argv[5:]
import daemon_ctl as dc
d, name, stack, secs = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4])
end = time.monotonic() + secs
while time.monotonic() < end:
    try:
        if name not in dc.rows(d):
            shutil.rmtree(stack, ignore_errors=True)
            break
    except Exception:
        pass
    time.sleep(0.2)
"""


def no_wait(a, opts, secs):
    """11-10 self_ctl：rm 的是自己＝daemon 會連這支一起收掉；寄出就回。--purge＝另起一個脫離的小行程，等那列不在了再刪 stack。"""
    import subprocess
    import sys
    from .shared import send_only
    keep = None
    if opts.get("purge"):
        others = [r.get("stack") for n, r in table().items() if n != a.name]
        keep = covers(a.stack, [a.row.get("ws"), a.row.get("def"), daemon_path(), os.getcwd(), os.path.expanduser("~")] + others)
        if not keep and not aos_flags.confirm(PROG, "remove %s and delete its stack %s?" % (a.name, a.stack), yes=opts.get("yes")):
            aos_flags.warn(PROG, "nothing done")
            return
    send_only({"procs_removed": [a.name]})
    if opts.get("purge") and not keep:
        subprocess.Popen([sys.executable, "-c", WAITER, daemon_path(), a.name, a.stack, str(max(secs, 60))] + [p for p in sys.path if p],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True, close_fds=True)
        print("rm sent; %s leaves the daemon table, and its stack %s is deleted once it is gone" % (a.name, a.stack))
    elif keep:
        print("rm sent; %s leaves the daemon table; stack %s kept (it is %s or above it)" % (a.name, a.stack, keep))
    else:
        print("rm sent; %s leaves the daemon table; stack %s kept (aos-agent ctl add with the same --stack picks it up again)" % (a.name, a.stack))


def covers(stack, paths):
    """stack 是不是 paths 裡某一個、或在它上層（rm 不能刪的）；回那一個或 None。"""
    s = os.path.realpath(stack)
    for p in paths:
        if isinstance(p, str) and p:
            r = os.path.realpath(p)
            if r == s or r.startswith(s.rstrip("/") + "/"):
                return p
    return None
