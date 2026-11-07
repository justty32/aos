# aos_agent/ctl/phase.py - 起停、睡醒與暫停恢復 agent。
import aos_ws
import daemon_ctl as dc
from ..common import bad_args, Fail, call_dc, ctl_wait, daemon_path, find, need_table, note, parse, phase_body, row_named, target, wait_for, timeout_opt, queued_opt
from ..decl import close_screen_if_any
from ..hints import comes_back_paused, label, queued


HELP = {
    "start": """aos-agent ctl start - start it again with the same stack

usage: aos-agent [--daemon D] ctl start [--target NAME] [--timeout-s S] [--on-queued fail|ok]

flags:
  -t, --target NAME   which agent (default: $AOS_AGENT)
      --timeout-s S   seconds to wait for the daemon (default 30)
      --on-queued MODE  fail or ok when still queued (default fail)
  -h, --help          show this help

Prints one result line on stdout; state already reached is a successful no-op.
exit codes: 0 done; 1 error (TargetMissing, InstanceMissing, PhaseBad, CtlRejected...).
more: proto8/cmd/aos-agent/README.md
""",
    "stop": """aos-agent ctl stop - stop after this round and keep its stack

usage: aos-agent [--daemon D] ctl stop [--target NAME] [--timeout-s S]

flags:
  -t, --target NAME   which agent (default: $AOS_AGENT)
      --timeout-s S   seconds to wait for the daemon (default 30)
  -h, --help          show this help

Prints one result line on stdout; state already reached is a successful no-op.
exit codes: 0 done; 1 error (TargetMissing, InstanceMissing, PhaseBad, CtlRejected...).
more: proto8/cmd/aos-agent/README.md
""",
    "sleep": """aos-agent ctl sleep - SIGTERM a running or stopping proc and keep its stack

usage: aos-agent [--daemon D] ctl sleep [--target NAME] [--timeout-s S]

flags:
  -t, --target NAME   which agent (default: $AOS_AGENT)
      --timeout-s S   seconds to wait for the daemon (default 30)
  -h, --help          show this help

Running becomes sleeping (wake or daemon restart brings it back).
Stopping after stop becomes stopped (use start to run it again).
Prints one result line on stdout; state already reached is a successful no-op.
exit codes: 0 done; 1 error (TargetMissing, InstanceMissing, PhaseBad, CtlRejected...).
more: proto8/cmd/aos-agent/README.md
""",
    "wake": """aos-agent ctl wake - wake it with the same stack

usage: aos-agent [--daemon D] ctl wake [--target NAME] [--timeout-s S] [--on-queued fail|ok]

flags:
  -t, --target NAME   which agent (default: $AOS_AGENT)
      --timeout-s S   seconds to wait for the daemon (default 30)
      --on-queued MODE  fail or ok when still queued (default fail)
  -h, --help          show this help

Prints one result line on stdout; state already reached is a successful no-op.
exit codes: 0 done; 1 error (TargetMissing, InstanceMissing, PhaseBad, CtlRejected...).
more: proto8/cmd/aos-agent/README.md
""",
    "pause": """aos-agent ctl pause - pause its loop through the ctl window

usage: aos-agent [--daemon D] ctl pause [--target NAME]

flags:
  -t, --target NAME   which agent (default: $AOS_AGENT)
  -h, --help          show this help

Prints one result line on stdout; state already reached is a successful no-op.
exit codes: 0 done; 1 error (TargetMissing, InstanceMissing, PhaseBad, CtlRejected...).
more: proto8/cmd/aos-agent/README.md
""",
    "resume": """aos-agent ctl resume - resume its paused loop

usage: aos-agent [--daemon D] ctl resume [--target NAME]

flags:
  -t, --target NAME   which agent (default: $AOS_AGENT)
  -h, --help          show this help

Prints one result line on stdout; state already reached is a successful no-op.
exit codes: 0 done; 1 error (TargetMissing, InstanceMissing, PhaseBad, CtlRejected...).
more: proto8/cmd/aos-agent/README.md
""",
}

def cmd_start(argv):
    opts, rest = parse(argv, {"--target": "target", "--timeout-s": "timeout_s", "--on-queued": "on_queued"}, help=HELP["start"], short=("-t",))
    secs = timeout_opt(opts, HELP["start"])
    on_queued = queued_opt(opts, HELP["start"])
    if rest:
        raise bad_args(HELP["start"], "start takes no positional arguments: %s (pick the target with --target)" % rest[0])
    need_table()
    a = target(opts)
    if a.phase == "stopping":                         # 還在停的途中：等它停好再起
        wait_for(lambda: (row_named(a.name) or {}).get("phase") != "stopping", "the daemon has not finished stopping %s" % a.name, secs)
        a = find(a.name)
    if a.phase in {"running", "stuck"}:
        print("already running (%s)" % label(a))
        return
    n, held = queued(a) or 0, comes_back_paused(a)
    result = ctl_wait("start", phase_body("start", a.name), lambda _: (row_named(a.name) or {}).get("phase") != "stopped",   # sleeping 的＝daemon_ctl PhaseBad「要 wake」
             "the daemon has not started %s yet" % a.name, "CtlRejected", secs=secs, on_queued=on_queued, name=a.name)
    if result is None:
        return
    print("started (same stack); %d queued letter(s) will be answered next" % n + paused_tail(a, held))


def paused_tail(a, held):
    """11-05 晚：暫停中被停／睡的，起來照它的 state 先暫停——原本照樣說「will be answered next」，listen 才發現暫停著。"""
    return "; it was paused when it went down, so it comes back paused: aos-agent ctl resume --target %s" % a.name if held else ""


def cmd_stop(argv):
    opts, rest = parse(argv, {"--target": "target", "--timeout-s": "timeout_s"}, help=HELP["stop"], short=("-t",))
    secs = timeout_opt(opts, HELP["stop"])
    if rest:
        raise bad_args(HELP["stop"], "stop takes no positional arguments: %s (pick the target with --target)" % rest[0])
    need_table()
    a = target(opts)
    if a.phase == "stopped":
        print("already stopped (%s)" % label(a))
        return
    if a.phase == "sleeping":                         # 11-05 嚴格分：不關畫面、直接讓 daemon_ctl 報 PhaseBad「要先 wake」
        phase_body("stop", a.name)
    close_screen_if_any(a)
    stopped = lambda _: (row_named(a.name) or {"phase": "stopped"}).get("phase") == "stopped"
    if a.phase != "stopping":
        ctl_wait("stop", phase_body("stop", a.name), stopped, "the daemon has not finished stopping %s" % a.name, "CtlRejected", secs=secs)
    else:
        wait_for(lambda: stopped(None), "the daemon has not finished stopping %s" % a.name, secs)
    print("stopped, stack kept (%s); say still queues letters meanwhile, aos-agent ctl start --target %s to carry on" % (a.stack, a.name))


def cmd_sleep(argv):
    """sleep：送 SIGTERM，running 留 sleeping、stop 中留 stopped；stack 與 launch 保留。"""
    opts, rest = parse(argv, {"--target": "target", "--timeout-s": "timeout_s"}, help=HELP["sleep"], short=("-t",))
    secs = timeout_opt(opts, HELP["sleep"])
    if rest:
        raise bad_args(HELP["sleep"], "sleep takes no positional arguments: %s (pick the target with --target)" % rest[0])
    need_table()
    a = target(opts)
    if a.phase == "sleeping":
        print("already asleep (%s)" % label(a))
        return
    rows = aos_ws.history(a.stack)                    # 11-05 edge-agent：eca 答到一半 sleep＝那批不重答，醒來也等不到
    if rows and not aos_ws.is_answer(rows[-1]):
        note("%s has not finished answering the last message; some bodies (eca) drop the batch being answered when put to sleep: if no answer comes after wake, say it again" % a.name)
    row = row_named(a.name) or {}
    final_phase = "stopped" if row.get("stop_mode") == "stop" else "sleeping"
    ctl_wait("sleep", phase_body("sleep", a.name), lambda _: (row_named(a.name) or {"phase": final_phase}).get("phase") == final_phase,
             "the daemon has not put %s to sleep yet" % a.name, "CtlRejected", secs=secs)
    if final_phase == "stopped":
        print("stopped, stack kept (%s); aos-agent ctl start --target %s starts it again" % (a.stack, a.name))
    else:
        print("asleep, stack kept (%s); say still queues letters meanwhile, aos-agent ctl wake --target %s wakes it (it also wakes when the daemon restarts)" % (a.stack, a.name))


def cmd_wake(argv):
    opts, rest = parse(argv, {"--target": "target", "--timeout-s": "timeout_s", "--on-queued": "on_queued"}, help=HELP["wake"], short=("-t",))
    secs = timeout_opt(opts, HELP["wake"])
    on_queued = queued_opt(opts, HELP["wake"])
    if rest:
        raise bad_args(HELP["wake"], "wake takes no positional arguments: %s (pick the target with --target)" % rest[0])
    need_table()
    a = target(opts)
    if a.phase in {"running", "stuck"}:
        print("already awake (%s)" % label(a))
        return
    n, held = queued(a) or 0, comes_back_paused(a)
    result = ctl_wait("wake", phase_body("wake", a.name), lambda _: (row_named(a.name) or {}).get("phase") != "sleeping",   # stopped 的＝daemon_ctl PhaseBad「要 start」
             "the daemon has not woken %s yet" % a.name, "CtlRejected", secs=secs, on_queued=on_queued, name=a.name)
    if result is None:
        return
    print("awake (same stack); %d queued letter(s) will be answered next" % n + paused_tail(a, held))


def cmd_pause_resume(cmd):
    def run(argv):
        opts, rest = parse(argv, {"--target": "target"}, help=HELP[cmd], short=("-t",))
        if rest:
            raise bad_args(HELP[cmd], "%s takes no positional arguments: %s (pick the target with --target)" % (cmd, rest[0]))
        a = target(opts)
        call_dc(dc.write_ctl, daemon_path(), a.name, cmd)  # seq 對人沒意義、不印
        print("paused %s; aos-agent ctl resume --target %s to continue" % (a.name, a.name) if cmd == "pause" else "resumed %s" % a.name)
    return run
