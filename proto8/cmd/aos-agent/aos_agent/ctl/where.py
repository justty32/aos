# aos_agent/ctl/where.py - 顯示 agent 的 stack 或工作區路徑。
import daemon_ctl as dc
import os
from ..common import Fail, call_dc, daemon_path, find, parse, target


def cmd(argv):
    """預設（＝--stack）印它的 stack；--ws 印它的工作區（使用者 11-04 晚「aos agent的where，我希望默認是--stack，有需要再另外指定--ws。」）。"""
    opts, rest = parse(argv, {"--target": "target"}, {"--stack": "stack", "--ws": "ws"})
    if rest:
        raise Fail("ArgumentsBad", "where takes no positional arguments: %s (pick the target with --target)" % rest[0])
    if opts.get("stack") and opts.get("ws"):
        raise Fail("ArgumentsBad", "where takes only one of --stack and --ws (neither = --stack)")
    name = opts.get("target") or os.environ.get("AOS_AGENT", "")
    if not name:
        target(opts)                                    # TargetMissing
    if not opts.get("ws"):
        print(call_dc(dc.cell_of, daemon_path(), name))
        return
    ws = find(name).row.get("ws")
    if not ws:
        raise Fail("WsMissing", "%s has no workspace on the table (not attached with aos-agent ctl add / aos-daemon-ctl add --ws; it runs in the daemon's own AOS_WS)" % name)
    print(ws)
