# aos_agent/listen.py - 等待回答或列出與追蹤歷史對話。
HELP = """aos-agent listen - print the agent's answer

usage: aos-agent [--daemon D] listen [--target NAME] [--timeout-s SECS | --last N [--follow]]

Without --last: wait for the answer to the latest question and print only its text (so
> file and pipes work; notes go to stderr). --last N prints the last N exchanges as blocks:
a line "== #N", the question lines prefixed "> ", then the answer. --follow keeps printing
new ones; Ctrl-C leaves with exit 0.

flags:
  -t, --target NAME   which agent (default: $AOS_AGENT)
  --timeout-s SECS    give up after SECS seconds (AnswerMissing); leave out to wait without limit
  --last N            show the last N exchanges (a whole number) instead of waiting
  -f, --follow        with --last: keep following
  -h, --help          show this help

exit codes: 0 printed; 1 error (AnswerMissing, QuestionUnknown...); 130 Ctrl-C while waiting."""

import aos_ws
import math
import os
import sys
import time
from .common import Fail, bad_args, POLL, daemon_path, note, parse, target
from .hints import daemon_held, label, off_table, on_table, run_hint, stuck_hint


# ---------------------------------------------------------------- 等回答（搬自 extras/human/bin/aos-listen）

def latest(a):
    sigs = aos_ws.names(a.stack, "new") + aos_ws.names(a.stack, "cur")
    return max(sigs, key=aos_ws.letter_key) if sigs else None


def print_answer(a, sig):
    """印 history 最新那則回答；沒有＝sig 是 None 就 QuestionUnknown，否則 AnswerMissing。"""
    got = aos_ws.answers(a.stack)
    if got:
        sys.stdout.write(got[-1] if got[-1].endswith("\n") else got[-1] + "\n")
        sys.stdout.flush()
        return
    if sig is None:
        raise Fail("QuestionUnknown", "no letter in queue/new/ or queue/cur/ and no answer in history")
    if not os.path.isdir(a.stack):                    # 11-05 edge-agent：等的途中被 ctl rm（stack 刪了），原本說「不在 queue、history 沒回答」
        raise Fail("InstanceMissing", "%s was removed (stack %s is gone); %s will never be answered" % (a.name, a.stack, sig))
    raise Fail("AnswerMissing", "%s has left the queue but history has no answer" % sig)


def handed_unanswered(a, before):
    """信不見了、還沒答＝已經收進去、還在答（eca 交出去就收信、fsm 答的途中）：回答沒比開始時多、history 最後一則不是回答；
    或 history 最後一則 user 在最後一則回答之後（11-05 晚：前一題的回答在等的途中才到、回答數變多，原本就把前一題的回答當成這封的印出來）。"""
    rows = aos_ws.history(a.stack)
    if not rows:
        return False
    if len(aos_ws.answers(a.stack)) <= before and not aos_ws.is_answer(rows[-1]):
        return True
    last_user = max((i for i, m in enumerate(rows) if m.get("role") == "user"), default=-1)
    last_answer = max((i for i, m in enumerate(rows) if aos_ws.is_answer(m)), default=-1)
    return last_user > last_answer


def wait_latest(a, timeout, before=None):
    """等最新那封的回答（before＝寄之前的回答數；chat 給，listen 開始時才數）。"""
    sig = latest(a)
    if before is None:
        before = len(aos_ws.answers(a.stack))
    if sig is None and not handed_unanswered(a, before):   # 答案已經到了（或根本沒寄過）：立刻印最新那則回答
        return print_answer(a, None)
    start, warned, paused_said, next_check = time.monotonic(), False, False, 0.0
    new_warned = False
    what = sig or "the latest letter"

    def say_paused():                                 # 11-05 edge-agent：暫停中原本一聲不吭地等
        nonlocal paused_said
        if not paused_said and label(a) == "paused":
            note("%s is paused and will not answer until resumed: aos-agent ctl resume --target %s. Still waiting, Ctrl-C to leave" % (a.name, a.name))
            paused_said = True

    while True:
        stages = [s for s in aos_ws.where(a.stack, sig) if s in ("new", "cur")] if sig else []
        if not stages:
            if not handed_unanswered(a, before):
                return print_answer(a, sig)
            if time.monotonic() >= next_check:
                next_check = time.monotonic() + 1.0
                if on_table(a):
                    say_paused()
                elif handed_unanswered(a, before):
                    if not os.path.isdir(a.stack):
                        raise Fail("InstanceMissing", "%s was removed (stack %s is gone); %s will never be answered" % (a.name, a.stack, what))
                    gone = off_table(a)
                    if gone:
                        raise Fail("AnswerMissing", "%s was handed over but history has no answer: %s" % (what, gone))
                    if daemon_held(a):                # 停著／睡著（答到一半被 stop、sleep）：照等，它回來可能接著答（11-05 edge-agent）
                        if not warned:
                            note("%s was handed over and is not answered yet; %s is not running now. %s. Still waiting, Ctrl-C to leave" % (what, a.name, run_hint(a)))
                            warned = True
                    else:
                        raise Fail("AnswerMissing", "%s was handed over (not in the queue) but history has no answer and nothing is running %s"
                                   " (a batch cut off midway is not answered again by itself; say it again for a new answer)" % (what, a.name))
            if timeout is not None and time.monotonic() - start >= timeout:
                raise Fail("AnswerMissing", "waited %g s; %s was handed over and is not answered yet" % (timeout, what))
            time.sleep(POLL)
            continue
        now = time.monotonic()
        if not new_warned and "new" in stages and now - start >= 10 and on_table(a) and a.phase == "running" and label(a) != "paused":   # 暫停中已另有一句
            note("%s has not been taken from queue/new/ after 10 s; %s may be busy, or its daemon may be down: aos-daemon-ctl --daemon %s ls (the last line shows what the daemon's supervisor sees)" % (sig, a.name, daemon_path()))
            new_warned = True
        if now >= next_check:
            next_check = now + 1.0
            if on_table(a):
                warned = False
                say_paused()
            elif not os.path.isdir(a.stack):
                raise Fail("InstanceMissing", "%s was removed (stack %s is gone); %s will never be answered" % (a.name, a.stack, sig))
            elif not warned:
                note(stuck_hint(a, sig) + ". Still waiting, Ctrl-C to leave")
                warned = True
        if timeout is not None and now - start >= timeout:
            raise Fail("AnswerMissing", "waited %g s; %s is not answered yet (the letter is in queue/%s/)" % (timeout, sig, ", ".join(stages)))
        time.sleep(POLL)


def block(n, asked, answer):
    out = "== #%d\n" % n
    for q in asked:
        out += "".join("> %s\n" % l for l in q.rstrip("\n").splitlines())
    return out + answer + ("" if answer.endswith("\n") else "\n")


def follow(a, last, keep):
    ex = aos_ws.exchanges(a.stack)
    seen = len(ex)
    for i in range(max(0, seen - last), seen) if last else []:
        sys.stdout.write(block(i + 1, *ex[i]))
    sys.stdout.flush()
    if not keep:
        return
    warned, next_check = False, 0.0
    while True:
        ex = aos_ws.exchanges(a.stack)
        if len(ex) < seen:                            # history 被 compact 換短了：從現在的尾巴接著看
            seen = len(ex)
        for i in range(seen, len(ex)):
            sys.stdout.write(block(i + 1, *ex[i]))
        seen = len(ex)
        sys.stdout.flush()
        now = time.monotonic()
        if now >= next_check:
            next_check = now + 1.0
            waiting = aos_ws.waiting(a.stack)
            if not waiting or on_table(a):
                warned = False
            elif not warned:
                note("%d letters in the queue are not answered (%s), but nothing is running %s now; %s. Still waiting, Ctrl-C to leave"
                     % (len(waiting), ", ".join(waiting[:3]) + ("..." if len(waiting) > 3 else ""), a.name, run_hint(a)))
                warned = True
        time.sleep(POLL)


def seconds(v):
    """--timeout-s：有限、不小於 0 的秒數；不給旗標才是不設上限（inf／1e999／nan 都擋，E1）。"""
    try:
        n = float(v)
        if not math.isfinite(n) or n < 0:
            raise ValueError
    except ValueError:
        raise bad_args(HELP, "--timeout-s needs a finite number of seconds not below 0 (leave it out to wait without limit): %s" % v)
    return n


def count(v):
    """--last：不小於 0 的整數（1.5、inf 不收，E1）。"""
    try:
        n = int(v)
        if n < 0:
            raise ValueError
    except ValueError:
        raise bad_args(HELP, "--last needs a whole number not below 0: %s" % v)
    return n


def cmd(argv):
    opts, rest = parse(argv, {"--target": "target", "--timeout-s": "timeout", "--last": "last"}, {"--follow": "follow"}, help=HELP, short=("-t", "-f"))
    timeout = None if opts.get("timeout") is None else seconds(opts["timeout"])
    last = None if opts.get("last") is None else count(opts["last"])
    if rest:
        raise bad_args(HELP, "listen takes no positional arguments: %s (it always waits for the latest letter)" % rest[0])
    waits = last is None and not opts.get("follow")
    if not waits and timeout is not None:
        raise bad_args(HELP, "--timeout-s is only for waiting on the latest letter, not with --last / --follow")
    a = target(opts)
    try:
        if waits:
            wait_latest(a, timeout)
        else:
            follow(a, last or 0, bool(opts.get("follow")))
    except KeyboardInterrupt:
        sys.exit(130 if waits else 0)
