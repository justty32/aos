#!/usr/bin/env python3
# quiet_tick.py - on_clock hook（每 60 秒）：清淨時段結束後，quiet/deferred.jsonl 有東西就合成一則「[aos] quiet_over: …」寄進 agent 的 queue、清空。
# 做法：先把 deferred.jsonl 改名（不跟 quiet_hook 同時寫打架）→ 合成 → aos-post send --ordered <stack>/queue → 成功才刪；寄失敗就把內容併回 deferred.jsonl 下次再試。
# 被擋的只是通知：new_mail 的信還在信箱（mailbox_peek）、kernel_hold 的請求還在 gate（kernel_gate ls）；合成訊息裡寫明這點與 letter 名單。
# 介面：stdin＝事件 JSON（stack＝agent 的 stack）。清淨還沒結束＝什麼都不做。錯：stderr 一行「quiet_tick: error: 代號 原因」、退 1。
import json, os, re, subprocess, sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import quiet as q

COUNT = re.compile(r"^\[aos\] new_mail: (\d+) new letter")
FROM = re.compile(r"letters? from (.*?)\. Look with", re.S)
LETTER = re.compile(r"^- letter (\S+)", re.M)


def die(code, why):
    sys.stderr.write("quiet_tick: error: %s %s\n" % (code, why))
    sys.exit(1)


def summary(rows):
    mails, holds, letters, senders, nm = 0, 0, [], [], 0
    for r in rows:
        c = r["content"]
        if c.startswith("[aos] kernel_hold"):
            holds += 1
            for name in LETTER.findall(c):
                if name not in letters:
                    letters.append(name)
        else:
            mails += 1
            m = COUNT.match(c)
            nm += int(m.group(1)) if m else 1
            m = FROM.search(c)
            for who in (m.group(1).split(", ") if m else []):
                if who not in senders:
                    senders.append(who)
    parts = []
    if mails:
        parts.append("new_mail x%d (%d new letter%s; senders: %s)" % (mails, nm, "" if nm == 1 else "s", ", ".join(senders) or "?"))
    if holds:
        parts.append("kernel_hold x%d (letters: %s)" % (holds, ", ".join(letters) or "?"))
    n = len(rows)
    return ("[aos] quiet_over: %d notice%s held during the quiet time: %s. Nothing was lost: the mail is still in your mailbox "
            "(mailbox_peek) and the requests are still held at your kernel gate (kernel_gate ls)." % (n, "" if n == 1 else "s", "; ".join(parts)))


def main():
    try:
        stack = json.load(sys.stdin)["stack"]
    except (ValueError, KeyError, TypeError):
        die("ArgumentsBad", "the event on stdin is not JSON with a stack")
    if q.active(stack):
        return 0
    d = q.qdir(stack)
    path = os.path.join(d, q.DEFERRED)
    mine = "%s.sending.%d" % (path, os.getpid())
    try:
        os.rename(path, mine)
    except FileNotFoundError:
        return 0
    except OSError as e:
        die("WriteFailed", "cannot take %s: %s" % (path, e))
    rows = q.read_deferred(mine)
    if rows:
        box = os.path.join(stack, "queue")
        if not all(os.path.isdir(os.path.join(box, s)) for s in ("tmp", "new", "cur")):
            subprocess.run(["aos-post", "init", box], capture_output=True, timeout=8)
        try:
            p = subprocess.run(["aos-post", "send", "--ordered", box], input=json.dumps({"role": "user", "content": summary(rows)}, ensure_ascii=False),
                               capture_output=True, text=True, timeout=8)
            ok, err = p.returncode == 0, p.stderr.strip()
        except (OSError, subprocess.TimeoutExpired) as e:
            ok, err = False, str(e)
        if not ok:
            with open(mine, encoding="utf-8") as f, open(path, "a", encoding="utf-8") as g:   # 併回去，下一分鐘再試
                g.write(f.read())
            os.remove(mine)
            die("CommandFailed", "cannot send the summary to %s: %s" % (box, err.splitlines()[-1] if err else "?"))
    os.remove(mine)
    try:
        if q.until_of(stack) is not None and not q.active(stack):
            os.remove(os.path.join(d, q.UNTIL))        # 過期的 until.json 順手收掉
    except OSError:
        pass
    return 0


sys.exit(main())
