"""aos_sweep_proc 清道夫的行程那半：認出這台 daemon 預設小格裡「表上沒有、但還活著、確定是這台生的」子 loop，先寫它的 ctl stop，過寬限還在才 TERM／10 秒後 KILL；真 zombie 只報。
只收有十足把握的那一類（使用者 11-10 題 2 選 A）：格在 D/procs/<名>/、表上沒有任何一列的 stack 是它、它自己的 state 窗 pid＋started_at_ticks＋boot_id
對得上 /proc（同 daemon adopt 的 live_in_cell，但 boot_id 必須有）、/proc/<pid>/environ 的 AOS_STACK＝這格、AOS_DAEMON＝這台、活了 60 秒以上。
daemon 不在（state 窗對不上 /proc）＝不碰任何行程：活著的子項本來就是等下一台接回的。
讀 /proc、送訊號是 N-17「只有 daemon 碰 pid」的第二個例外（第一個是 poke）。寫過 stop 的記在 D/.sweeper_pending.json（點開頭＝不進 image）。"""
import json
import os
import signal
import time

import aos_flags
import daemon_ctl as dc

PENDING = ".sweeper_pending.json"
STOP_GRACE_S = 300      # 寫了 stop 之後，至少這麼久、而且是之後的某一輪還在，才送訊號
MIN_AGE_S = 60          # 剛 fork、daemon 還沒寫表的窗
TERM_WAIT_S = 10        # SIGTERM 後等幾秒才 SIGKILL（同 daemon 收子項的 grace）


def _stat(pid):
    """/proc/pid/stat →（狀態字母, ppid, pgrp, starttime, comm）；讀不到丟 OSError／ValueError／IndexError。"""
    with open("/proc/%d/stat" % pid, encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    comm = text[text.index("(") + 1:text.rindex(")")]
    f = text[text.rindex(")") + 1:].split()
    return f[0], int(f[1]), int(f[2]), int(f[19]), comm


def _boot_id():
    try:
        with open("/proc/sys/kernel/random/boot_id", encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return None


def _age_s(ticks):
    """行程活了幾秒（/proc/uptime 減 starttime）；讀不到＝0（當作太年輕，不動）。"""
    try:
        with open("/proc/uptime", encoding="utf-8") as fh:
            up = float(fh.read().split()[0])
        return up - ticks / os.sysconf("SC_CLK_TCK")
    except (OSError, ValueError, IndexError):
        return 0.0


def _environ(pid):
    """/proc/pid/environ 的 dict；讀不到（別的帳號＝EPERM）丟 OSError。"""
    with open("/proc/%d/environ" % pid, "rb") as fh:
        raw = fh.read()
    out = {}
    for item in raw.split(b"\0"):
        k, eq, v = item.partition(b"=")
        if eq:
            out[k.decode("utf-8", "replace")] = v.decode("utf-8", "replace")
    return out


def _same(pid, ticks):
    """pid 還是那支（starttime 相同、不是 zombie）。"""
    try:
        letter, _pp, _pg, start, _c = _stat(pid)
    except (OSError, ValueError, IndexError):
        return False
    return start == ticks and letter not in ("Z", "X")


def _table():
    """全機 /proc：{pid: (狀態, ppid, pgrp, comm)}；讀不到的跳過。"""
    out = {}
    for n in os.listdir("/proc"):
        if n.isdigit():
            try:
                letter, pp, pg, _s, comm = _stat(int(n))
            except (OSError, ValueError, IndexError):
                continue
            out[int(n)] = (letter, pp, pg, comm)
    return out


def _below(procs, roots):
    """roots 底下（子、孫…）的 pid。"""
    kids = {}
    for pid, (_l, pp, _g, _c) in procs.items():
        kids.setdefault(pp, []).append(pid)
    out, todo = [], list(roots)
    while todo:
        for k in kids.get(todo.pop(), ()):
            if k not in out:
                out.append(k)
                todo.append(k)
    return out


def _cfg(cell, loop_name):
    """格裡父寫的 loop 設定：（state 窗名, ctl 名, state_flux 名）；沒寫用預設，null＝None。"""
    try:
        with open(os.path.join(cell, loop_name), encoding="utf-8") as fh:
            cfg = json.load(fh)
    except (OSError, ValueError):
        cfg = {}
    if not isinstance(cfg, dict):
        cfg = {}

    def name(key, default):
        v = cfg.get(key, default)
        return v if isinstance(v, str) and v else None
    return name("state", "state.json"), name("ctl", "ctl.json"), name("state_flux", "state_flux.json")


def _orphan(prog, d, cell, loop_name, boot):
    """這格是不是「確定是這台生的、還活著」的子 loop：回（pid, ticks, 說明）；不是＝(None, None, 為什麼要報或 None＝正常不報)。"""
    sname, _c, _f = _cfg(cell, loop_name)
    if sname is None:
        return None, None, None
    st = aos_flags.read_window(prog, os.path.join(cell, sname))
    if st is None:
        return None, None, None
    pid, ticks, sboot = st.get("pid"), st.get("started_at_ticks"), st.get("boot_id")
    if type(pid) is not int or pid <= 0 or type(ticks) is not int:
        return None, None, None
    if boot is None or not isinstance(sboot, str) or sboot != boot:
        # 別次開機或別台機器（stack 經 git／cp 搬來）寫的窗：一定不是這台這次生的。pid 剛好撞到本機活著的行程才報一句，否則是正常的空格。
        if os.path.exists("/proc/%d" % pid):
            return None, pid, "its state window is from another boot or another machine (boot_id differs); pid %d here is someone else; left alone" % pid
        return None, None, None
    if not _same(pid, ticks):
        return None, None, None
    try:
        env = _environ(pid)
    except OSError as e:
        return None, pid, "alive but cannot read its environment (%s); left alone" % (e.strerror or e)
    if env.get("AOS_STACK", "").rstrip("/") != cell or env.get("AOS_DAEMON", "").rstrip("/") != d:
        return None, pid, "alive but not started by this daemon for this cell; left alone"
    if _age_s(ticks) < MIN_AGE_S:
        return None, pid, "alive and off the table but younger than %d s; looked at again next round" % MIN_AGE_S
    return pid, ticks, None


def _signal(pid, ticks):
    """先 pidfd 核身分再 SIGTERM 整群（setsid 過＝群組長是它）＋底下自成一群的；10 秒後還在就 SIGKILL。回結果句。"""
    procs = _table()
    below = [p for p in _below(procs, [pid]) if procs[p][2] == p]   # 底下自己當群組長的（inst 起的單子）
    try:
        fd = os.pidfd_open(pid)
    except ProcessLookupError:
        return "gone before the signal"
    except OSError as e:
        return "cannot signal: %s" % (e.strerror or e)
    try:
        if not _same(pid, ticks):
            return "gone before the signal"
        signal.pidfd_send_signal(fd, signal.SIGTERM)
        for g in below:
            _killpg(g, signal.SIGTERM)
        group = procs.get(pid, (None, None, None))[2] == pid
        if group:
            _killpg(pid, signal.SIGTERM)
        end = time.monotonic() + TERM_WAIT_S
        while time.monotonic() < end:
            if not _same(pid, ticks):
                return "sent SIGTERM; it exited"
            time.sleep(0.1)
        if _same(pid, ticks):
            signal.pidfd_send_signal(fd, signal.SIGKILL)
        if group:
            _killpg(pid, signal.SIGKILL)
        for g in below:
            _killpg(g, signal.SIGKILL)
        return "sent SIGTERM, then SIGKILL after %d s" % TERM_WAIT_S
    except ProcessLookupError:
        return "sent SIGTERM; it exited"
    except PermissionError:
        return "cannot signal: permission denied (another account); left alone"
    finally:
        os.close(fd)


def _killpg(g, sig):
    try:
        os.killpg(g, sig)
    except (ProcessLookupError, PermissionError):
        pass


def _load(path):
    try:
        with open(path, encoding="utf-8") as fh:
            v = json.load(fh)
        return v if isinstance(v, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(rep, path, pending):
    try:
        if not pending:
            if os.path.lexists(path):
                os.unlink(path)
            return
        tmp = "%s.%d.tmp" % (path, os.getpid())
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(pending) + "\n")
        os.replace(tmp, path)
    except OSError as e:
        rep.warn("cannot write %s: %s" % (path, e.strerror or e))


def check(rep, d, st, loop_name, stop_grace_s, dry_run, now):
    """行程那半的一輪；結果寫進 rep.data["processes"]。"""
    out = rep.data["processes"]
    try:
        pid, _t = dc.check_alive(d, dc.read_state(d))
    except dc.Fail as e:
        out["note"] = "daemon not running (%s); processes left alone" % e
        return
    out["checked"] = True
    boot = _boot_id()
    path = os.path.join(d, PENDING)
    pending = _load(path)
    keep = {}
    on_table = {os.path.realpath(r["stack"]) for r in st["procs"].values() if isinstance(r, dict) and isinstance(r.get("stack"), str)}
    seen = set()
    for cell in cells(d):
        if os.path.realpath(cell) in on_table:
            continue
        opid, ticks, why = _orphan(rep.prog, d, cell, loop_name, boot)
        label = "procs/" + os.path.basename(cell)
        if opid is not None or ticks is not None:
            seen.add(cell)
        if opid is None:
            if why:
                out["orphans"].append({"cell": label, "pid": ticks, "action": why})
            continue
        try:                                          # 動手前重讀一次表：剛 add 上表的不收
            if os.path.realpath(cell) in {os.path.realpath(r["stack"]) for r in dc.state(d)["procs"].values()
                                          if isinstance(r, dict) and isinstance(r.get("stack"), str)}:
                continue
        except dc.Fail:
            out["orphans"].append({"cell": label, "pid": opid, "action": "table unreadable on re-check; left alone"})
            continue
        was = pending.get(cell)
        same = isinstance(was, dict) and was.get("pid") == opid and was.get("ticks") == ticks
        if same and now - was.get("stop_at", now) >= stop_grace_s:
            action = ("would signal (stop written %d s ago)" % (now - was["stop_at"])) if dry_run else _signal(opid, ticks)
            if dry_run or _same(opid, ticks):
                keep[cell] = was
        elif same:
            action = "stop written %d s ago; signals after %d s" % (now - was["stop_at"], stop_grace_s)
            keep[cell] = was
        else:
            _s, cname, fname = _cfg(cell, loop_name)
            if cname is None:
                action = "off the table, alive, but its ctl window is off; left alone"
            elif dry_run:
                action = "would write stop to %s" % os.path.join(cell, cname)
            else:
                cpath = os.path.join(cell, cname)
                try:
                    seq = dc.next_seq(cpath, os.path.join(cell, fname) if fname else None)
                    dc.put_ctl(cpath, "stop", seq)
                    action = "off the table; wrote stop (seq %d) to %s" % (seq, cpath)
                    keep[cell] = {"pid": opid, "ticks": ticks, "stop_at": now, "seq": seq}
                except dc.Fail as e:
                    action = "cannot write stop: %s" % e
        out["orphans"].append({"cell": label, "pid": opid, "action": action})
    for cell, was in pending.items():
        if cell not in seen:
            out["orphans"].append({"cell": "procs/" + os.path.basename(cell), "pid": was.get("pid") if isinstance(was, dict) else None,
                                   "action": "exited after the stop"})
    if not dry_run:
        _save(rep, path, keep)
    _zombies(out, pid, st)


def cells(d):
    """D/procs/ 底下的預設小格（daemon 自己的固定名）；不在＝沒有。"""
    base = os.path.join(d, "procs")
    try:
        with os.scandir(base) as it:
            return sorted(e.path for e in it if e.is_dir(follow_symlinks=False))
    except OSError:
        return []


def _zombies(out, dpid, st):
    """daemon 與表上各列底下的真 zombie（已死、等父 wait）：只報，外人收不掉。"""
    procs = _table()
    roots = [dpid] + [r["pid"] for r in st["procs"].values() if isinstance(r, dict) and type(r.get("pid")) is int]
    for p in _below(procs, roots):
        letter, pp, _g, comm = procs[p]
        if letter == "Z":
            out["zombies"].append({"pid": p, "ppid": pp, "comm": comm})
