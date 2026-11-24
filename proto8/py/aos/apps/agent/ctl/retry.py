# aos/apps/agent/ctl/retry.py - 清掉 agent 的失敗冷卻（cooldown.json），讓它下一拍就重試（使用者 11-24：「做一個立刻重試的動作，但不要做成工具，並盡可能納入現有指令，成為子指令」）。
import time
from aos.agentlib import cooldown
from ..common import Fail, parse, target
from ..hints import label
from .shared import name_last, query_opt


HELP = """aos-agent ctl retry - clear its failure cooldown so it tries again on its next round

usage: aos-agent [--daemon D] ctl retry [--target NAME] [--timeout-s S] [NAME]

flags:
  -t, --target NAME   which agent (default: $AOS_AGENT, ./.stack, ./); or NAME as the last argument
      --timeout-s S   seconds to wait for AOS_KERNEL's answer about the table (default 3)
  -h, --help          show this help

After a failure of the outside service (the brain for agent-fsm: BrainFailed, SendFailed,
BudgetMissing; the CLI for eca: CliFailed, ReplyMissing) the agent waits longer each time
(30 s up to 30 min) in its stack's cooldown.json. retry deletes that file: an agent-fsm sends
its request again and an eca runs its CLI again on the next round, instead of waiting.
Prints what was cleared: failures in a row, the time it was waiting for (local) or "due", and
the last error. No cooldown = says so, exit 0. A stopped or sleeping agent is not started:
the line says how to start or wake it (it then does not wait either).
With $AOS_KERNEL set (and no --daemon) it asks AOS_KERNEL where the table is, as ctl ls does.
exit codes: 0 cleared or nothing to clear; 1 error (TargetMissing, InstanceMissing, WriteFailed...).
more: proto8/py/aos/apps/agent/README.md
"""


def one_line(s, n=200):
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[:n - 3] + "..."


def cmd(argv):
    opts, rest = parse(argv, {"--target": "target", "--timeout-s": "timeout_s"}, help=HELP, short=("-t",))
    name_last(opts, rest, HELP)
    query_opt(opts, HELP)
    a = target(opts)
    st, rec = cooldown.state(a.stack)
    if rec is None:
        print("%s has no cooldown (%s); nothing to clear" % (a.name, cooldown.path(a.stack)))
        return
    try:
        cooldown.clear(a.stack)
    except OSError as e:
        raise Fail("WriteFailed", "cannot remove %s: %s" % (cooldown.path(a.stack), e.strerror or e))
    if st == "cooling":
        wait = "it was waiting until %s" % time.strftime("%H:%M:%S", time.localtime(cooldown.parse(rec["until"])))
    else:
        wait = "it was already due"
    low = rec.get("error")
    said = "%s %s" % (low.get("code", ""), low.get("msg", "")) if isinstance(low, dict) else rec.get("reason") or ""
    last = one_line(" ".join(x for x in (rec.get("code") or "", said) if x)) or "-"
    phase = label(a)
    if phase in ("stopped", "sleeping"):
        verb = "start" if phase == "stopped" else "wake"
        then = "; it is %s: aos-agent ctl %s --target %s to carry on" % (phase, verb, a.name)
    elif phase == "paused":
        then = "; it is paused: aos-agent ctl resume --target %s to carry on" % a.name
    else:
        then = "; it tries again on its next round"
    print("cleared %s's cooldown: %d failure%s in a row, %s; last error: %s%s"
          % (a.name, rec["failures"], "" if rec["failures"] == 1 else "s", wait, last, then))
