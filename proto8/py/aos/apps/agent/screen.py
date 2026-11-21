# aos/apps/agent/screen.py - 開啟、關閉與追蹤 agent 的畫面子介面。
HELP = {
    'open': """aos-agent open - open and attach to the agent's screen

usage: aos-agent [--daemon D] open [-t NAME] [--detach]

flags:
  -t, --target NAME   which agent (default: $AOS_AGENT, else ./.stack or ./)
  --detach           open the screen without attaching
  -h, --help          show this help

Runs the screen entry declared by the definition; its output goes to the terminal.
With --detach, only opens the screen. The definition must declare aos-agent/screen.

exit codes: 0 done; 1 error (TargetMissing, InstanceMissing, ScreenMissing, ScreenBad...).""",
    'close': """aos-agent close - close the agent's screen

usage: aos-agent [--daemon D] close [-t NAME]

flags:
  -t, --target NAME   which agent (default: $AOS_AGENT, else ./.stack or ./)
  -h, --help          show this help

Runs the definition's screen close action and passes its output through.
If the screen is answering, its entry may refuse with SessionBad.

exit codes: 0 done; 1 error (TargetMissing, InstanceMissing, ScreenMissing, ScreenBad...).""",
    'watch': """aos-agent watch - follow the agent's screen until one answer ends

usage: aos-agent [--daemon D] watch [-t NAME]

flags:
  -t, --target NAME   which agent (default: $AOS_AGENT, else ./.stack or ./)
  -h, --help          show this help

Runs the definition's screen watch action and passes its output through.
The definition must declare the aos-agent/screen interface.

exit codes: 0 done; 1 error (TargetMissing, InstanceMissing, ScreenMissing, ScreenBad...).""",
    'peek': """aos-agent peek - answer /status or /usage at once, without the queue

usage: aos-agent [--daemon D] peek [-t NAME] /status|/usage

flags:
  -t, --target NAME   which agent (default: $AOS_AGENT, else ./.stack or ./)
  -h, --help          show this help

Runs the definition's screen peek action and prints its answer: no letter, nothing in
history, nothing typed into the screen, so it also answers while the agent is in a turn.
The definition must declare the aos-agent/screen interface (eca does).

exit codes: 0 printed; 1 error (TargetMissing, InstanceMissing, ScreenMissing, ScreenBad...)."""
}

from .common import Fail, bad_args, parse, target
from .decl import pass_err, run_entry, screen_entry


def peek(argv):
    """11-16 ok-small：唯讀 slash 當場回＝screen 入口的 peek 動作（使用者 11-16「/usage、/status 在 agent 忙的時候也直接回，不用排隊」）。"""
    opts, rest = parse(argv, {"--target": "target"}, help=HELP["peek"], short=("-t",))
    if len(rest) != 1:
        raise bad_args(HELP["peek"], "peek takes one command (what the body answers, eca: /status or /usage), got %d arguments" % len(rest))
    a = target(opts)
    _, entry = screen_entry(a)
    rc, err = run_entry(a, entry, ["peek", rest[0]])
    pass_err(rc, err)


def cmd(action):
    def run(argv):
        opts, rest = parse(argv, {"--target": "target"}, {"--detach": "detach"} if action == "open" else None,
                           help=HELP[action], short=("-t",))
        if rest:
            raise bad_args(HELP[action], "%s takes no positional arguments: %s (pick the target with --target)" % (action, rest[0]))
        a = target(opts)
        _, entry = screen_entry(a)
        args = [action] + (["--detach"] if opts.get("detach") else [])
        attach = action == "open" and not opts.get("detach")
        rc, err = run_entry(a, entry, args, capture_err=not attach)
        if attach and rc != 0:
            raise Fail("ScreenBad", "the screen entry %s of %s exited %d" % (entry, a.name, rc))
        pass_err(rc, err)
    return run
