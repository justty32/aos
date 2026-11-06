# aos_agent/common.py - 共用分層 help、錯誤指路、旗標、daemon 協定與 agent 查找。
import os
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
        raise Fail("DaemonMissing", "%s is not an aos-daemon stack (no procs_state.json); run this in the workspace the daemon was started in (./.stack), "
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


def kernel_row():
    """AOS_KERNEL 落在表上哪一隻的 stack 裡（模式 2 的 0 號 proc）：(名字, 列)；沒設或不在誰的 stack 裡＝None。"""
    k = kernel_box()
    if not k:
        return None
    for n, r in table(quiet=True).items():
        st = r.get("stack")
        if isinstance(st, str) and st and under(k, st):
            return n, r
    return None


def is_kernel(a):
    """a 就是 AOS_KERNEL 那個 kernel（信箱在它的 stack 裡）：管它的信直接寄 daemon（它睡著時收不到給自己的 wake）。"""
    k = kernel_box()
    if k and under(k, a.stack):
        note("%s is the AOS_KERNEL kernel itself; sending this one straight to the daemon" % a.name)
        return True
    return False


def kernel_hint():
    """等滿逾時時補一句（沒設 AOS_KERNEL＝""）：信先給判官，沒放行也會等不到。"""
    k = kernel_box()
    if not k:
        return ""
    kr = kernel_row()
    if kr:
        return "; the letter went to AOS_KERNEL (mailbox of %s) first and no reply came from the judge either (it may be stuck or unable to write the reply mailbox): see %s/%s" % (
            kr[0], kr[1].get("stack"), call_dc(dc.names_of, daemon_path())["procs_stderr"])
    if os.path.dirname(k) == os.path.realpath(daemon_path()):
        return "; the letter went to the judge in the daemon body first (AOS_KERNEL=%s) and no reply came from it either (it may be unable to write the reply mailbox): see the daemon's stderr" % k
    return "; AOS_KERNEL=%s is neither this daemon's judge mailbox nor inside any listed proc's stack: wrong daemon or the kernel is gone, nobody reads the letter" % k


def wait_for(cond, what, secs=WAIT_S, via_kernel=True):
    """等 daemon 套用。via_kernel＝信經 AOS_KERNEL 寄的：kernel（表上的 0 號）不是 running＝立刻 WaitFailed（它不會判，等也沒用）。"""
    kr = kernel_row() if via_kernel else None
    if kr and kr[1].get("phase") != "running":
        ph = kr[1].get("phase")
        raise Fail("WaitFailed", "%s: the letter is in AOS_KERNEL, but kernel %s is %s and will not judge it (it waits in its mailbox until it is back); first aos-agent ctl %s --target %s" % (
            what, kr[0], ph, "wake" if ph == "sleeping" else "start", kr[0]))
    end = time.monotonic() + secs
    while time.monotonic() < end:
        v = cond()
        if v:
            return v
        time.sleep(0.1)
    raise Fail("WaitFailed", "waited %d s, %s%s" % (secs, what, kernel_hint() if via_kernel else ""))


def ctl_wait(cmd, body, cond, what, refused, direct=False):
    """共用回信箱按 in_reply_to 等自己的回信，同時等 daemon 表上的結果。"""
    d = daemon_path()
    box = call_dc(dc.reply_box, d)
    if not direct and kernel_box():
        note("routing via AOS_KERNEL=%s" % kernel_box())
    letter = call_dc(dc.send, d, body, reply_to=box, direct=direct)
    got, done_at = [None], [None]

    def step():
        if got[0] is None:
            got[0] = call_dc(dc.take_reply, box, letter)
        rep = got[0]
        if isinstance(rep, dict) and rep.get("applied") is False:
            err = rep.get("error") if isinstance(rep.get("error"), dict) else {}
            raise Fail(refused, "AOS_KERNEL refused the %s letter: %s %s" % (cmd, err.get("code", "?"), err.get("msg", "")))
        v = cond(letter)
        if not v:
            return None
        if rep is not None:
            return v
        done_at[0] = done_at[0] or time.monotonic()
        return v if time.monotonic() - done_at[0] >= REPLY_GRACE else None

    started = time.monotonic()
    try:
        return wait_for(step, what, via_kernel=not direct)
    except Fail as e:
        if e.code == "WaitFailed" and got[0] is None and time.monotonic() - started >= WAIT_S:
            raise Fail("DaemonMissing", "no reply from the daemon at %s within 30 s (busy, paused or not running; the letter stays in its mailbox and is applied if the daemon takes it later)%s" % (d, kernel_hint() if not direct else "")) from e
        raise


def phase_body(cmd, name):
    """控制動詞的檢查順序與共用介面一致。"""
    d = daemon_path()
    row = call_dc(dc.row_of, d, name)
    if cmd in ("stop", "sleep"):
        call_dc(dc.need_ctl, d, name, row)
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
        raise Fail("InstanceMissing", "%s is not on the daemon table (removed with rm, or it exited 0 and left the table; the stack may still be there: aos-agent ctl add with the same name to pick it up again)" % name)
    return Agent(name, r)


def target(opts, quiet=False):
    """--target ＞ $AOS_AGENT；都沒有＝TargetMissing。"""
    name = opts.get("target") or os.environ.get("AOS_AGENT", "")
    if not name:
        raise Fail("TargetMissing", "no target: add --target NAME, or export AOS_AGENT=NAME (or source using-aos-agent.sh NAME)")
    return find(name, quiet)
