# aos_agent/say.py - 寄一則訊息到 agent 的 queue。
import aos_ws
import sys
from .common import Fail, note, parse, target
from .hints import label, on_table, run_hint


def cmd(argv):
    opts, rest = parse(argv, {"--target": "target"})
    a = target(opts)                                # 11-05 edge-agent：先找對象，沒對象不先等 stdin
    piped = not rest or rest == ["-"]               # 11-05 使用者「aos-say,aos-listen，我希望能支援stdin/out。」：沒給話或給 -＝整份 stdin 一則
    if piped and (sys.stdin is None or sys.stdin.isatty()):
        raise Fail("ArgumentsBad", "no message: give WORDS or pipe it into stdin (stdin is a terminal; usage: aos-agent say [--target NAME] [WORDS...|-])")
    try:                                            # 11-04 夜邊緣實測：不是 UTF-8 的話（argv 或 stdin）原本噴 traceback
        if piped:                                   # 照原樣讀 bytes、照 UTF-8 解（不看 locale），去尾端一個換行
            text = sys.stdin.buffer.read().decode("utf-8")
            text = text[:-2] if text.endswith("\r\n") else text[:-1] if text.endswith("\n") else text
        else:
            text = " ".join(rest)
            text.encode("utf-8")
    except UnicodeError:
        raise Fail("ArgumentsBad", "the message is not UTF-8")
    if not text.strip():
        raise Fail("ArgumentsBad", "the message is empty (aos-agent say [--target NAME] [WORDS...|-])")
    sig = aos_ws.put(a.stack, text)
    print(sig, flush=True)
    if not on_table(a):
        note("queued in %s/queue/new/; nothing is running %s now; %s" % (a.stack, a.name, run_hint(a)))
    elif label(a) == "paused":
        note("queued in %s/queue/new/; %s is paused and will not answer until resumed: aos-agent ctl resume --target %s" % (a.stack, a.name, a.name))
