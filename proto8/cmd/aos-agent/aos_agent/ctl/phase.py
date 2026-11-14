# aos_agent/ctl/phase.py - 起停、睡醒與暫停恢復 agent（走 AOS_KERNEL 時 start／stop／sleep／wake 只看回信）。
import aos_ws
import daemon_ctl as dc
from ..common import call_dc, find, note, parse, row_named, table_ref, target, target_name, via_kernel
from .shared import ctl_wait, name_last, need_table, phase_body, queued_opt, send_only, timeout_opt, wait_for
from ..decl import close_screen_if_any
from ..hints import comes_back_paused, label, queued


HELP = {
    "start": """aos-agent ctl start - start it again with the same stack

usage: aos-agent [--daemon D] ctl start [--target NAME] [--timeout-s S] [--on-queued fail|ok] [NAME]

flags:
  -t, --target NAME   which agent (default: $AOS_AGENT); or NAME as the last argument
      --timeout-s S   seconds to wait for the daemon (default 30)
      --on-queued MODE  fail or ok when still queued (default fail)
  -h, --help          show this help

Prints one result line on stdout; state already reached is a successful no-op.
With $AOS_KERNEL set (and no --daemon) it reads only the reply to its own letter (no table
lookup, no phase check first, no wait for the table): "start accepted for NAME".
exit codes: 0 done; 1 error (TargetMissing, InstanceMissing, PhaseBad, CtlRejected...).
more: proto8/cmd/aos-agent/README.md
""",
    "stop": """aos-agent ctl stop - stop after this round and keep its stack

usage: aos-agent [--daemon D] ctl stop [--target NAME] [--no-wait] [--timeout-s S] [NAME]

flags:
  -t, --target NAME   which agent (default: $AOS_AGENT); or NAME as the last argument
      --timeout-s S   seconds to wait for the daemon (default 30)
      --no-wait       send it and return; do not wait for it to happen (for an agent stopping itself)
  -h, --help          show this help

Stops when this round ends. --no-wait waits only for the daemon to accept the letter.
Closes its screen first; a workspace that is gone does not block it (one warning line).
Prints one result line on stdout; state already reached is a successful no-op.
With $AOS_KERNEL set (and no --daemon) it reads only the reply to its own letter (no table
lookup, no phase check first, no wait for the table): "stop accepted for NAME".
exit codes: 0 done; 1 error (TargetMissing, InstanceMissing, PhaseBad, CtlRejected...).
more: proto8/cmd/aos-agent/README.md
""",
    "sleep": """aos-agent ctl sleep - SIGTERM a running or stopping proc and keep its stack

usage: aos-agent [--daemon D] ctl sleep [--target NAME] [--no-wait] [--timeout-s S] [NAME]

flags:
  -t, --target NAME   which agent (default: $AOS_AGENT); or NAME as the last argument
      --timeout-s S   seconds to wait for the daemon (default 30)
      --no-wait       send it and return; do not wait for it to happen (for an agent stopping itself)
  -h, --help          show this help

Running becomes sleeping (wake or daemon restart brings it back).
Stopping after stop becomes stopped (use start to run it again).
--no-wait sends the letter and returns at once (the daemon then SIGTERMs it).
Prints one result line on stdout; state already reached is a successful no-op.
With $AOS_KERNEL set (and no --daemon) it reads only the reply to its own letter (no table
lookup, no phase check first, no wait for the table): "sleep accepted for NAME".
exit codes: 0 done; 1 error (TargetMissing, InstanceMissing, PhaseBad, CtlRejected...).
more: proto8/cmd/aos-agent/README.md
""",
    "wake": """aos-agent ctl wake - wake it with the same stack

usage: aos-agent [--daemon D] ctl wake [--target NAME] [--timeout-s S] [--on-queued fail|ok] [NAME]

flags:
  -t, --target NAME   which agent (default: $AOS_AGENT); or NAME as the last argument
      --timeout-s S   seconds to wait for the daemon (default 30)
      --on-queued MODE  fail or ok when still queued (default fail)
  -h, --help          show this help

Prints one result line on stdout; state already reached is a successful no-op.
With $AOS_KERNEL set (and no --daemon) it reads only the reply to its own letter (no table
lookup, no phase check first, no wait for the table): "wake accepted for NAME".
exit codes: 0 done; 1 error (TargetMissing, InstanceMissing, PhaseBad, CtlRejected...).
more: proto8/cmd/aos-agent/README.md
""",
    "pause": """aos-agent ctl pause - pause its loop through the ctl window

usage: aos-agent [--daemon D] ctl pause [--target NAME] [--no-wait] [NAME]

flags:
  -t, --target NAME   which agent (default: $AOS_AGENT); or NAME as the last argument
      --no-wait       send it and return; do not wait for it to happen (for an agent stopping itself)
  -h, --help          show this help

--no-wait writes its ctl and returns (a running step is not interrupted; it pauses
between steps). It stays paused until someone runs ctl resume.
Prints one result line on stdout; state already reached is a successful no-op.
exit codes: 0 done; 1 error (TargetMissing, InstanceMissing, PhaseBad, CtlRejected...).
more: proto8/cmd/aos-agent/README.md
""",
    "resume": """aos-agent ctl resume - resume its paused loop

usage: aos-agent [--daemon D] ctl resume [--target NAME] [NAME]

flags:
  -t, --target NAME   which agent (default: $AOS_AGENT); or NAME as the last argument
  -h, --help          show this help

Prints one result line on stdout; state already reached is a successful no-op.
exit codes: 0 done; 1 error (TargetMissing, InstanceMissing, PhaseBad, CtlRejected...).
more: proto8/cmd/aos-agent/README.md
""",
}

def name_only(opts):
    """只看回信的路：要名字、不讀表（--target ＞ 子命令前的 --target ＞ $AOS_AGENT；都沒有＝TargetMissing）。"""
    name = target_name(opts)
    if not name:
        target(opts)                                  # TargetMissing
    return name


def by_letter(cmd, opts, secs, on_queued="fail"):
    """走 kernel 的 start／stop／sleep／wake（kernel-framework 03）：只寄那封信、只看它的回信；不讀表、不核 phase、不關畫面、不等表。"""
    name = name_only(opts)
    if ctl_wait(cmd, phase_body(cmd, name, look=False), lambda _: True, "the %s letter for %s has no reply yet" % (cmd, name),
                "CtlRejected", secs=secs, on_queued=on_queued, name=name, replied=True) is None:
        return None                                   # 排隊中、--on-queued ok：ctl_wait 已印 queued 那行
    return name


def cmd_start(argv, look=None):
    """look＝讀表核 phase、等表上起來（沒走 kernel 一律如此；set-def --restart 走 kernel 時也明給）；None＝走 kernel 就只看回信。"""
    opts, rest = parse(argv, {"--target": "target", "--timeout-s": "timeout_s", "--on-queued": "on_queued"}, help=HELP["start"], short=("-t",))
    secs = timeout_opt(opts, HELP["start"])
    on_queued = queued_opt(opts, HELP["start"])
    name_last(opts, rest, HELP["start"])
    if not (look if look is not None else not via_kernel()):
        name = by_letter("start", opts, secs, on_queued)
        if name:
            print("start accepted for %s" % name)
        return
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


def cmd_stop(argv, look=None):
    opts, rest = parse(argv, {"--target": "target", "--timeout-s": "timeout_s"}, {"--no-wait": "no_wait"}, help=HELP["stop"], short=("-t",))
    secs = timeout_opt(opts, HELP["stop"])
    name_last(opts, rest, HELP["stop"])
    if not (look if look is not None else not via_kernel()):      # --no-wait 也一樣：本來就只等 daemon 收下
        name = by_letter("stop", opts, secs)
        print("stop accepted for %s; aos-agent ctl start --target %s to carry on" % (name, name))
        return
    need_table()
    a = target(opts)
    if a.phase == "stopped":
        print("already stopped (%s)" % label(a))
        return
    if a.phase == "sleeping":                         # 11-05 嚴格分：不關畫面、直接讓 daemon_ctl 報 PhaseBad「要先 wake」
        phase_body("stop", a.name)
    if opts.get("no_wait"):                           # 11-10 self_ctl：對自己下 stop＝這一輪（含叫這支的工具）不結束就停不了；只等 daemon 收下
        if a.phase != "stopping":
            ctl_wait("stop", phase_body("stop", a.name), lambda _: True, "the daemon has not accepted the stop for %s" % a.name, "CtlRejected", secs=secs, replied=True)
        print("stop accepted; %s stops when this round ends, stack kept (%s); aos-agent ctl start --target %s to carry on" % (a.name, a.stack, a.name))
        return
    close_screen_if_any(a)
    stopped = lambda _: (row_named(a.name) or {"phase": "stopped"}).get("phase") == "stopped"
    if a.phase != "stopping":
        ctl_wait("stop", phase_body("stop", a.name), stopped, "the daemon has not finished stopping %s" % a.name, "CtlRejected", secs=secs)
    else:
        wait_for(lambda: stopped(None), "the daemon has not finished stopping %s" % a.name, secs)
    print("stopped, stack kept (%s); say still queues letters meanwhile, aos-agent ctl start --target %s to carry on" % (a.stack, a.name))


def cmd_sleep(argv):
    """sleep：送 SIGTERM，running 留 sleeping、stop 中留 stopped；stack 與 launch 保留。"""
    opts, rest = parse(argv, {"--target": "target", "--timeout-s": "timeout_s"}, {"--no-wait": "no_wait"}, help=HELP["sleep"], short=("-t",))
    secs = timeout_opt(opts, HELP["sleep"])
    name_last(opts, rest, HELP["sleep"])
    if via_kernel():
        if opts.get("no_wait"):                       # 寄出就回、不等回信（同下面沒走 kernel 的 --no-wait）
            name = name_only(opts)
            send_only(phase_body("sleep", name, look=False))
            print("sleep sent for %s; aos-agent ctl ls shows it once the daemon has applied it" % name)
            return
        name = by_letter("sleep", opts, secs)
        print("sleep accepted for %s" % name)
        return
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
    if opts.get("no_wait"):                           # 11-10 self_ctl：睡的是自己＝SIGTERM 會連這支一起收掉；寄出就回、不等回信
        send_only(phase_body("sleep", a.name))
        print("sleep sent; %s will be %s, stack kept (%s); %s" % (a.name, final_phase, a.stack,
              "aos-agent ctl start --target %s starts it again" % a.name if final_phase == "stopped" else
              "aos-agent ctl wake --target %s wakes it (it also wakes when the daemon restarts)" % a.name))
        return
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
    name_last(opts, rest, HELP["wake"])
    if via_kernel():
        name = by_letter("wake", opts, secs, on_queued)
        if name:
            print("wake accepted for %s" % name)
        return
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
        opts, rest = parse(argv, {"--target": "target"}, {"--no-wait": "no_wait"} if cmd == "pause" else {}, help=HELP[cmd], short=("-t",))
        name_last(opts, rest, HELP[cmd])
        a = target(opts)
        call_dc(dc.write_ctl, table_ref(), a.name, cmd, wait=not opts.get("no_wait"))   # 走 kernel＝表檔經查詢信拿  # seq 對人沒意義、不印
        if opts.get("no_wait"):
            print("pause sent; %s pauses between steps and stays paused until aos-agent ctl resume --target %s" % (a.name, a.name))
            return
        print("paused %s; aos-agent ctl resume --target %s to continue" % (a.name, a.name) if cmd == "pause" else "resumed %s" % a.name)
    return run
