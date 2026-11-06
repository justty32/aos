# aos_agent/ctl/rm.py - 確認後拔掉 agent 並保護不能刪除的 stack 路徑。
import os
import aos_flags
from .. import PROG
import shutil
from ..common import bad_args, Fail, ctl_wait, daemon_path, find, is_kernel, need_table, parse, row_named, table
from ..decl import close_screen_if_any


HELP = """aos-agent ctl rm - detach one agent and delete its stack

usage: aos-agent [--daemon D] ctl rm [-y] NAME

NAME must be spelled out ($AOS_AGENT is not used here). Closes its screen first (answering
= SessionBad, nothing removed), detaches it from the daemon, then deletes its stack. A stack
that covers the workspace, the definition, the daemon, the cwd, home or another listed
stack is kept. It asks on a terminal; -y skips (stderr):
  aos-agent: remove NAME and delete its stack /path/to/stack? [y/N]
Only y / yes goes on; anything else, an empty line or end of input = nothing done (exit 0).
Not on a terminal (a pipe, a script, an agent) it does not ask.

flags:
  -y, --yes    do not ask
  -h, --help   show this help

exit codes: 0 removed, or "aos-agent: warning: nothing done" after a no; 1 error
  (InstanceMissing, SessionBad, CtlRejected...); 130 Ctrl-C at the question.
"""

def cmd(argv):
    opts, rest = parse(argv, {}, {"--yes": "yes"}, help=HELP, short=("-y",))
    if len(rest) != 1:
        raise bad_args(HELP, "rm needs the name spelled out (no --target / AOS_AGENT: it deletes the stack, which cannot be undone)")
    need_table()
    a = find(rest[0])
    others = [r.get("stack") for n, r in table(quiet=True).items() if n != a.name]
    keep = covers(a.stack, [a.row.get("ws"), a.row.get("def"), daemon_path(), os.getcwd(), os.path.expanduser("~")] + others)
    question = ("remove %s (its stack %s is kept)?" if keep else
                "remove %s and delete its stack %s?") % (a.name, a.stack)
    if not aos_flags.confirm(PROG, question, yes=opts.get("yes")):
        aos_flags.warn(PROG, "nothing done")
        return
    close_screen_if_any(a)
    direct = is_kernel(a)
    ctl_wait("rm", {"procs_removed": [a.name]}, lambda _: row_named(a.name) is None, "the daemon has not removed %s yet" % a.name, "CtlRejected", direct)
    if keep:                                          # 11-04 夜邊緣實測：add --stack . 之後 rm 會連工作區一起刪；stack 蓋住這些的不刪
        print("removed %s; stack %s kept (it is %s or above it)" % (a.name, a.stack, keep))
        return
    shutil.rmtree(a.stack, ignore_errors=True)        # 不封存（使用者 11-02 晚）
    print("removed %s (deleted stack %s)" % (a.name, a.stack))


def covers(stack, paths):
    """stack 是不是 paths 裡某一個、或在它上層（rm 不能刪的）；回那一個或 None。"""
    s = os.path.realpath(stack)
    for p in paths:
        if isinstance(p, str) and p:
            r = os.path.realpath(p)
            if r == s or r.startswith(s.rstrip("/") + "/"):
                return p
    return None
