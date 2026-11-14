# aos_agent/ctl/where.py - 顯示 agent 的 stack 或工作區路徑。
import daemon_ctl as dc
from ..common import bad_args, Fail, call_dc, find, parse, table_ref, target, target_name
from .shared import name_last, query_opt


HELP = """aos-agent ctl where - print its stack or workspace path

usage: aos-agent [--daemon D] ctl where [--stack | --ws] [-t NAME] [--timeout-s S] [NAME]

flags:
  -t, --target NAME   which agent (default: $AOS_AGENT); or NAME as the last argument
  --stack            print its stack (default)
  --ws               print its workspace instead
  --timeout-s S       seconds to wait for AOS_KERNEL's answer about the table (default 3)
  -h, --help          show this help

Prints one path on stdout. --stack and --ws cannot be combined.
With $AOS_KERNEL set (and no --daemon) it first asks AOS_KERNEL where the table is (a
procs_state_path letter) and reads that file; no answer within --timeout-s = KernelFailed
(AOS_DAEMON is not read instead).
exit codes: 0 printed; 1 error (TargetMissing, InstanceMissing, WsMissing, KernelFailed...).
more: proto8/cmd/aos-agent/README.md
"""

def cmd(argv):
    """預設（＝--stack）印它的 stack；--ws 印它的工作區（使用者 11-04 晚「aos agent的where，我希望默認是--stack，有需要再另外指定--ws。」）。"""
    opts, rest = parse(argv, {"--target": "target", "--timeout-s": "timeout_s"}, {"--stack": "stack", "--ws": "ws"}, help=HELP, short=("-t",))
    name_last(opts, rest, HELP)
    if opts.get("stack") and opts.get("ws"):
        raise bad_args(HELP, "where takes only one of --stack and --ws (neither = --stack)")
    query_opt(opts, HELP)
    name = target_name(opts)
    if not name:
        target(opts)                                    # TargetMissing
    if not opts.get("ws"):
        print(call_dc(dc.cell_of, table_ref(), name))
        return
    ws = find(name).row.get("ws")
    if not ws:
        raise Fail("WsMissing", "%s has no workspace on the table (not attached with aos-agent ctl add / aos-daemon-ctl add --ws; it runs in the daemon's own AOS_WS)" % name)
    print(ws)
