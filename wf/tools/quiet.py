#!/usr/bin/env python3
# quiet.py - 清淨時段的指令與共用函式：開（30m／90s／1h）、關（off）、看（status）；quiet_hook.py、quiet_tick.py 也 import 這裡。
# 使用者 11-14：「太多的aos信件通知，你可以自己寫個腳本或小工具，讓自己有個暫時的清淨時段，專心處理事情」。
# 做法：<stack>/quiet/until.json 記到幾點結束（epoch 秒）；before_queue hook（quiet_hook.py）在清淨期間把「[aos] new_mail」「[aos] kernel_hold」
#   兩種通知擋下、原文附加到 quiet/deferred.jsonl（xiaosi 來的信放行）；on_clock hook（quiet_tick.py）時段結束後把暫存的合成一則「[aos] quiet_over: …」寄回 queue。
#   被擋的只是「通知」：信還在信箱、kernel_hold 的請求還在 gate（hold.json 與 requests/），不會不見。
# stack 預設取 $AOS_STACK（在 agent 自己的 Bash 裡就是它自己的 stack），可用 --stack 指定。
# 錯：stderr 一行「quiet: error: 代號 原因」、退 1。輸出一律英文；--help 印用法。
import json, os, re, sys, time

HELP = """usage: quiet.py [--stack DIR] 30m|90s|1h|1h30m   start a quiet time (new_mail and kernel_hold notices are held back)
       quiet.py [--stack DIR] off                    end it now (the held notices come back as one message within a minute)
       quiet.py [--stack DIR] status                 minutes left and how many notices are held
DIR defaults to $AOS_STACK (the agent's own stack). Notices from xiaosi, and every other kind of message, always get through.
"""
DIR = "quiet"
UNTIL, DEFERRED = "until.json", "deferred.jsonl"
UNITS = {"h": 3600, "m": 60, "s": 1}


def die(code, why):
    sys.stderr.write("quiet: error: %s %s\n" % (code, why))
    sys.exit(1)


def qdir(stack):
    return os.path.join(stack, DIR)


def parse_duration(text):
    """'30m' / '90s' / '1h' / '1h30m' -> seconds; None if bad."""
    m = re.fullmatch(r"(?:\d+[hms])+", text.strip().lower())
    if not m:
        return None
    secs = sum(int(n) * UNITS[u] for n, u in re.findall(r"(\d+)([hms])", text.lower()))
    return secs if secs > 0 else None


def until_of(stack):
    """quiet end time (epoch seconds), or None when there is no readable until.json."""
    try:
        with open(os.path.join(qdir(stack), UNTIL), encoding="utf-8") as f:
            v = json.load(f).get("until")
        return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None
    except (OSError, ValueError, AttributeError):
        return None


def active(stack, now=None):
    u = until_of(stack)
    return u is not None and (time.time() if now is None else now) < u


def read_deferred(path):
    rows = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if isinstance(r, dict) and isinstance(r.get("content"), str):
                    rows.append(r)
    except OSError:
        pass
    return rows


def write_atomic(path, text):
    tmp = "%s.%d.tmp" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def main(argv):
    if argv[:1] in (["-h"], ["--help"]):
        sys.stdout.write(HELP)
        return 0
    stack = None
    if argv[:1] == ["--stack"]:
        if len(argv) < 2:
            die("ArgumentsBad", "--stack needs a folder")
        stack, argv = argv[1], argv[2:]
    stack = (stack or os.environ.get("AOS_STACK") or "").rstrip("/")
    if not stack or not os.path.isdir(stack):
        die("StackMissing", "no stack folder (set $AOS_STACK or pass --stack DIR)")
    if len(argv) != 1:
        die("ArgumentsBad", "one argument: a duration like 30m, or off, or status (quiet.py --help)")
    cmd, d = argv[0], qdir(stack)
    if cmd == "off":
        try:
            os.remove(os.path.join(d, UNTIL))
            print("quiet time is off")
        except FileNotFoundError:
            print("quiet time was not on")
        except OSError as e:
            die("WriteFailed", "cannot remove %s: %s" % (os.path.join(d, UNTIL), e))
        held = len(read_deferred(os.path.join(d, DEFERRED)))
        if held:
            print("%d held notice%s will come back as one [aos] quiet_over message within a minute" % (held, "" if held == 1 else "s"))
        return 0
    if cmd == "status":
        u, held = until_of(stack), len(read_deferred(os.path.join(d, DEFERRED)))
        if u is not None and time.time() < u:
            print("quiet: on, %.1f minutes left (until %s), %d notice%s held" % ((u - time.time()) / 60, time.strftime("%H:%M:%S", time.localtime(u)), held, "" if held == 1 else "s"))
        else:
            print("quiet: off, %d notice%s held" % (held, "" if held == 1 else "s") + ("" if not held else " (they come back within a minute)"))
        return 0
    secs = parse_duration(cmd)
    if secs is None:
        die("ArgumentsBad", "bad duration %r (examples: 90s, 30m, 1h, 1h30m) or use off / status" % cmd)
    try:
        os.makedirs(d, exist_ok=True)
        until = time.time() + secs
        write_atomic(os.path.join(d, UNTIL), json.dumps({"until": until, "until_iso": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(until)), "seconds": secs}) + "\n")
    except OSError as e:
        die("WriteFailed", "cannot write under %s: %s" % (d, e))
    print("quiet time on for %s, until %s" % (cmd, time.strftime("%H:%M:%S", time.localtime(until))))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
