# aos_mailbox/__init__.py - aos-mailbox 本體：找我的 stack、四個子命令（where、peek、read、send）、叫 aos-post 命令列。
# 設計與代定：proto8/thinking/2026-11/10/mailbox/01-設計.md。信箱＝<stack>/mailbox/（aos-post 的 tmp/ new/ cur/，留著的進 archive/）。
# peek 只讀 new/*/letter.json（aos-post 沒有只看不拿的子命令）；其餘都交給 aos-post（init、send、take、see、done）。
import json
import os
import re
import subprocess
import sys

import aos_flags
import daemon_ctl as dc

PROG = "aos-mailbox"
STATUSES = ("REQUEST", "DONE", "BLOCKED", "NEEDS-USER", "FAILED", "PROGRESS")
SECTIONS = ("what", "outputs", "not_done", "decide")
BOX = "mailbox"
ORDERED = re.compile(r"^[0-9]{12}\.")
TIMEOUT_S = 30

HELP = """aos-mailbox - my mailbox: send letters to agents, see and read the letters sent to me

usage: aos-mailbox [-s STACK] SUBCOMMAND [FLAGS...] [ARGS...]
       aos-mailbox SUBCOMMAND --help

subcommands:
  where   print my mailbox folder (create it if missing)
  peek    list waiting letters without taking them: LETTER TAB FROM TAB STATUS TAB TITLE
  read    take the oldest letter, print it, then remove it (--keep: keep it in archive/)
  send    send a letter to an agent (--to NAME [-d DAEMON]) or to a mailbox folder (--box PATH)

flags:
  -s, --stack STACK   my stack folder (default: $AOS_LINUX_USER_STACK, else ~/.aos/stack); the mailbox is STACK/mailbox
  -h, --help          show this help
Flags may go anywhere after the name they belong to (-s also after the subcommand);
send's WHAT and everything after it is text.

A letter follows the inbox protocol: from, to, status (REQUEST DONE BLOCKED NEEDS-USER FAILED PROGRESS),
a one-line title that makes sense alone, and four parts: what, outputs, not_done, decide.
Letters are information and requests, not orders.
exit codes: 0 ok; 10 read found no letter; 1 error ("aos-mailbox: error: CODE reason" on stderr).
more: proto8/cmd/aos-mailbox/README.md"""

HELPS = {
    "where": """aos-mailbox where - print my mailbox folder

usage: aos-mailbox [-s STACK] where

Create STACK/mailbox (tmp/, new/, cur/) if it is missing, then print its absolute path.""",
    "peek": """aos-mailbox peek - list the letters waiting in my mailbox

usage: aos-mailbox [-s STACK] peek [-j]

flags:
  -j, --json   one JSON array of {letter, from, to, status, title, sent_at}

One line per letter, oldest first: LETTER TAB FROM TAB STATUS TAB TITLE (? = unreadable).
Letters stay where they are. No letters (or no mailbox yet) = no output, exit 0.""",
    "read": """aos-mailbox read - read the oldest letter in my mailbox

usage: aos-mailbox [-s STACK] read [--all] [--keep] [-j]

flags:
  --all        read every waiting letter
  --keep       keep what was read in STACK/mailbox/archive/ (default: remove it)
  -j, --json   one JSON object per letter per line

A letter left half-read by a crash is read first. To answer, send to its reply_to:
  aos-mailbox send --box REPLY_TO --in-reply-to LETTER --status DONE --title "..." "..."
exit codes: 0 read; 10 no letter; 1 error.""",
    "send": """aos-mailbox send - send one letter

usage: aos-mailbox [-s STACK] send (--to NAME [-d DAEMON] | --box PATH) --status STATUS --title TITLE
                   [--outputs TEXT] [--not-done TEXT] [--decide TEXT] [--in-reply-to LETTER]
                   [--from NAME] WHAT...|-

flags:
  --to NAME             the agent's name on a daemon table; its mailbox is created if missing
  -d, --daemon DAEMON   that daemon's stack folder (default: $AOS_DAEMON, else ./.stack)
  --box PATH            a mailbox folder (must already have tmp/, new/, cur/)
  --status STATUS       REQUEST, DONE, BLOCKED, NEEDS-USER, FAILED or PROGRESS
  --title TITLE         one line that makes sense on its own
  --outputs TEXT        files, commits, results (default: none)
  --not-done TEXT       what is missing or unproven (default: none)
  --decide TEXT         what the receiver or the user must decide (default: none)
  --in-reply-to LETTER  the letter this answers
  --from NAME           my name (default: $USER, else user)

WHAT is the main part (for REQUEST: what the receiver should do); - reads it from stdin.
Flags go before WHAT (from WHAT on everything is text).
Replies go to my mailbox (STACK/mailbox). Prints the sent letter's name.
Rules: when a task ends send DONE, BLOCKED, NEEDS-USER or FAILED; stuck over 10 minutes = send BLOCKED.""",
}


class Fail(Exception):
    def __init__(self, code, msg):
        super().__init__(msg)
        self.code = code


def parse(argv, sub, flags=None, switches=None, short=(), keep=None):
    """子命令的旗標；-s/--stack 寫在子命令前後都收，前後不同＝ArgumentsBad（同 aos-agent 的 -t，坑-68）。"""
    global STACK
    try:
        opts, rest = aos_flags.parse(argv, dict(flags or {}, **{"--stack": "stack"}), switches or {}, help=HELPS[sub],
                                     short=tuple(short) + ("-s",), keep=keep)
    except aos_flags.Error as e:
        raise Fail(e.code, "%s (see aos-mailbox %s --help)" % (e, sub))
    s = opts.get("stack")
    if s and STACK and s != STACK:
        raise Fail("ArgumentsBad", "two different stacks: %s before the subcommand, %s after it; give --stack once" % (STACK, s))
    STACK = s or STACK
    return opts, rest


# ---- 我的 stack 與信箱 -------------------------------------------------------------

STACK = None   # main 從 --stack 定


def my_stack():
    # 預設 ~/.aos/stack（使用者 11-11 裁「改成帶 aos 字樣的位置」→「~/.aos/stack」；原本 ~/.stack）
    s = STACK or os.environ.get("AOS_LINUX_USER_STACK", "") or os.path.join(os.path.expanduser("~"), ".aos", "stack")
    return os.path.abspath(s)


def my_box(create):
    box = os.path.join(my_stack(), BOX)
    if create and not is_box(box):
        try:
            os.makedirs(my_stack(), exist_ok=True)
        except OSError as e:
            raise Fail("StackMissing", "cannot create my stack %s: %s" % (my_stack(), e))
        post("init", box)
    return box


def is_box(path):
    return all(os.path.isdir(os.path.join(path, d)) for d in ("tmp", "new", "cur"))


def post(*args, body=None, ok=(0,)):
    """aos-post args…：寄件身分＝我的 stack（清掉 $AOS_WS、設 $AOS_STACK）。回 (退出碼, stdout)；退 1＝它的錯誤行原樣轉。"""
    env = dict(os.environ, AOS_STACK=my_stack())
    env.pop("AOS_WS", None)
    try:
        p = subprocess.run(["aos-post"] + list(args), input=body if body is not None else "", capture_output=True,
                           text=True, env=env, timeout=TIMEOUT_S)
    except OSError as e:
        raise Fail("LaunchFailed", "cannot run aos-post (put it on PATH with proto8/install.sh): %s" % e)
    except subprocess.TimeoutExpired:
        raise Fail("LaunchFailed", "aos-post %s took over %d s" % (args[0], TIMEOUT_S))
    if p.returncode not in ok:
        m = [re.match(r"aos-post: error: ([A-Za-z]+) (.*)", line) for line in p.stderr.splitlines()]
        m = [x for x in m if x]
        if m:
            raise Fail(m[-1].group(1), m[-1].group(2))
        raise Fail("CommandFailed", "aos-post %s exited %d" % (args[0], p.returncode))
    for line in p.stderr.splitlines():
        if line.startswith("aos-post: warning:"):
            print(line, file=sys.stderr)
    return p.returncode, p.stdout


def order(names):
    """aos-post 的處理順序：有序在前、無序在後，各自照名字排；. 開頭不算信。"""
    names = [n for n in names if not n.startswith(".")]
    return sorted(names, key=lambda n: (0 if ORDERED.match(n) else 1, n))


def letters_in(folder):
    try:
        return order(os.listdir(folder))
    except OSError:
        return []


def load(path):
    try:
        with open(path, encoding="utf-8") as f:
            v = json.load(f)
        return v if isinstance(v, dict) else None
    except (OSError, ValueError):
        return None


def one_line(v):
    return "?" if v is None else str(v).replace("\t", " ").replace("\n", " ")


# ---- 子命令 -------------------------------------------------------------------

def cmd_where(argv):
    opts, rest = parse(argv, "where")
    if rest:
        raise Fail("ArgumentsBad", "where takes no arguments (usage: aos-mailbox where)")
    print(my_box(True))


def cmd_peek(argv):
    opts, rest = parse(argv, "peek", switches={"--json": "json"}, short=("-j",))
    if rest:
        raise Fail("ArgumentsBad", "peek takes no arguments (usage: aos-mailbox peek [-j])")
    new = os.path.join(my_box(False), "new")
    rows = []
    for name in letters_in(new):
        letter = load(os.path.join(new, name, "letter.json")) or {}
        body = letter.get("body") if isinstance(letter.get("body"), dict) else {}
        rows.append({"letter": name, "from": body.get("from"), "to": body.get("to"), "status": body.get("status"),
                     "title": body.get("title"), "sent_at": letter.get("sent_at")})
    if opts.get("json"):
        print(json.dumps(rows, ensure_ascii=False))
        return
    for r in rows:
        print("\t".join([r["letter"], one_line(r["from"]), one_line(r["status"]), one_line(r["title"])]))


def flat(box, name, letter):
    """信封＋body 攤平給人看；reply_to 拼回絕對（aos-post 存成相對收件信箱的根）。"""
    body = letter.get("body") if isinstance(letter.get("body"), dict) else {"what": letter.get("body")}
    reply = letter.get("reply_to")
    if isinstance(reply, str):
        reply = os.path.normpath(os.path.join(box, reply))
    out = {"letter": name, "sender": letter.get("sender"), "sent_at": letter.get("sent_at"), "reply_to": reply,
           "in_reply_to": letter.get("in_reply_to")}
    for k in ("from", "to", "status", "title") + SECTIONS:
        out[k] = body.get(k)
    for k, v in body.items():          # 不認得的鍵照印（別的程式寄來的信）
        out.setdefault(k, v)
    return out


def show(r):
    keys = ["letter", "from", "to", "status", "title"] + list(SECTIONS) + ["sent_at", "reply_to", "in_reply_to", "sender"]
    keys += [k for k in r if k not in keys]
    for k in keys:
        if r.get(k) is not None or k in ("from", "status", "title", "what"):
            v = r.get(k)
            print("%s: %s" % (k, "?" if v is None else (v if isinstance(v, str) else json.dumps(v, ensure_ascii=False))))


def cmd_read(argv):
    opts, rest = parse(argv, "read", switches={"--all": "all", "--keep": "keep", "--json": "json"}, short=("-j",))
    if rest:
        raise Fail("ArgumentsBad", "read takes no arguments (usage: aos-mailbox read [--all] [--keep] [-j])")
    box = my_box(False)
    if not is_box(box):
        return 10
    done = ["done"] + (["--keep"] if opts.get("keep") else [])
    count = 0
    while True:
        cur = letters_in(os.path.join(box, "cur"))
        if cur:
            name = cur[0]
        else:
            code, out = post("take", box, ok=(0, 10))
            if code == 10:
                break
            name = out.strip()
        code, out = post("see", box, name, ok=(0, 1, 10))
        if code != 0:   # 壞信：aos-post done 丟掉（不管 --keep）
            aos_flags.warn(PROG, "letter %s is unreadable and was dropped" % name)
            post("done", box, name, ok=(0, 10))
            continue
        r = flat(box, name, json.loads(out))
        if opts.get("json"):
            print(json.dumps(r, ensure_ascii=False))
        else:
            if count:
                print()
            show(r)
        sys.stdout.flush()
        post(*(done + [box, name]), ok=(0, 10))
        count += 1
        if not opts.get("all"):
            break
    return 0 if count else 10


def target_box(opts):
    to, path = opts.get("to"), opts.get("box")
    if bool(to) == bool(path):
        raise Fail("ArgumentsBad", "give --to NAME or --box PATH, one of them (see aos-mailbox send --help)")
    if path:
        if opts.get("daemon"):
            raise Fail("ArgumentsBad", "--daemon goes with --to NAME, not with --box")
        box = os.path.abspath(path)
        if not os.path.isdir(box):
            raise Fail("MailboxMissing", "mailbox not found: %s" % box)
        if not is_box(box):
            raise Fail("MailboxBad", "%s is not a mailbox (it needs tmp/, new/ and cur/ folders)" % box)
        return box, box
    try:
        d = dc.find_daemon(opts.get("daemon"))
        row = dc.row_of(d, to)
    except dc.Fail as e:
        raise Fail({"ProcMissing": "InstanceMissing"}.get(e.code, e.code), str(e))
    stack = row.get("stack")
    if not isinstance(stack, str) or not os.path.isdir(stack):
        raise Fail("InstanceMissing", "%s has no stack folder on the daemon table" % to)
    box = os.path.join(stack, BOX)
    if not is_box(box):
        post("init", box)
    return box, to


def cmd_send(argv):
    flags = {"--to": "to", "--daemon": "daemon", "--box": "box", "--status": "status", "--title": "title",
             "--outputs": "outputs", "--not-done": "not_done", "--decide": "decide",
             "--in-reply-to": "in_reply_to", "--from": "from"}
    opts, rest = parse(argv, "send", flags, short=("-d",), keep=1)   # 11-10 cli-sweep Q3：WHAT 起原樣收
    status = opts.get("status")
    if not status:
        raise Fail("ArgumentsBad", "missing --status (one of %s)" % ", ".join(STATUSES))
    if status not in STATUSES:
        raise Fail("StatusBad", "status must be one of %s (got %r)" % (", ".join(STATUSES), status))
    title = (opts.get("title") or "").strip()
    if not title or "\n" in title:
        raise Fail("ArgumentsBad", "--title needs one non-empty line that makes sense on its own")
    if rest == ["-"]:
        what = sys.stdin.read()
    else:
        what = " ".join(rest)
    if not what.strip():
        raise Fail("ArgumentsBad", "missing WHAT, the main part of the letter (for REQUEST: what to do); - reads stdin")
    box, to = target_box(opts)
    mine = my_box(True)
    body = {"from": opts.get("from") or os.environ.get("USER") or "user", "to": to, "status": status, "title": title,
            "what": what.strip()}
    for k in SECTIONS[1:]:
        v = opts.get(k)
        body[k] = v.strip() if v and v.strip() else "none"
    args = ["send", "--reply-to", mine]
    if opts.get("in_reply_to"):
        args += ["--in-reply-to", opts["in_reply_to"]]
    _, out = post(*(args + [box]), body=json.dumps(body, ensure_ascii=False))
    print(out.strip())


SUBS = {"where": cmd_where, "peek": cmd_peek, "read": cmd_read, "send": cmd_send}


def main():
    global STACK
    aos_flags.HELP = HELP
    try:
        opts, rest = aos_flags.parse(sys.argv[1:], {"--stack": "stack"}, help=HELP, short=("-s",), sub="root")   # 11-10 Q1
        STACK = opts.get("stack")
        if not rest:
            raise Fail("ArgumentsBad", "missing subcommand (%s; see aos-mailbox --help)" % ", ".join(SUBS))
        if rest[0] not in SUBS:
            raise Fail("CommandUnknown", "unknown subcommand %s (%s; see aos-mailbox --help)" % (rest[0], ", ".join(SUBS)))
        code = SUBS[rest[0]](rest[1:])
    except aos_flags.Error as e:
        aos_flags.die(PROG, e.code, e)
    except Fail as e:
        aos_flags.die(PROG, e.code, e)
    sys.exit(code or 0)
