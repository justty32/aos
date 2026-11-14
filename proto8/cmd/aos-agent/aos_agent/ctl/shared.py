# aos_agent/ctl/shared.py - ctl 動作才用的共用零件：--timeout-s／--on-queued／名字放最後、寄控制信給 daemon（或 AOS_KERNEL）並等回信與公開表。
import math
import os
import time
import daemon_ctl as dc
from .. import common
from ..common import Fail, bad_args, call_dc, daemon_path, kernel_box, note, queue_position, table_ref, via_kernel

WAIT_S = 30                                     # add／stop／rm／start 等 daemon 的上限（daemon 的 grace 是 10 秒）
REPLY_GRACE = 1.0                               # 結果先到時再留一秒等回信


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


def query_opt(opts, help):
    """ctl ls／who／where／state 的 --timeout-s：走 kernel 時等查詢信回信的秒數（沒給＝3 秒）；沒走 kernel 不寄信、用不到。"""
    if opts.get("timeout_s") is not None:
        common.QUERY_S = timeout_opt(opts, help)


def need_table():
    """沒走 kernel：daemon 的資料夾要有表（照舊）。走 kernel：不核，讀表的地方經查詢信拿、問不到就報。"""
    if via_kernel():
        return None
    d = daemon_path()
    if not os.path.isfile(os.path.join(d, "procs_state.json")):
        raise Fail("StateMissing", "%s is not an aos-daemon stack (no procs_state.json); run this in the workspace the daemon was started in (./.stack), "
                   "or point --daemon / AOS_DAEMON at the daemon's $AOS_STACK" % d)
    return d


def kernel_hint():
    """只指向 AOS_KERNEL 公開介面，不辨識收件者身份。"""
    k = kernel_box()
    return "; letter was sent first to AOS_KERNEL=%s; no reply from there; inspect adjacent %s" % (k, os.path.join(os.path.dirname(k), "queue.json")) if k else ""


def queued_opt(opts, help):
    value = opts.get("on_queued", "fail")
    if value not in {"fail", "ok"}:
        raise bad_args(help, "--on-queued must be fail or ok")
    return value


def wait_for(cond, what, secs=WAIT_S):
    """等公開表上的結果，不讀收件者身份或內部狀態。"""
    end = time.monotonic() + secs
    while time.monotonic() < end:
        v = cond()
        if v:
            return v
        time.sleep(min(0.1, max(0, end - time.monotonic())))
    raise Fail("WaitFailed", "waited %g s, %s%s" % (secs, what, kernel_hint()))


def nested_pid_ns():
    """這支行程不在最外層的 pid 命名空間＝True（最外層那個的 inode 是核心固定值 0xEFFFFFFC＝4026531836）；讀不到也當是（不核）。"""
    try:
        return os.readlink("/proc/self/ns/pid") != "pid:[4026531836]"
    except OSError:
        return True


def daemon_up(d):
    """寄信前先核 daemon 活著沒（11-10 晚 cli-sweep 甲6：沒在跑就不乾等 --timeout-s）：只看它的 state 窗＋/proc（同 aos-daemon-ctl ls
    的「# daemon:」那行）。確定不在＝DaemonMissing 並指路；state 窗關著、讀壞（StateMissing／StateBad）＝不擋，照舊寄信等回音。
    自己在子 pid 命名空間裡（aos-sandbox 的 bwrap --unshare-all）看不到 daemon 的 pid＝不核、照舊（不誤報）。"""
    if nested_pid_ns():
        return
    try:
        dc.check_alive(d, dc.read_state(d))
    except dc.Fail as e:
        if e.code != "DaemonMissing":
            return
        raise Fail("DaemonMissing", "%s; nothing was sent. Start it first: aos-exec --stack %s <its definition folder> "
                   "(see aos-daemon-ctl -d %s ls)" % (e, d, d)) from e


def send_only(body):
    """寄給 daemon、不要回信、不等（11-10 self_ctl：sleep／rm 自己＝等的人會被一起收掉）；回信名。走 kernel＝寄 AOS_KERNEL、不核 daemon 活不活。"""
    if via_kernel():
        return call_dc(dc.send, None, body)
    d = daemon_path()
    daemon_up(d)
    return call_dc(dc.send, d, body)


def ctl_wait(cmd, body, cond, what, refused, secs=WAIT_S, on_queued="fail", name=None, replied=False):
    """等自己的回信與公開表；排隊可成功返回，逾時先撤未領取的信。replied＝收到 daemon 的回信（applied）就算數、不看表。
    走 kernel（kernel-framework 03）＝信寄 AOS_KERNEL、回信信箱照 kernel_reply_box、不核 daemon 活不活；只看回信的指令呼叫時給 replied。"""
    kernel = via_kernel()
    if kernel:
        d = None
        box = call_dc(dc.kernel_reply_box)
    else:
        d = daemon_path()
        daemon_up(d)
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
        if replied:
            return got
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
    if kernel:
        raise Fail("DaemonFailed", "no reply to the %s letter sent to AOS_KERNEL=%s within %g s; %s; inspect adjacent %s"
                   % (cmd, recipient, secs, outcome, os.path.join(os.path.dirname(recipient), "queue.json")))
    raise Fail("DaemonFailed", "no result from the daemon at %s within %g s; %s%s" % (d, secs, outcome, kernel_hint()))


def phase_body(cmd, name, look=True):
    """控制動詞的檢查順序與共用介面一致。look＝先對表上那列核 phase；只看回信的（走 kernel 的 stop／start／sleep／wake）不讀表、不核。"""
    if look:
        row = call_dc(dc.row_of, table_ref(), name)
        call_dc(dc.need_phase, cmd, name, row)
    return {{"stop": "procs_stopped", "start": "procs_started", "sleep": "procs_slept", "wake": "procs_woken"}[cmd]: [name]}


def name_last(opts, rest, help):
    """11-10 cli-sweep Q2（使用者「2.收。」）：ctl 對單一隻的動作也收「名字放最後」——aos-agent ctl stop ann 與 -t ann 都通；
    兩個都給又不同＝ArgumentsBad；多於一個位置參數＝ArgumentsBad。"""
    if not rest:
        return
    if len(rest) > 1:
        raise bad_args(help, "one NAME at most, got %s" % " ".join(rest))
    if opts.get("target") and opts["target"] != rest[0]:
        raise bad_args(help, "two different targets: --target %s and %s; give it once" % (opts["target"], rest[0]))
    opts["target"] = rest[0]
