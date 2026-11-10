# aos_agent/ctl/state.py - 顯示單隻 agent 的狀態、回答與工具覆蓋層。
import aos_ws
import json
import os
from ..common import bad_args, Fail, parse, target
from ..decl import agent_decl, def_of, show_limits
from .. import declared_files
from ..hints import label, queued


HELP = """aos-agent ctl state - show one agent's state (status = the same)

usage: aos-agent [--daemon D] ctl state [--target NAME]

flags:
  -t, --target NAME   which agent (default: $AOS_AGENT)
  -h, --help          show this help

Prints its state, paths, queue, latest answer and its own tool changes on stdout.
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
    """ctl state 的一行（11-05 feat-proto 件 1）：這隻自己那份 tools（stack 裡、$override 定義那份）加了幾個、拿掉幾個、疊在誰上面；沒有＝None。"""
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
        tools = o.get("tools") or {}                 # 11-10 aos-tools-cli 步 4：{"$override": 底檔, "tools": {加的…, "不要的": null}}（null 那格不算工具）
        if not isinstance(tools, dict):
            raise TypeError("tools is not an object")
        add = sorted(n for n, e in tools.items() if e is not None)
        rm = sorted(n for n, e in tools.items() if e is None)
        base = o.get("$override")
        over = " over %s" % json.dumps(base, ensure_ascii=False) if base is not None else ""
        return "own: %d listed, %d set to null (%s)%s" % (len(add), len(rm), ", ".join(["+" + n for n in add] + ["null:" + n for n in rm]) or "empty", over)
    except (OSError, ValueError, AttributeError, TypeError) as e:
        return "own tools file unreadable: %s (%s)" % (p, e)
