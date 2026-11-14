#!/usr/bin/env python3
# quiet.py - 清淨時段的指令與共用函式：開（30m／90s／1h）、關（off）、看（status）；quiet_hook.py、quiet_tick.py 也 import 這裡。
# 使用者 11-14：「太多的aos信件通知，你可以自己寫個腳本或小工具，讓自己有個暫時的清淨時段，專心處理事情」。
# 做法：<stack>/quiet/until.json 記到幾點結束（epoch 秒）；before_queue hook（quiet_hook.py）在清淨期間把「[aos] new_mail」「[aos] kernel_hold」
#   兩種通知擋下、原文附加到 quiet/deferred.jsonl（xiaosi 來的信放行）；on_clock hook（quiet_tick.py）時段結束後把暫存的合成一則「[aos] quiet_over: …」寄回 queue。
#   被擋的只是「通知」：信還在信箱、kernel_hold 的請求還在 gate（hold.json 與 requests/），不會不見。
# stack 預設取 $AOS_STACK（在 agent 自己的 Bash 裡就是它自己的 stack），可用 --stack 指定。
# 使用者 11-14：「你做的這個工具也可以分享給大家」→ 任何 agent 都能裝在自己身上：`quiet.py install`／`uninstall` 加減 hook（走 aos-agent hook）；
#   「哪些寄件人算要緊」「自動回信不回誰」「ok-* 回報該改寄誰」不寫死，放 <stack>/quiet/config.json（見下面 config()）。
#   自動回信（autoreply_tick.py，11-14：「你也可以弄個自動回信工具」）：清淨中對來信自動回一封；status 多印清淨期間自動回了幾封。
# 錯：stderr 一行「quiet: error: 代號 原因」、退 1。輸出一律英文；--help 印用法。
import fnmatch, json, os, re, subprocess, sys, time

HELP = """usage: quiet.py [--stack DIR] 30m|90s|1h|1h30m   start a quiet time (new_mail and kernel_hold notices are held back)
       quiet.py [--stack DIR] off                    end it now (the held notices come back as one message within a minute)
       quiet.py [--stack DIR] status                 minutes left, how many notices are held, how many auto-replies were sent
       quiet.py [--stack DIR] install [--no-autoreply]   add the hooks (quiet_hook, quiet_tick, autoreply_tick) to this agent, with a default config
       quiet.py [--stack DIR] uninstall              remove those hooks (the quiet/ folder stays)
DIR defaults to $AOS_STACK (the agent's own stack). Every other kind of message, and notices from the senders listed
in DIR/quiet/config.json "urgent_senders", always get through. Config keys (all optional):
  "self": my own name (default: the stack folder name)      "urgent_senders": ["name", ...]  (substring, any case)
  "no_reply_senders": ["name", ...]  never auto-reply to these (me and urgent_senders are always skipped)
  "redirect": {"senders": ["ok-*"], "to": "name"}  these senders get a "send reports to NAME" reminder (once an hour each)
  "autoreply": false  turns auto-replies off
"""
DIR = "quiet"
UNTIL, DEFERRED = "until.json", "deferred.jsonl"
CONFIG, AUTOREPLY_DIR, COUNT = "config.json", "autoreply", "count.json"
UNITS = {"h": 3600, "m": 60, "s": 1}
HOOKS = (("quiet_hook", "quiet_hook.py", ["--event", "before_queue", "--timeout-ms", "5000"]),
         ("quiet_tick", "quiet_tick.py", ["--event", "on_clock", "--every-ms", "60000", "--timeout-ms", "10000"]),
         ("autoreply_tick", "autoreply_tick.py", ["--event", "on_clock", "--every-ms", "60000", "--timeout-ms", "15000"]))
DEFAULT_CONFIG = {"urgent_senders": [], "no_reply_senders": [], "redirect": {"senders": [], "to": ""}}


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


def names(v):
    return [x.strip().lower() for x in v if isinstance(x, str) and x.strip()] if isinstance(v, list) else []


def config(stack):
    """the agent's settings from <stack>/quiet/config.json, with every key filled in (a missing or broken file = no urgent senders)."""
    try:
        with open(os.path.join(qdir(stack), CONFIG), encoding="utf-8") as f:
            raw = json.load(f)
        raw = raw if isinstance(raw, dict) else {}
    except (OSError, ValueError):
        raw = {}
    red = raw.get("redirect") if isinstance(raw.get("redirect"), dict) else {}
    me = raw.get("self") if isinstance(raw.get("self"), str) and raw.get("self").strip() else os.path.basename(stack.rstrip("/"))
    return {"self": me, "urgent": names(raw.get("urgent_senders")), "no_reply": names(raw.get("no_reply_senders")),
            "redirect_senders": names(red.get("senders")), "redirect_to": red.get("to") if isinstance(red.get("to"), str) else "",
            "autoreply": raw.get("autoreply") is not False}


def has_any(sender, wanted):
    """sender contains any of the wanted names (substring, any case)."""
    s = (sender or "").lower()
    return any(w in s for w in wanted)


def read_count(stack):
    try:
        with open(os.path.join(stack, AUTOREPLY_DIR, COUNT), encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


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


def agent_hook(stack, *args):
    """run `aos-agent hook` aimed at the agent whose stack this is (<daemon>/procs/<name>)."""
    name, procs = os.path.basename(stack), os.path.dirname(stack)
    if os.path.basename(procs) != "procs":
        die("StackBad", "%s is not <daemon>/procs/<name>; cannot tell which agent it is" % stack)
    try:
        return subprocess.run(["aos-agent", "--daemon", os.path.dirname(procs), "hook", "-t", name] + list(args), capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired) as e:
        die("CommandFailed", "cannot run aos-agent hook: %s" % e)


def setup(stack, cmd, flags):
    here = os.path.dirname(os.path.realpath(__file__))
    for name, fname, extra in HOOKS:
        if cmd == "install" and name == "autoreply_tick" and "--no-autoreply" in flags:
            continue
        if cmd == "install":
            p = agent_hook(stack, "add", "-n", name, "--on-error", "continue", "--replace", *extra, os.path.join(here, fname))
        else:
            p = agent_hook(stack, "rm", name)
        if p.returncode != 0 and not (cmd == "uninstall" and "HookMissing" in p.stderr):
            die("CommandFailed", "hook %s %s: %s" % (name, cmd, (p.stderr.strip().splitlines() or ["?"])[-1]))
        print("%s %s" % (name, "installed" if cmd == "install" else "removed (or was not there)"))
    if cmd == "install":
        path = os.path.join(qdir(stack), CONFIG)
        if not os.path.exists(path):
            try:
                os.makedirs(qdir(stack), exist_ok=True)
                write_atomic(path, json.dumps(DEFAULT_CONFIG, indent=1) + "\n")
                print("wrote a default %s (edit it: urgent_senders, no_reply_senders, redirect)" % path)
            except OSError as e:
                die("WriteFailed", "cannot write %s: %s" % (path, e))
        print("done; the hooks work from the next event. Turn quiet time on with: quiet.py 30m")
    return 0


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
    if argv[:1] == ["install"] and argv[1:] == ["--no-autoreply"]:
        return setup(stack, "install", ["--no-autoreply"])
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
        c = read_count(stack)
        n = c.get("n") if isinstance(c.get("n"), int) else None
        if u is not None and c.get("until") != u:
            n = 0                                   # 還沒回過：計數檔是上一段清淨的
        if n is not None:
            print("quiet auto-replies sent %s: %d" % ("this quiet time" if u is not None and time.time() < u else "in the last quiet time", n))
        return 0
    if cmd in ("install", "uninstall"):
        return setup(stack, cmd, [])
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
