"""daemon_ctl 控制：檢查 proc 階段、依公開窗名寫入控制並等待套用；也寫 daemon 自己的 ctl 停它本身。"""
import json
import os
import time

import aos_flags
import daemon_ctl as _pkg

from .base import Fail, STATE_FLUX
from .entry import read_loop
from .poke import check_alive, poke, read_state
from .table import cell_of, names_of, row_of

CTL = "ctl.json"   # daemon 自己 ctl 窗的預設名（daemon.json 沒寫 ctl 時）



def need_ctl(d, name, row=None):
    """公開 ctl 路徑：父寫的 loop 設定有非空 ctl 才用它，其他一律 ctl.json。"""
    stack = cell_of(d, name, row)
    try:
        c = read_loop(os.path.join(stack, names_of(d)["procs_loop"])).get("ctl")
    except Fail:
        c = None
    return stack, os.path.join(stack, c if isinstance(c, str) and c else "ctl.json")


# 11-05 portable-flow 衝突 1「嚴格分」：sleep 另收 stopping，其餘動詞只收一種 phase；用錯的提示（照表上的 phase 給下一步）
PHASE_OK = {"stop": "running", "sleep": "running", "start": "stopped", "wake": "sleeping"}
PHASE_HINT = {
    ("stop", "sleeping"): "%s is sleeping (no need to stop it); wake it first, then stop, or just rm",
    ("stop", "stopped"): "%s is already stopped",
    ("stop", "stopping"): "%s is stopping; wait until it has stopped; if it never stops (stuck, or SIGSTOP), use sleep to keep it stopped, or rm to detach it (TERM, then KILL after 10s)",
    ("sleep", "sleeping"): "%s is already sleeping",
    ("sleep", "stopped"): "%s is stopped (no need to sleep it); start brings it back",
    ("start", "sleeping"): "%s is sleeping; use wake (start only starts stopped ones)",
    ("start", "running"): "%s is already running",
    ("start", "stopping"): "%s is stopping; start it after it has stopped; if it never stops (stuck, or SIGSTOP), use sleep to keep it stopped, or rm to detach it (TERM, then KILL after 10s)",
    ("wake", "stopped"): "%s is stopped; use start (wake only wakes sleeping ones)",
    ("wake", "running"): "%s is awake (running); no need to wake it",
    ("wake", "stopping"): "%s is stopping, not sleeping",
}


def need_phase(cmd, name, row):
    ph = row.get("phase")
    if ph == "stuck":
        ph = "running"
    if cmd == "sleep" and ph == "stopping":
        return
    if ph != PHASE_OK[cmd]:
        msg = PHASE_HINT.get((cmd, ph), "%%s is %s; %s only takes %s ones" % (ph, cmd, PHASE_OK[cmd]))
        raise Fail("PhaseBad", msg % name)



APPLY_S = 5.0   # pause／resume 等子 loop 套用的上限（暫停中的 loop 每秒讀一次 ctl、閒著的每圈讀）


def write_ctl(d, name, cmd, timeout_s=APPLY_S):
    row = row_of(d, name)
    stack, path = need_ctl(d, name, row)
    # 只收 running（含被標 stuck 的，行程還在）；stopped／sleeping 沒有正在讀 ctl 的行程，應先 start／wake。
    if row.get("phase") not in {"running", "stuck"}:
        raise Fail("PhaseBad", "%s is %s; %s only takes running (or stuck) ones (start or wake it first; no process is reading ctl now)"
                   % (name, row.get("phase"), cmd))
    sname = flux_name(os.path.join(stack, names_of(d)["procs_loop"]))
    seq = next_seq(path, os.path.join(stack, sname) if sname else None)
    put_ctl(path, cmd, seq)
    wait_applied(d, name, stack, cmd, seq, timeout_s)
    return seq


def flux_name(config):
    """設定檔裡的 state_flux 窗名：讀不到用預設，null／非字串＝None（不開）。"""
    try:
        sname = read_loop(config).get("state_flux", STATE_FLUX)
    except Fail:
        sname = STATE_FLUX
    return sname if isinstance(sname, str) and sname else None


def _seq_in(path, key):
    """檔裡 key 的非負整數；檔不在、壞、不是物件或值不對＝None（安靜）。"""
    if path is None:
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError):
        return None
    v = doc.get(key) if isinstance(doc, dict) else None
    return v if isinstance(v, int) and not isinstance(v, bool) and v >= 0 else None


def next_seq(ctl_path, flux_path):
    """新 seq＝max(ctl 現有 seq＋1, state_flux 的 ctl_seq＋1)，讀不到的一邊不算、都沒有＝1。
    坑-62（11-10）：只看 ctl 的話，ctl 被手動清掉後會從 1 重數，撞上舊回音的 ctl_seq 1 就當成已套用。"""
    seqs = [s + 1 for s in (_seq_in(ctl_path, "seq"), _seq_in(flux_path, "ctl_seq")) if s is not None]
    return max(seqs, default=1)


def put_ctl(path, cmd, seq):
    """寫一道 {"cmd", "seq"}：同資料夾暫存 .<名>.<pid>.tmp 再 rename（設計-42：多人同寫不互踩）。"""
    tmp = os.path.join(os.path.dirname(path), ".%s.%d.tmp" % (os.path.basename(path), os.getpid()))
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"cmd": cmd, "seq": seq}) + "\n")
        os.replace(tmp, path)
    except OSError as e:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise Fail("WriteFailed", "cannot write %s: %s" % (path, e))


SHUTDOWN_S = 15.0   # shutdown 等 daemon 退出的上限（收工時子項 SIGTERM、10 秒後 SIGKILL）


def shutdown(d, timeout_s=SHUTDOWN_S):
    """停 daemon 本身（open-11）：先確認它活著，寫它自己 ctl 的 stop、poke，等行程不在；等不到＝提醒行。回傳 seq。"""
    state = read_state(d)
    pid, _ = check_alive(d, state)
    config = os.path.join(d, "daemon.json")
    try:
        cname = read_loop(config).get("ctl", CTL)
    except Fail:
        cname = CTL
    if not isinstance(cname, str) or not cname:
        raise Fail("CtlMissing", "the daemon's ctl window is off (ctl: null); stop it with SIGTERM to pid %d" % pid)
    sname = flux_name(config)
    path = os.path.join(d, cname)
    seq = next_seq(path, os.path.join(d, sname) if sname else None)
    up = state.get("daemon")
    if isinstance(up, str) and up:
        aos_flags.warn(_pkg.PROG, "this daemon is a proc of the daemon at %s; exiting 0 takes it off that table "
                       "(to keep its row, use aos-daemon-ctl --daemon %s stop NAME instead)" % (up, up))
    put_ctl(path, "stop", seq)
    try:
        poke(d, "ctl")
    except Fail as e:
        if e.code != "DaemonMissing":       # 寫完到按門鈴之間就退了＝也算停了
            raise
    end = time.monotonic() + timeout_s
    while True:
        try:
            check_alive(d, state)
        except Fail:
            return seq
        if time.monotonic() >= end:   # 11-10 two-machines：退 0 會讓人以為停乾淨、可以 commit／push 了，所以改成錯誤行退 1
            raise Fail("StillRunning", "the daemon at %s (pid %d) is still running after %g s, so it is not safe to commit or copy "
                       "yet (it stops between rounds: a long body, or procs that take up to 10 s to exit, delay it); it stops "
                       "when it applies stop (seq %d); run shutdown again (it waits again) or give a longer --timeout-s"
                       % (d, pid, timeout_s, seq))
        time.sleep(0.05)



def wait_applied(d, name, stack, cmd, seq, timeout_s=APPLY_S):
    """等子 loop 的 state_flux 窗 ctl_seq 追上 seq；state_flux 窗是 null＝不等；等不到＝提醒行。"""
    sname = flux_name(os.path.join(stack, names_of(d)["procs_loop"]))
    if sname is None:
        return
    spath, end = os.path.join(stack, sname), time.monotonic() + timeout_s
    while True:
        st = aos_flags.read_window(_pkg.PROG, spath)
        got = st.get("ctl_seq") if st is not None else None
        if got == seq:
            return
        if time.monotonic() >= end:
            aos_flags.warn(_pkg.PROG, "%s has not applied %s (seq %d) within %g s (it reads its ctl between steps; a long step delays it); "
                           "a stop or sleep sent before it applies overwrites or drops it" % (name, cmd, seq, timeout_s))
            return
        time.sleep(0.05)
