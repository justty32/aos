"""daemon_ctl 控制：檢查 proc 階段、依公開窗名寫入控制並等待套用。"""
import json
import os
import time

import aos_flags
import daemon_ctl as _pkg

from .base import Fail, STATE_FLUX
from .entry import read_loop
from .table import cell_of, names_of, row_of



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
    # 只收 running 的；stopped／sleeping 沒有正在讀 ctl 的行程，應先 start／wake。
    if row.get("phase") not in {"running", "stuck"}:
        raise Fail("PhaseBad", "%s is %s; %s only takes running ones (start or wake it first; no process is reading ctl now)"
                   % (name, row.get("phase"), cmd))
    try:
        with open(path, encoding="utf-8") as fh:
            old = json.load(fh)
        seq = old.get("seq") if isinstance(old, dict) else None
    except (OSError, ValueError):
        seq = None
    seq = seq + 1 if isinstance(seq, int) and not isinstance(seq, bool) and seq >= 0 else 1
    tmp = os.path.join(os.path.dirname(path), "." + os.path.basename(path))
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"cmd": cmd, "seq": seq}) + "\n")
        os.replace(tmp, path)
    except OSError as e:
        raise Fail("WriteFailed", "cannot write %s: %s" % (path, e))
    wait_applied(d, name, stack, cmd, seq, timeout_s)
    return seq





def wait_applied(d, name, stack, cmd, seq, timeout_s=APPLY_S):
    """等子 loop 的 state_flux 窗 ctl_seq 追上 seq；state_flux 窗是 null＝不等；等不到＝提醒行。"""
    try:
        sname = read_loop(os.path.join(stack, names_of(d)["procs_loop"])).get("state_flux", STATE_FLUX)
    except Fail:
        sname = STATE_FLUX
    if not isinstance(sname, str) or not sname:
        return
    spath, end = os.path.join(stack, sname), time.monotonic() + timeout_s
    while True:
        try:
            with open(spath, encoding="utf-8") as fh:
                got = json.load(fh).get("ctl_seq")
        except (OSError, ValueError, AttributeError):
            got = None
        if got == seq:
            return
        if time.monotonic() >= end:
            aos_flags.warn(_pkg.PROG, "%s has not applied %s (seq %d) within %g s (it reads its ctl between steps; a long step delays it); "
                           "a stop or sleep sent before it applies overwrites or drops it" % (name, cmd, seq, timeout_s))
            return
        time.sleep(0.05)
