# aos_agent/say.py - 寄一則訊息到 agent 的 queue。
HELP = """aos-agent say - put one message in the agent's queue

usage: aos-agent [--daemon D] say [--target NAME] [--from WHO] [WORDS...]
       ... | aos-agent [--daemon D] say [--target NAME] [--from WHO]

WORDS are joined with single spaces into one message; flags go before them (from the
first word on everything is the message, -t included). No WORDS (or "-") = the whole of
stdin is the message (one trailing newline dropped); stdin being a terminal = ArgumentsBad.
stdout prints the letter name. A paused or sleeping agent still queues it; a warning says so.

flags:
  -t, --target NAME   which agent (default: $AOS_AGENT)
  --from WHO          the sender's name, shown to an external coding agent with a claude body whose screen is open
                      (default: the listed agent whose stack holds $AOS_STACK, else your login name);
                      its CLI marks the message as not typed by its user. Other agents ignore it.
  -h, --help          show this help

exit codes: 0 queued; 1 error (TargetMissing, InstanceMissing, PostFailed...)."""

import sys
from .common import bad_args, note, parse, target
from .hints import label, on_table, run_hint
from . import sender


def cmd(argv):
    opts, rest = parse(argv, dict({"--target": "target"}, **sender.FLAG), help=HELP, short=("-t",), keep=1)   # 11-10 Q3：WORDS 起原樣交出（訊息裡的 -t 不是旗標）
    a = target(opts)                                # 11-05 edge-agent：先找對象，沒對象不先等 stdin
    who = sender.sender(opts, HELP)                 # 11-13：寄件人（只有 eca 的信帶）
    piped = not rest or rest == ["-"]               # 11-05 使用者「aos-say,aos-listen，我希望能支援stdin/out。」：沒給話或給 -＝整份 stdin 一則
    if piped and (sys.stdin is None or sys.stdin.isatty()):
        raise bad_args(HELP, "no message: give WORDS or pipe it into stdin (stdin is a terminal)")
    try:                                            # 11-04 夜邊緣實測：不是 UTF-8 的話（argv 或 stdin）原本噴 traceback
        if piped:                                   # 照原樣讀 bytes、照 UTF-8 解（不看 locale），去尾端一個換行
            text = sys.stdin.buffer.read().decode("utf-8")
            text = text[:-2] if text.endswith("\r\n") else text[:-1] if text.endswith("\n") else text
        else:
            text = " ".join(rest)
            text.encode("utf-8")
    except UnicodeError:
        raise bad_args(HELP, "the message is not UTF-8")
    if not text.strip():
        raise bad_args(HELP, "the message is empty")
    sig = sender.put(a, text, who)
    print(sig, flush=True)
    if not on_table(a):
        note("queued in %s/queue/new/; nothing is running %s now; %s" % (a.stack, a.name, run_hint(a)))
    elif label(a) == "paused":
        note("queued in %s/queue/new/; %s is paused and will not answer until resumed: aos-agent ctl resume --target %s" % (a.stack, a.name, a.name))
