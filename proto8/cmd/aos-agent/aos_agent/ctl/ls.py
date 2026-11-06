# aos_agent/ctl/ls.py - 列出 daemon 表上的 proc 與狀態。
import json
from ..common import bad_args, Agent, Fail, parse, table
from ..hints import label, queued


# ---------------------------------------------------------------- 子命令：查表類＋說話（步 4）

HELP = """aos-agent ctl ls - list every proc on the daemon table

usage: aos-agent [--daemon D] ctl ls [-j]

flags:
  -j, --json   print one JSON array instead of TAB-separated rows
  -h, --help   show this help

Rows: NAME STATE WORKSPACE QUEUED REASON. An empty table prints nothing.
exit codes: 0 listed; 1 error (DaemonMissing...).
more: proto8/cmd/aos-agent/README.md
"""

def cmd(argv):
    opts, rest = parse(argv, {}, {"--json": "json"}, help=HELP, short=("-j",))
    if rest:
        raise bad_args(HELP, "ls takes no arguments: %s" % rest[0])
    rows = [Agent(n, r) for n, r in table().items()]
    if opts.get("json"):
        print(json.dumps([dict(name=a.name, state=label(a), phase=a.phase, ws=a.row.get("ws") or "", stack=a.stack,
                               queued=queued(a), reason=a.reason) for a in rows], ensure_ascii=False))
        return
    for a in rows:
        q = queued(a)
        print("\t".join([a.name, label(a), a.row.get("ws") or "-", "-" if q is None else str(q),
                         " ".join(str(a.reason).splitlines()) if a.reason else "-"]))
