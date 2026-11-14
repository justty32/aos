#!/usr/bin/env python3
# autoreply_tick.py - on_clock hook（每 60 秒）：只看（不收）agent 自己的信箱 <stack>/mailbox/new，替來信自動回一封。
# 使用者 11-14：「好，你也可以弄個自動回信工具...www。」；後來又說「做的工具也可以分享給大家」→ 誰要特別對待都放 <stack>/quiet/config.json（quiet.py config()）。
# 規則（每封信最多回一次）：
#   1. 清淨中（quiet/until.json 還沒過期），而且信是這段清淨期間來的、寄件人不在 urgent_senders／no_reply_senders、不是自己 → 回 PROGRESS「清淨中、信已收」。
#   2. 不管清不清淨，寄件人符合 redirect.senders（例 "ok-*"）→ 回一封「之後回報請寄 redirect.to」；同一寄件人一小時內只提醒一次。
#      兩條同時成立就合成一封（清淨回信裡附提醒，一樣算這個寄件人的提醒）。
#   不回：自己寄的、urgent_senders／no_reply_senders 的人、自動回信本身（title 開頭「[auto] 」）。
# 狀態在 <stack>/autoreply/：replied.json（回過的信名；信被讀掉就從檔裡移除）、reminded.json（寄件人→上次提醒時間）、count.json（這段清淨自動回了幾封，quiet.py status 讀它）。
# 回信地址取原信的 reply_to（相對於信箱），沒有就用 sender＋/mailbox；用 aos-mailbox send --box --in-reply-to，不動原信。
# 介面：stdin＝事件 JSON（stack＝agent 的 stack）。錯：stderr 一行「autoreply_tick: error: 代號 原因」、退 1。輸出（含信的內容）一律英文。
import fnmatch, json, os, subprocess, sys, time
from datetime import datetime
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import quiet as q

PREFIX = "[auto] "
HOUR = 3600
MAX_PER_RUN = 10
STEP_S = 6


def die(code, why):
    sys.stderr.write("autoreply_tick: error: %s %s\n" % (code, why))
    sys.exit(1)


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            v = json.load(f)
        return v if isinstance(v, type(default)) else default
    except (OSError, ValueError):
        return default


def save(path, value):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    q.write_atomic(path, json.dumps(value, ensure_ascii=False, indent=1) + "\n")


def run(argv, text=None):
    try:
        return subprocess.run(argv, input=text, capture_output=True, text=True, timeout=STEP_S)
    except (OSError, subprocess.TimeoutExpired) as e:
        die("CommandFailed", "%s: %s" % (" ".join(argv[:3]), e))


def epoch(iso):
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
    except (ValueError, AttributeError):
        return None


def reply_box(mailbox, letter):
    """where to answer: the letter's reply_to (relative to my mailbox), else its sender + /mailbox; None if there is no mailbox there."""
    d = load(os.path.join(mailbox, "new", letter, "letter.json"), {})
    cands = []
    if isinstance(d.get("reply_to"), str):
        cands.append(os.path.normpath(os.path.join(mailbox, d["reply_to"])))
    if isinstance(d.get("sender"), str):
        cands.append(os.path.join(d["sender"], "mailbox"))
    for c in cands:
        if all(os.path.isdir(os.path.join(c, s)) for s in ("tmp", "new", "cur")):
            return c
    return None


def compose(cfg, quiet_until, remind):
    me, to = cfg["self"], cfg["redirect_to"] or (cfg["urgent"][0] if cfg["urgent"] else "")
    note = "This is an automatic reply: no need to answer it. "
    if quiet_until:
        hhmm = time.strftime("%H:%M", time.localtime(quiet_until))
        title = "%s%s is in quiet time (until %s): letter received, will be handled later" % (PREFIX, me, hhmm)
        what = "%s%s is in quiet time until %s and has not read your letter yet; it stays in the mailbox and will be read afterwards." % (note, me, hhmm)
        if to:
            what += " If it is urgent, send it to %s instead, with status NEEDS-USER or BLOCKED." % to
        if remind:
            what += " From now on please send your reports to %s, not to %s." % (to, me)
    else:
        title = "%sreports to %s should go to %s from now on" % (PREFIX, me, to)
        what = "%sPlease send your reports to %s, not to %s; %s passes on what is urgent right away. This reminder is sent at most once an hour." % (note, to, me, to)
    return title, what


def main():
    try:
        stack = json.load(sys.stdin)["stack"].rstrip("/")
    except (ValueError, KeyError, TypeError, AttributeError):
        die("ArgumentsBad", "the event on stdin is not JSON with a stack")
    cfg = q.config(stack)
    if not cfg["autoreply"]:
        return 0
    if not os.path.isdir(os.path.join(stack, "mailbox")):
        return 0                                                 # 還沒有信箱＝沒有信
    p = run(["aos-mailbox", "-s", stack, "peek", "--json"])
    if p.returncode != 0:
        die("CommandFailed", "aos-mailbox peek: %s" % ((p.stderr.strip().splitlines() or ["?"])[-1]))
    try:
        rows = [r for r in json.loads(p.stdout or "[]") if isinstance(r, dict) and isinstance(r.get("letter"), str)]
    except ValueError:
        die("CommandFailed", "aos-mailbox peek --json printed something that is not JSON")
    mailbox = os.path.join(stack, "mailbox")
    ad = os.path.join(stack, q.AUTOREPLY_DIR)
    now = time.time()
    here = {r["letter"] for r in rows}
    replied_p, reminded_p, count_p = (os.path.join(ad, n) for n in ("replied.json", "reminded.json", q.COUNT))
    replied = load(replied_p, [])
    keep = [n for n in replied if n in here]                      # 讀掉的信就從檔裡移除
    done = set(keep)
    reminded = {k: v for k, v in load(reminded_p, {}).items() if isinstance(v, (int, float)) and now - v < HOUR}
    until = q.until_of(stack)
    quiet_on = until is not None and now < until
    started = None
    if quiet_on:
        secs = load(os.path.join(q.qdir(stack), q.UNTIL), {}).get("seconds")
        started = until - secs if isinstance(secs, (int, float)) and not isinstance(secs, bool) else None
    count = load(count_p, {})
    if quiet_on and count.get("until") != until:
        count = {"until": until, "n": 0}
    sent, quiet_sent, errors = 0, 0, []
    skip = cfg["no_reply"] + cfg["urgent"]
    for r in rows:
        name = r["letter"]
        who = r.get("from") if isinstance(r.get("from"), str) else ""
        title = r.get("title") if isinstance(r.get("title"), str) else ""
        if name in done or title.startswith(PREFIX) or who.strip().lower() == cfg["self"].lower() or q.has_any(who, skip) or not who.strip():
            continue
        quiet_now = quiet_on and (started is None or (epoch(r.get("sent_at")) or now) >= started - 1)
        redirect = bool(cfg["redirect_to"]) and any(fnmatch.fnmatchcase(who.lower(), pat) for pat in cfg["redirect_senders"])
        remind = redirect and now - reminded.get(who, 0) >= HOUR
        if not (quiet_now or remind) or sent >= MAX_PER_RUN:
            continue
        box = reply_box(mailbox, name)
        if box is None:
            errors.append("letter %s from %s has no mailbox to answer" % (name, who))
            keep.append(name)                                       # 不再重試
            continue
        t, w = compose(cfg, until if quiet_now else None, remind)
        a = run(["aos-mailbox", "-s", stack, "send", "--box", box, "--from", cfg["self"], "--status", "PROGRESS", "--title", t, "--in-reply-to", name, "-"], text=w)
        if a.returncode != 0:
            errors.append("cannot answer letter %s: %s" % (name, (a.stderr.strip().splitlines() or ["?"])[-1]))
            continue
        keep.append(name)
        sent += 1
        if remind:
            reminded[who] = now
        if quiet_now:
            quiet_sent += 1
    try:
        if keep != replied:
            save(replied_p, keep)
        if sent:
            save(reminded_p, reminded)
        if quiet_sent:
            count["n"] = count.get("n", 0) + quiet_sent
            save(count_p, count)
    except OSError as e:
        die("WriteFailed", "cannot write under %s: %s" % (ad, e))
    if errors:
        die("CommandFailed", "; ".join(errors))
    return 0


sys.exit(main())
