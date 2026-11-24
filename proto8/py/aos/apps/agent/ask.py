# aos/apps/agent/ask.py - 一問一答：say 一則再等配到這封信名的回答（subagent 工具的 op ask 也叫這支；舊身體退回等最新那則）。
HELP = """aos-agent ask - put one message in the agent's queue and print its answer

usage: aos-agent [--daemon D] ask [--target NAME] [--from WHO] [--mailbox DIR] [--timeout-s SECS | --timeout-cycles N] [WORDS...]
       ... | aos-agent [--daemon D] ask [--target NAME] [--from WHO] [--mailbox DIR] [--timeout-s SECS | --timeout-cycles N]

Same as aos-agent say followed by aos-agent listen --letter (the subagent tool's op ask runs
this): WORDS are the message exactly as for say (flags go before them; no WORDS or "-" = the
whole of stdin), then it waits for the answer to that letter and prints only its text on stdout.
The letter name is not printed. Others talking to the same agent at the same time get their
own answers; one answer to several letters at once is printed to each asker.
An agent whose body does not record letter names yet (no aos.letter in its history) is matched
the old way, with a warning on stderr: the latest answer, not necessarily the one to yours.
A failed brain call is reported as in aos-agent listen: if the agent stopped on that error,
ask ends at once with AnswerMissing and the error lines from the agent's stderr file.

flags:
  -t, --target NAME   which agent (default: $AOS_AGENT, else ./.stack or ./)
  --from WHO          the sender's name (same as aos-agent say --from)
  --mailbox DIR       also end on a letter in DIR answering it (same as aos-agent listen --mailbox)
  --timeout-s SECS    give up after SECS seconds (AnswerMissing); 0 or omitted = no limit
  --timeout-cycles N  give up after N cycles (positive integer); exclusive with --timeout-s
  -h, --help          show this help

exit codes: 0 printed; 1 error (TargetMissing, InstanceMissing, AnswerMissing, LetterDropped...); 130 Ctrl-C while waiting
  (the message was sent; read the answer later with aos-agent listen --letter, as the warning says)."""

import os
import sys
from aos import ws as aos_ws
from .common import bad_args, note, parse, target
from .listen import cycles, seconds, wait_latest
from .say import message
from . import sender

DEFAULT_S = 0                                   # 0＝不限（11-15，以前 600）；對齊 subagent 工具的 op ask（py/aos/agentlib/agents_cmd.py 的 LISTEN_DEFAULT_S）


def send(a, text, who):
    """寄一則（ask 與 chat 共用；reply-match-1114 03 §2、§5）：寄之前先記 history 的列數與回答數，給舊身體的退路用
    （信離開 queue 仍查無紀錄、寄之後多了不帶 aos 的信列＝退回等最新那則）。回 (信名, 回答數, 列數)。"""
    rows = aos_ws.history(a.stack)
    before_rows, before = len(rows), sum(1 for m in rows if aos_ws.is_answer(m))
    return sender.put(a, text, who), before, before_rows


def wait_sent(a, sent, timeout, timeout_cycles=None, mailbox=None):
    """等 send 寄的那封的回答（印在 stdout）；mailbox＝也看這個信箱裡回這封的信（listen --mailbox）。"""
    sig, before, before_rows = sent
    wait_latest(a, timeout, before, timeout_cycles=timeout_cycles, letter=sig, before_rows=before_rows, mailbox=mailbox)


def cmd(argv):
    """11-14 意見「aos-agent 沒有 ask」；reply-match-1114 起配對信名（agent 端記 aos.letter／answer_to 與 letters.json）。"""
    opts, rest = parse(argv, dict({"--target": "target", "--timeout-s": "timeout", "--timeout-cycles": "timeout_cycles", "--mailbox": "mailbox"},
                                  **sender.FLAG),
                       help=HELP, short=("-t",), keep=1)   # 同 say：WORDS 起原樣交出
    if "timeout" in opts and "timeout_cycles" in opts:
        raise bad_args(HELP, "--timeout-s and --timeout-cycles are mutually exclusive")
    timeout_cycles = cycles(opts["timeout_cycles"], HELP) if "timeout_cycles" in opts else None
    timeout = DEFAULT_S if opts.get("timeout") is None else seconds(opts["timeout"], HELP, "0 = no limit")
    mailbox = opts.get("mailbox")
    if mailbox == "":
        raise bad_args(HELP, "--mailbox needs a mailbox folder")
    a = target(opts)                                # 同 say：先找對象，沒對象不先等 stdin
    who = sender.sender(opts, HELP)
    text = message(rest, HELP)
    sent = send(a, text, who)
    try:
        wait_sent(a, sent, None if timeout_cycles is not None or timeout == 0 else timeout, timeout_cycles,
                  None if mailbox is None else os.path.abspath(mailbox))
    except KeyboardInterrupt:
        note("that message was sent; read the answer later with aos-agent listen --target %s --letter %s" % (a.name, sent[0]))
        sys.exit(130)
