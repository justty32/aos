# aos_agent/ctl/state.py - 顯示單隻 agent 的狀態、回答與工具覆蓋層。
import aos_ws
import json
import os
from ..common import bad_args, Fail, parse, target
from ..decl import agent_decl, def_of, show_limits
from agent_files import declared_files
from ..hints import label, queued


HELP = """aos-agent ctl state - show one agent's state (status = the same)

usage: aos-agent [--daemon D] ctl state [--target NAME]

flags:
  -t, --target NAME   which agent (default: $AOS_AGENT)
  -h, --help          show this help

Prints its state, paths, queue, latest answer and tool overlay on stdout.
exit codes: 0 shown; 1 error (TargetMissing, InstanceMissing...).
more: proto8/cmd/aos-agent/README.md
"""

def last_answer(a):
    got = aos_ws.answers(a.stack)
    if not got:
        return "(none yet)"
    s = got[-1].strip().replace("\n", " ")
    return s[:60] + ("…" if len(s) > 60 else "")


def cmd(argv):
    opts, rest = parse(argv, {"--target": "target"}, help=HELP, short=("-t",))
    if rest:
        raise bad_args(HELP, "state takes no positional arguments: %s (pick the target with --target)" % rest[0])
    a = target(opts)
    q = queued(a)
    lines = ["name    %s" % a.name, "state   %s (daemon phase %s)" % (label(a), a.phase), "ws      %s" % (a.row.get("ws") or "-"),
             "stack   %s" % a.stack, "queue   %s" % ("-" if q is None else "%d queued" % q), "answer  %s" % last_answer(a)]
    try:
        lines.insert(4, "def     %s" % def_of(a))
    except Fail:
        pass
    if a.row.get("limits"):                           # 11-05 feat-proto 件 5：表上那列的份額（E1 起 daemon 寫；沒有不印）
        at = max(i for i, s in enumerate(lines) if s.startswith(("stack ", "def ")))
        lines.insert(at + 1, "limits  %s" % show_limits(a.row["limits"]))
    ov = overlay_count(a)
    if ov:
        lines.insert(len(lines) - 2, "tools   %s" % ov)
    if a.reason:
        lines.insert(2, "reason  %s" % a.reason)
    warn = aos_ws.read(os.path.join(a.stack, "mailbox_warning.txt"))
    if warn and warn.strip():
        lines.append("badmail %s" % warn.strip().splitlines()[-1])
    print("\n".join(lines))


def overlay_count(a):
    """ctl state 的一行（11-05 feat-proto 件 1）：這隻宣告的 tools 覆蓋層 加了幾個、拿掉幾個；沒覆蓋層＝None。"""
    try:
        folder, decl = agent_decl(a)
        rel = declared_files(folder).get("tools")
    except (Fail, ValueError):
        return None
    if rel is None:
        return None
    p = os.path.join(a.stack, rel)
    if not os.path.isfile(p):
        return None
    try:
        with open(p, encoding="utf-8") as f:
            o = json.load(f)
        add, rm = o.get("add") or {}, o.get("rm") or []
        return "overlay: %d added, %d removed (%s)" % (len(add), len(rm), ", ".join(["+" + n for n in add] + ["-" + n for n in rm]) or "empty")
    except (OSError, ValueError, AttributeError, TypeError) as e:
        return "overlay unreadable: %s (%s)" % (p, e)
