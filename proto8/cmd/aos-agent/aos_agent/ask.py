# aos_agent/ask.py - 一問一答：say 一則再等最新那則回答（跟 subagent 工具的 op ask 同語意，不配對信名）。
HELP = """aos-agent ask - put one message in the agent's queue and print its answer

usage: aos-agent [--daemon D] ask [--target NAME] [--from WHO] [--timeout-s SECS | --timeout-cycles N] [WORDS...]
       ... | aos-agent [--daemon D] ask [--target NAME] [--from WHO] [--timeout-s SECS | --timeout-cycles N]

Same as aos-agent say followed by aos-agent listen (and the same as the subagent tool's
op ask): WORDS are the message exactly as for say (flags go before them; no WORDS or "-" =
the whole of stdin), then it waits for the latest answer and prints only its text on stdout.
The letter name is not printed.
Limit: the answer is not matched to your letter. It is the agent's latest answer, so if
someone else says something to the same agent at the same time, the answer you get may be
the one to their message (or yours may go to them).

flags:
  -t, --target NAME   which agent (default: $AOS_AGENT)
  --from WHO          the sender's name (same as aos-agent say --from)
  --timeout-s SECS    give up after SECS seconds (AnswerMissing); default 600; 0 = no limit
  --timeout-cycles N  give up after N cycles (positive integer); exclusive with --timeout-s
  -h, --help          show this help

exit codes: 0 printed; 1 error (TargetMissing, InstanceMissing, AnswerMissing...); 130 Ctrl-C while waiting
  (the message was sent; read the answer later with aos-agent listen)."""

import sys
import aos_ws
from .common import bad_args, note, parse, target
from .listen import cycles, seconds, wait_latest
from .say import message
from . import sender

DEFAULT_S = 600                                 # 對齊 subagent 工具的 op ask（lib/agent/agents_cmd.py 的 LISTEN_DEFAULT_S）


def cmd(argv):
    """11-14 意見「aos-agent 沒有 ask」：ok-pilot 定只對齊 subagent 的 op ask＝say 接 listen、不配對（真配對要 agent 端記信名，另案）。"""
    opts, rest = parse(argv, dict({"--target": "target", "--timeout-s": "timeout", "--timeout-cycles": "timeout_cycles"}, **sender.FLAG),
                       help=HELP, short=("-t",), keep=1)   # 同 say：WORDS 起原樣交出
    if "timeout" in opts and "timeout_cycles" in opts:
        raise bad_args(HELP, "--timeout-s and --timeout-cycles are mutually exclusive")
    timeout_cycles = cycles(opts["timeout_cycles"], HELP) if "timeout_cycles" in opts else None
    timeout = DEFAULT_S if opts.get("timeout") is None else seconds(opts["timeout"], HELP, "0 = no limit")
    a = target(opts)                                # 同 say：先找對象，沒對象不先等 stdin
    who = sender.sender(opts, HELP)
    text = message(rest, HELP)
    before = len(aos_ws.answers(a.stack))           # 寄之前數（同 chat）：回答比 listen 開始等還早到也認得
    sender.put(a, text, who)
    try:
        wait_latest(a, None if timeout_cycles is not None or timeout == 0 else timeout, before, timeout_cycles=timeout_cycles)
    except KeyboardInterrupt:
        note("that message was sent; read the answer later with aos-agent listen --target %s" % a.name)
        sys.exit(130)
