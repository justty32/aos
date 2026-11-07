# aos_agent/common.py - 共用分層 help、錯誤指路、旗標、daemon 協定與活列查找及等待。
import os
import math
import json
import textwrap
from . import PROG
import aos_flags
import daemon_ctl as dc
import time

HERE = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))           # proto8/
TOOLS = os.path.join(ROOT, "cmd", "aos-tools", "bin", "aos-tools")
dc.PROG = PROG
WAIT_S = 30                                     # add／stop／rm／start 等 daemon 的上限（daemon 的 grace 是 10 秒）
REPLY_GRACE = 1.0                               # 結果先到時再留一秒等回信
POLL = 0.2                                      # listen 看一次的間隔（秒）
DECL = "interfaces.json"                        # 宣告檔（03）
IFACE = "aos-agent"

# ---------------------------------------------------------------- daemon（共用 daemon_ctl 模組）

DAEMON = None                                   # main 裡從 --daemon 定



class Fail(Exception):
    def __init__(self, code, msg):
        super().__init__(str(msg).replace("\n", " "))
        self.code = code


def note(msg):
    """提醒（不是錯）：stderr 一行 `aos-agent: warning: 句子`（11-05 R1；原本是括號一行）。"""
    aos_flags.warn(PROG, msg)


def usage_of(help):
    """HELP 的第一個 usage 是錯誤行與群組導航的唯一來源。"""
    return next(line.removeprefix("usage: ") for line in help.splitlines()
                if line.startswith("usage: "))


def bad_args(help, reason):
    return Fail("ArgumentsBad", "%s (usage: %s)" % (reason, usage_of(help)))


def actions(helps, prefix):
    """由動作的 usage 與 NAME 生群組導航，不重抄命令語法或摘要。"""
    out = []
    for help in helps:
        usage = usage_of(help).removeprefix(prefix)
        name = help.splitlines()[0].split(" - ", 1)[1]
        entry = "  %s%s" % (usage.ljust(max(24, len(usage) + 2)), name)
        if len(entry) <= 100:
            out.append(entry)
        else:
            out.append("  " + usage)
            out.extend(textwrap.wrap(name, width=100, initial_indent="                          ",
                                     subsequent_indent="                          "))
    return "\n".join(out)


def parse(argv, flags=None, switches=None, *, help=None, short=None):
    try:
        return aos_flags.parse(argv, flags or {}, switches, help=help, short=short)
    except aos_flags.Error as e:
        if e.code == "ArgumentsBad" and help:
            raise bad_args(help, str(e)) from e
        path = help.splitlines()[0].split(" - ", 1)[0] if help else PROG
        raise Fail(e.code, "%s (see %s --help)" % (e, path)) from e


def timeout_opt(opts, help):
    """六個控制動詞共用有限正秒數；未指定沿用原本上限。"""
    raw = opts.get("timeout_s", WAIT_S)
    try:
        secs = float(raw)
    except (ValueError, TypeError):
        secs = float("nan")
    if not math.isfinite(secs) or secs <= 0:
        raise bad_args(help, "--timeout-s must be a positive number of seconds, not %s" % raw)
    return secs


def call_dc(fn, *args, **kwargs):
    """共用模組的錯只在這裡換成這支的代號。"""
    try:
        return fn(*args, **kwargs)
    except dc.Fail as e:
        raise Fail({"ProcMissing": "InstanceMissing"}.get(e.code, e.code), str(e)) from e


def daemon_path():
    return call_dc(dc.find_daemon, DAEMON)


def need_table():
    d = daemon_path()
    if not os.path.isfile(os.path.join(d, "procs_state.json")):
        raise Fail("StateMissing", "%s is not an aos-daemon stack (no procs_state.json); run this in the workspace the daemon was started in (./.stack), "
                   "or point --daemon / AOS_DAEMON at the daemon's $AOS_STACK" % d)
    return d


def table(quiet=False):
    """直接讀 daemon 的表；quiet 留給既有呼叫者。"""
    return {n: r for n, r in call_dc(dc.rows, daemon_path()).items() if isinstance(r, dict)}


def under(path, top):
    p, t = os.path.realpath(path), os.path.realpath(top).rstrip("/")
    return p == t or p.startswith(t + "/")


def kernel_box():
    """$AOS_KERNEL（ctl 的信先寄那裡給判官，11-05 kernel-daemon）；沒設＝None。"""
    k = os.environ.get("AOS_KERNEL", "")
    return os.path.realpath(k) if k else None


def kernel_hint():
    """只指向 AOS_KERNEL 公開介面，不辨識收件者身份。"""
    k = kernel_box()
    return "; letter was sent first to AOS_KERNEL=%s; no reply from there; inspect adjacent %s" % (k, os.path.join(os.path.dirname(k), "queue.json")) if k else ""


def queued_opt(opts, help):
    value = opts.get("on_queued", "fail")
    if value not in {"fail", "ok"}:
        raise bad_args(help, "--on-queued must be fail or ok")
    return value


def queue_position(letter):
    k = kernel_box()
    if not k:
        return None
    try:
        with open(os.path.join(os.path.dirname(k), "queue.json"), encoding="utf-8") as fh:
            rows = json.load(fh).get("queued", [])
        return next((i for i, row in enumerate(rows, 1) if isinstance(row, dict) and row.get("letter") == letter), None)
    except (OSError, ValueError, AttributeError, TypeError):
        return None


def wait_for(cond, what, secs=WAIT_S):
    """等公開表上的結果，不讀收件者身份或內部狀態。"""
    end = time.monotonic() + secs
    while time.monotonic() < end:
        v = cond()
        if v:
            return v
        time.sleep(min(0.1, max(0, end - time.monotonic())))
    raise Fail("WaitFailed", "waited %g s, %s%s" % (secs, what, kernel_hint()))


def ctl_wait(cmd, body, cond, what, refused, secs=WAIT_S, on_queued="fail", name=None):
    """等自己的回信與公開表；排隊可成功返回，逾時先撤未領取的信。"""
    d = daemon_path()
    box = call_dc(dc.reply_box, d)
    recipient = call_dc(dc.mailbox_of, d)
    if kernel_box():
        note("routing via AOS_KERNEL=%s" % kernel_box())
    if cmd in {"add", "start", "wake"} and on_queued == "fail":
        millis = secs * 1000
        body = dict(body, queue_wait_ms=int(millis) if math.isfinite(millis) else int(secs) * 1000)
    letter = call_dc(dc.send, d, body, reply_to=box)
    got, done_at = None, None
    end = time.monotonic() + secs

    def step(expiration=False):
        nonlocal got, done_at
        if got is None:
            got = call_dc(dc.take_reply, box, letter)
        if isinstance(got, dict) and got.get("applied") is False:
            err = got.get("error") if isinstance(got.get("error"), dict) else {}
            if expiration:
                raise Fail(err.get("code", refused), err.get("msg", "request refused"))
            raise Fail(refused, "the %s letter was refused: %s %s" % (cmd, err.get("code", "?"), err.get("msg", "")))
        v = cond(letter)
        if not v:
            return None
        if got is not None:
            return v
        done_at = done_at or time.monotonic()
        return v if time.monotonic() - done_at >= REPLY_GRACE else None

    while time.monotonic() < end:
        value = step()
        if value:
            return value
        time.sleep(min(0.1, max(0, end - time.monotonic())))
    value = step()
    if value:
        return value
    if got is not None:
        raise Fail("WaitFailed", "waited %g s, %s" % (secs, what))
    position = queue_position(letter)
    if position is not None and cmd in {"add", "start", "wake"}:
        if on_queued == "ok":
            print("queued %s at position %d (letter %s; applied when a slot frees)" % (name, position, letter))
            return None
        grace_end = time.monotonic() + REPLY_GRACE
        while time.monotonic() < grace_end:
            value = step(expiration=True)
            if value:
                return value
            time.sleep(min(0.05, max(0, grace_end - time.monotonic())))
        value = step(expiration=True)
        if value:
            return value
    withdrawn = call_dc(dc.regret, recipient, letter)
    outcome = "letter withdrawn, it will not be applied" if withdrawn else "could not withdraw it; it may still be applied"
    raise Fail("DaemonFailed", "no result from the daemon at %s within %g s; %s%s" % (d, secs, outcome, kernel_hint()))


def phase_body(cmd, name):
    """控制動詞的檢查順序與共用介面一致。"""
    d = daemon_path()
    row = call_dc(dc.row_of, d, name)
    call_dc(dc.need_phase, cmd, name, row)
    return {{"stop": "procs_stopped", "start": "procs_started", "sleep": "procs_slept", "wake": "procs_woken"}[cmd]: [name]}


class Agent:
    """表上的一隻：name、row（那一列；路徑欄 daemon_ctl 已拼回絕對）、stack、ws、phase、reason。"""

    def __init__(self, name, row):
        self.name, self.row = name, row
        self.stack = (row.get("stack") or "").rstrip("/") or "/"
        self.ws = row.get("ws") or os.getcwd()
        self.phase = row.get("phase")
        r = row.get("reason")
        self.reason = None if r is None else str(r).replace("\n", " ")


def row_named(name):
    return table(quiet=True).get(name)


def find(name, quiet=False):
    r = table(quiet=quiet).get(name)
    if r is None or not isinstance(r.get("stack"), str) or not r.get("stack"):
        raise Fail("InstanceMissing", "%s is not on the daemon table (removed with rm, exited 0, or an adopted body ended with unknown status; known nonzero exits stay stopped with a reason; the stack may still be there: aos-agent ctl add with the same name to pick it up again)" % name)
    return Agent(name, r)


def target(opts, quiet=False):
    """--target ＞ $AOS_AGENT；都沒有＝TargetMissing。"""
    name = opts.get("target") or os.environ.get("AOS_AGENT", "")
    if not name:
        raise Fail("TargetMissing", "no target: add --target NAME, or export AOS_AGENT=NAME (or source using-aos-agent.sh NAME)")
    return find(name, quiet)
