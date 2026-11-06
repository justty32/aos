# aos_agent/ctl/where.py - 顯示 agent 的 stack 或工作區路徑。
import daemon_ctl as dc
import os
from ..common import bad_args, Fail, call_dc, daemon_path, find, parse, target


HELP = """aos-agent ctl where - print its stack or workspace path

usage: aos-agent [--daemon D] ctl where [--stack | --ws] [-t NAME]

flags:
  -t, --target NAME   which agent (default: $AOS_AGENT)
  --stack            print its stack (default)
  --ws               print its workspace instead
  -h, --help          show this help

Prints one path on stdout. --stack and --ws cannot be combined.
exit codes: 0 printed; 1 error (TargetMissing, InstanceMissing, WsMissing...).
more: proto8/cmd/aos-agent/README.md
"""

def cmd(argv):
    """預設（＝--stack）印它的 stack；--ws 印它的工作區（使用者 11-04 晚「aos agent的where，我希望默認是--stack，有需要再另外指定--ws。」）。"""
    opts, rest = parse(argv, {"--target": "target"}, {"--stack": "stack", "--ws": "ws"}, help=HELP, short=("-t",))
    if rest:
        raise bad_args(HELP, "where takes no positional arguments: %s (pick the target with --target)" % rest[0])
    if opts.get("stack") and opts.get("ws"):
        raise bad_args(HELP, "where takes only one of --stack and --ws (neither = --stack)")
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
