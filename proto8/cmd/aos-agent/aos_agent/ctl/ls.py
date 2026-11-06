# aos_agent/ctl/ls.py - 列出 daemon 表上的 proc 與狀態。
import json
from ..common import Agent, Fail, parse, table
from ..hints import label, queued


# ---------------------------------------------------------------- 子命令：查表類＋說話（步 4）

def cmd(argv):
    opts, rest = parse(argv, {}, {"--json": "json"})
    if rest:
        raise Fail("ArgumentsBad", "ls takes no arguments: %s" % rest[0])
    rows = [Agent(n, r) for n, r in table().items()]
    if opts.get("json"):
        print(json.dumps([dict(name=a.name, state=label(a), phase=a.phase, ws=a.row.get("ws") or "", stack=a.stack,
                               queued=queued(a), reason=a.reason) for a in rows], ensure_ascii=False))
        return
    for a in rows:
        q = queued(a)
        print("\t".join([a.name, label(a), a.row.get("ws") or "-", "-" if q is None else str(q),
                         " ".join(str(a.reason).splitlines()) if a.reason else "-"]))
