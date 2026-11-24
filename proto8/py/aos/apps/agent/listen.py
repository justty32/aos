# aos/apps/agent/listen.py - 以秒或 cycle 等待回答（給信名就配那封），或列出與追蹤歷史對話。
HELP = """aos-agent listen - print the agent's answer

usage: aos-agent [--daemon D] listen [--target NAME] [--letter NAME] [--mailbox DIR] [--timeout-s SECS | --timeout-cycles N | --last N [--follow] | --follow]

Without --last or --follow: wait for an answer and print only its text.
--letter NAME waits for the answer to that letter (the name aos-agent say printed). Without it:
the newest letter still in the queue, else the last letter the agent took and has not answered
(letters.json), else the latest answer (waiting for it if the agent is still answering).
An agent whose body does not record letter names yet (no aos.letter in its history) is matched
the old way: the latest answer, with a warning on stderr.
While a handed-over letter waits, a failed brain call (the stack's cooldown.json) is said once on
stderr with the error lines from the agent's stderr file; if the agent stopped on that error,
listen ends at once with AnswerMissing and those lines instead of waiting for the timeout.
--mailbox DIR also watches that mailbox (yours: the agent may answer with a letter there, e.g. BLOCKED;
a folder that does not exist yet is watched until it does):
a letter in it whose in_reply_to is the letter waited for ends the wait (exit 0); stdout says so and
gives its status, title and text; the letter stays in the mailbox.
--last N prints the last N exchanges as blocks: "== #N", question lines prefixed "> ",
then the answer. --follow prints new exchanges; add --last N to show history first.
Ctrl-C leaves follow mode with exit 0; reminders go to stderr.

flags:
  -t, --target NAME   which agent (default: $AOS_AGENT, else ./.stack or ./)
  --letter NAME       wait for the answer to this letter (not with --last / --follow)
  --mailbox DIR       also end on a letter in DIR that answers it (in_reply_to); not with --last / --follow
  --timeout-s SECS    give up after SECS seconds (AnswerMissing); 0 = no limit; omitted = no limit
  --timeout-cycles N  give up after N cycles (positive integer); exclusive with --timeout-s
  --last N            show the last N exchanges (a whole number) instead of waiting
  -f, --follow        follow new exchanges (also with --last)
  -h, --help          show this help

exit codes: 0 printed; 1 error (AnswerMissing, LetterDropped, QuestionUnknown...); 130 Ctrl-C while waiting."""

from aos import flags as aos_flags
from aos import ws as aos_ws
import json
import math
import os
import sys
import time
from .common import Fail, bad_args, POLL, daemon_path, note, parse, target, via_kernel
from .hints import brain_failure, brain_hint, daemon_held, failure_text, label, off_table, on_table, run_hint, stuck_hint


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
    if not os.path.isdir(a.stack):                    # 11-05 edge-agent：等的途中被 ctl rm --purge（stack 刪了），原本說「不在 queue、history 沒回答」
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


DROP_WHY = {"bad": "it was not a valid message", "blocked": "a before_queue hook blocked it",
            "failed": "the agent failed after it was handed over"}


def plain_user(m):
    """舊身體寫的信列：user、沒有 aos 鍵、不是 aos 自己寫的（[aos] 開頭）。"""
    return m.get("role") == "user" and "aos" not in m and not aos_ws.text_of(m).startswith("[aos] ")


def old_body(a, before_rows):
    """退路的判定（reply-match 03 §5）：history[before_rows:] 有舊身體的信列＝收這封的身體還沒升級（不寫 aos.letter）。"""
    return any(plain_user(m) for m in aos_ws.history(a.stack)[before_rows:])


def print_text(text):
    sys.stdout.write(text if text.endswith("\n") else text + "\n")
    sys.stdout.flush()


def mail_reply(box, sig):
    """box（aos-post 信箱）的 new/、cur/ 裡 in_reply_to 是 sig 的第一封 → (信名, letter.json 的內容)；沒有＝None。讀不懂的信略過。"""
    for stage in ("new", "cur"):
        here = os.path.join(box, stage)
        try:
            names_ = sorted(n for n in os.listdir(here) if not n.startswith("."))
        except OSError:
            continue
        for n in names_:
            try:
                got = json.loads(aos_ws.read(os.path.join(here, n, "letter.json"), ""))
            except ValueError:
                continue
            if isinstance(got, dict) and got.get("in_reply_to") == sig:
                return n, got
    return None


def print_mail(a, sig, box, name, letter):
    """11-24 晚（home-listen-1124，narr-amber 回報②）：對方用信回了（例 BLOCKED），不是 history 裡的回答——照樣結束等待、說清楚。"""
    body = letter.get("body") if isinstance(letter.get("body"), dict) else {"what": letter.get("body")}
    one = lambda v: " ".join(str(v).split()) if v is not None else "-"
    head = aos_flags.aos_note("listen", "%s answered %s with a letter in %s, not with a reply: %s \"%s\" (letter %s; it stays there, read it with mailbox_read)"
                       % (a.name, sig, box, one(body.get("status")), one(body.get("title")), name))
    what = body.get("what")
    print_text(head + ("\n" + str(what) if what not in (None, "") else ""))


def wait_latest(a, timeout, before=None, *, timeout_cycles=None, letter=None, before_rows=None, mailbox=None):
    """等一封信的回答（before＝寄之前的回答數；ask／chat 給，listen 開始時才數；reply-match-1114 03 §2、§5）。
    letter 給了（ask、chat、listen --letter）＝只認 aos_ws.answer_for 配到這封的回答；離開 queue 後查無紀錄（unknown）時，
    history[before_rows:] 有舊身體的信列才退回舊配法（還在答就等、回答數比 before 多才印最新那則），stderr 說一句；
    before_rows＝寄之前 history 的列數，沒給＝信還在 queue 就現在數，不然從頭找（此時不要求回答變多，同現行 listen）。
    letter 沒給（listen）＝等 queue 最新那封，queue 空就等 letters.json pending 最後那封，都配信名；查無紀錄＝照舊配法、不另說；
    都沒有＝現行規則（還在答就等新回答，不然印最新那則）。
    mailbox＝也看這個信箱（叫的人自己的）：有 in_reply_to 是這封的信＝印那封的摘要、結束（print_mail）。"""
    deadline = aos_ws.deadline_after(timeout_cycles) if timeout_cycles is not None else None
    duration = "%d cycles" % timeout_cycles if deadline is not None else "%g s" % timeout if timeout is not None else ""

    def timed_out():
        return aos_ws.expired(deadline) if deadline is not None else timeout is not None and time.monotonic() - start >= timeout

    strict = letter is not None
    sig = letter if strict else latest(a)
    if sig is None:
        pending = aos_ws.letters_pending(a.stack)
        sig = pending[-1] if pending else None
    if before is None:
        before = len(aos_ws.answers(a.stack))
    late = False
    if strict and before_rows is None:
        if set(aos_ws.where(a.stack, sig)) & {"new", "cur"}:
            before_rows = len(aos_ws.history(a.stack))
        else:
            before_rows, late = 0, True
    if sig is None and not handed_unanswered(a, before):   # 答案已經到了（或根本沒寄過）：立刻印最新那則回答
        return print_answer(a, None)
    start, warned, paused_said, next_check = time.monotonic(), False, False, 0.0
    new_warned = False
    brain_warned = False
    what = sig or "the latest letter"
    state, old = None, False                          # state＝answer_for 最後看到的；old＝這封已退回舊配法
    next_mail = 0.0

    def mailed():
        """mailbox 給了：每秒看一次有沒有回這封的信；有＝印、回 True。"""
        nonlocal next_mail
        if mailbox is None or sig is None or time.monotonic() < next_mail:
            return False
        next_mail = time.monotonic() + 1.0
        hit = mail_reply(mailbox, sig)
        if hit:
            print_mail(a, sig, mailbox, *hit)
            return True
        return False

    def say_brain():
        nonlocal brain_warned
        if not brain_warned:
            h = brain_hint(a)
            if h:
                note(h + ". Still waiting, Ctrl-C to leave")
                brain_warned = True

    def timeout_reason(reason):
        h = brain_hint(a)
        f = brain_failure(a)                          # small-1118：逾時的錯誤行帶上最後一次問腦失敗的原話
        return reason + ("; " + h if h else "") + ("; %s's last brain call failed: %s" % (a.name, failure_text(f)) if f else "")

    failure_said = False

    def check_failure():
        """small-1118（使用者 11-18 小題一包「listen 出錯時把理由帶出來」）：信交出去還沒答時看問腦失敗紀錄（hints.brain_failure）。
        身體停在這個錯上（例：端點回 400，fsm 記冷卻後退 1）＝現在就結束，AnswerMissing 帶原因，不乾等到逾時；
        只是冷卻中、會自己重送的（retry true 等）＝提醒一次、照等。"""
        nonlocal failure_said
        if not (state == "handed" or old or sig is None):
            return
        f = brain_failure(a)
        if not f:
            return
        if f["stopped"]:
            if a.row.get("auto_restart") is True:
                nxt = "the daemon restarts %s and it sends the same request again after the cooldown" % a.name
            else:
                nxt = "fix the cause, then start it again: aos-agent ctl start --target %s" % a.name
            later = "; read the answer later with aos-agent listen --target %s --letter %s" % (a.name, sig) if sig else ""
            raise Fail("AnswerMissing", "%s was handed over, but %s stopped on an error before answering: %s; %s%s"
                       % (what, a.name, failure_text(f), nxt, later))
        if not failure_said:
            note("%s's last brain call failed: %s; it sends the request again by itself when the cooldown ends. Still waiting, Ctrl-C to leave"
                 % (a.name, failure_text(f)))
            failure_said = True

    def say_paused():                                 # 11-05 edge-agent：暫停中原本一聲不吭地等
        nonlocal paused_said
        if not paused_said and label(a) == "paused":
            note("%s is paused and will not answer until resumed: aos-agent ctl resume --target %s. Still waiting, Ctrl-C to leave" % (a.name, a.name))
            paused_said = True

    def matched():
        """配信名：回 True＝已印回答；LetterDropped 直接丟；否則更新 state／old、回 False（還要等）。"""
        nonlocal state, old
        state, text = aos_ws.answer_for(a.stack, sig)
        if state in ("answered", "answered_removed"):
            if state == "answered_removed":
                note("this answer to %s was moved out of history (found in %s)" % (sig, aos_ws.REMOVED))
            print_text(text)
            return True
        if state == "dropped":
            raise Fail("LetterDropped", "%s will not be answered: %s dropped it (%s: %s); say it again for a new answer"
                       % (sig, a.name, text, DROP_WHY.get(text, "no reason given")))
        if state == "unknown" and not old and (not strict or old_body(a, before_rows)):
            old = True
            if strict:
                note("%s's body is not upgraded yet (no aos.letter), so this time the answer is matched the old way: "
                     "it is the latest answer, not necessarily the one to %s" % (a.name, sig))
        if state == "unknown" and old and not handed_unanswered(a, before) and (not strict or late or len(aos_ws.answers(a.stack)) > before):
            print_answer(a, sig)
            return True
        return False

    while True:
        stages = [s for s in aos_ws.where(a.stack, sig) if s in ("new", "cur")] if sig else []
        if mailed():
            return
        if not stages:
            if sig is None:
                if not handed_unanswered(a, before):
                    return print_answer(a, sig)
            elif matched():
                return
            if time.monotonic() >= next_check:
                next_check = time.monotonic() + 1.0
                check_failure()
                if on_table(a):
                    say_paused()
                    say_brain()
                elif sig is not None or handed_unanswered(a, before):
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
            if timed_out():
                if strict and state == "unknown" and not old:
                    reason = ("waited %s; %s has left the queue but has no record in history or letters.json (last state: unknown;"
                              " %s's body may not be upgraded yet, or the letter name is wrong)" % (duration, what, a.name))
                else:
                    reason = "waited %s; %s was handed over and is not answered yet" % (duration, what)
                    if strict:
                        reason += " (last state: %s)" % ("unknown, matched the old way" if old else state)
                raise Fail("AnswerMissing", timeout_reason(reason))
            time.sleep(POLL)
            continue
        now = time.monotonic()
        if not new_warned and "new" in stages and now - start >= 10 and on_table(a) and a.phase in {"running", "stuck"} and label(a) != "paused":   # 暫停中已另有一句
            if via_kernel():
                note("%s has not been taken from queue/new/ after 10 s; %s may be busy, or its daemon may be down: aos-agent ctl ls" % (sig, a.name))
            else:
                note("%s has not been taken from queue/new/ after 10 s; %s may be busy, or its daemon may be down: aos-daemon-ctl --daemon %s ls (the last line shows what the daemon's supervisor sees)" % (sig, a.name, daemon_path()))
            new_warned = True
        if now >= next_check:
            next_check = now + 1.0
            if on_table(a):
                warned = False
                say_paused()
                say_brain()
            elif not os.path.isdir(a.stack):
                raise Fail("InstanceMissing", "%s was removed (stack %s is gone); %s will never be answered" % (a.name, a.stack, sig))
            elif not warned:
                note(stuck_hint(a, sig) + ". Still waiting, Ctrl-C to leave")
                warned = True
        if timed_out():
            raise Fail("AnswerMissing", timeout_reason("waited %s; %s is not answered yet (the letter is in queue/%s/)" % (duration, sig, ", ".join(stages))))
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


def seconds(v, help=HELP, hint="leave it out to wait without limit"):
    """--timeout-s：有限、不小於 0 的秒數；0 或不給旗標＝不設上限（inf／1e999／nan 都擋，E1）。help＝錯誤行的 usage 用誰的（ask 共用）。"""
    try:
        n = float(v)
        if not math.isfinite(n) or n < 0:
            raise ValueError
    except ValueError:
        raise bad_args(help, "--timeout-s needs a finite number of seconds not below 0 (%s): %s" % (hint, v))
    return n


def cycles(raw, help=HELP):
    """--timeout-cycles：正的十進位整數、不超過 signed 64-bit（ask 共用）。"""
    if not raw or any(c < "0" or c > "9" for c in raw) or len(raw.lstrip("0")) > 19:
        raise bad_args(help, "--timeout-cycles needs a positive decimal integer within signed 64-bit range: %s" % raw)
    n = int(raw.lstrip("0") or "0")
    if not 0 < n <= 9223372036854775807:
        raise bad_args(help, "--timeout-cycles needs a positive decimal integer within signed 64-bit range: %s" % raw)
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
    opts, rest = parse(argv, {"--target": "target", "--letter": "letter", "--timeout-s": "timeout", "--timeout-cycles": "timeout_cycles", "--last": "last",
                              "--mailbox": "mailbox"},
                       {"--follow": "follow"}, help=HELP, short=("-t", "-f"))
    if "timeout" in opts and "timeout_cycles" in opts:
        raise bad_args(HELP, "--timeout-s and --timeout-cycles are mutually exclusive")
    timeout_cycles = cycles(opts["timeout_cycles"]) if "timeout_cycles" in opts else None
    timeout = None if opts.get("timeout") is None else seconds(opts["timeout"])
    last = None if opts.get("last") is None else count(opts["last"])
    if rest:
        raise bad_args(HELP, "listen takes no positional arguments: %s (to wait for one letter use --letter NAME)" % rest[0])
    waits = last is None and not opts.get("follow")
    if not waits and ("timeout" in opts or timeout_cycles is not None):
        raise bad_args(HELP, "--timeout-s / --timeout-cycles are only for waiting on a letter, not with --last / --follow")
    letter = opts.get("letter")
    if letter is not None and not waits:
        raise bad_args(HELP, "--letter is only for waiting on a letter, not with --last / --follow")
    mailbox = opts.get("mailbox")
    if mailbox is not None and not waits:
        raise bad_args(HELP, "--mailbox is only for waiting on a letter, not with --last / --follow")
    if mailbox == "":
        raise bad_args(HELP, "--mailbox needs a mailbox folder")
    if letter is not None and (not letter or "/" in letter or letter.startswith(".")):
        raise bad_args(HELP, "--letter needs a letter name as aos-agent say printed it (no / and not starting with .): %s" % letter)
    a = target(opts)
    try:
        if waits:
            wait_latest(a, None if timeout == 0 else timeout, timeout_cycles=timeout_cycles, letter=letter,
                        mailbox=None if mailbox is None else os.path.abspath(mailbox))
        else:
            follow(a, last or 0, bool(opts.get("follow")))
    except KeyboardInterrupt:
        sys.exit(130 if waits else 0)
