# aos_agent/chat.py - 逐行寄訊息並等候回答的互動迴圈。
HELP = """aos-agent chat - send one line per message and wait for each answer

usage: aos-agent [--daemon D] chat [-t NAME]

flags:
  -t, --target NAME   which agent (default: $AOS_AGENT)
  -h, --help          show this help

Reads messages from stdin; the prompt goes to stderr and answers go to stdout.
Empty lines are ignored. An error about one message returns to the prompt.
End of stdin exits 0, or 1 if a message failed; Ctrl-C exits 130.

exit codes: 0 done; 1 error (TargetMissing, InstanceMissing, AnswerMissing...); 130 Ctrl-C."""

from . import PROG
import aos_flags
import aos_ws
import sys
from .common import Fail, bad_args, find, note, parse, target
from .listen import wait_latest


def cmd(argv):
    """say＋listen 的迴圈（02「chat 怎麼運作」）：提示符在 stderr、stdout 只有回答；Ctrl-C 退 130、stdin 結束退 0
    （中途印過錯誤行＝退 1：有錯誤行不准退 0，11-05 R1）。"""
    opts, rest = parse(argv, {"--target": "target"}, help=HELP, short=("-t",))
    if rest:
        raise bad_args(HELP, "chat takes no positional arguments: %s (pick the target with --target)" % rest[0])
    a = target(opts)
    note("chatting with %s (Ctrl-C to exit)" % a.name)
    sent, failed = False, False
    try:
        while True:
            sent = False
            sys.stderr.write("> ")
            sys.stderr.flush()
            try:
                line = sys.stdin.buffer.readline().decode("utf-8")   # 一行一行解碼：壞一行不連累前後
            except UnicodeDecodeError:                  # 11-04 夜：這行不是 UTF-8＝印一行、不寄、回提示符
                print(aos_flags.error_line(PROG, "ArgumentsBad", bad_args(HELP, "this line is not UTF-8, not sent")), file=sys.stderr, flush=True)
                failed = True
                continue
            if not line:
                sys.stderr.write("\n")
                sys.exit(1 if failed else 0)
            if not line.strip():
                continue
            a = find(a.name, quiet=True)            # 11-05 edge-agent：聊到一半被 ctl rm --purge＝原本照寄、把刪掉的 stack 建回來、然後一直等
            before = len(aos_ws.answers(a.stack))
            aos_ws.put(a.stack, line)
            sent = True
            try:
                wait_latest(a, None, before)
            except Fail as e:
                if e.code not in ("QuestionUnknown", "AnswerMissing"):
                    raise
                print(aos_flags.error_line(PROG, e.code, e), file=sys.stderr, flush=True)   # 印一行、不退出，回提示符
                failed = True
    except KeyboardInterrupt:
        if sent:
            sys.stderr.write("\n")
            note("that message was sent; read the answer later with aos-agent listen --target %s" % a.name)
        else:
            sys.stderr.write("\n")
        sys.exit(130)
