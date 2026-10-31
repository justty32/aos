"""aos_ai_daemon - aos-ai 的背景命令：daemon up｜down｜status、start、stop（一個 root 一個 aos-daemon，寫它的 ctl）。

10-31 自 bin/aos-ai 拆出（行為不變）。"""
import fcntl, json, subprocess, time
from aos_ai_base import Daemon, Fail, HINTS, child_env, need, now, out, read_text, ticks, which, write_atomic


def daemon_up(root):
    d = Daemon(root)
    pid = d.running()
    if pid:
        return pid, True
    d.stack.mkdir(parents=True, exist_ok=True)       # aos-daemon 不自己建 stack（N-59 第 1 件）
    if not d.cfg.exists():
        write_atomic(d.cfg, json.dumps({"interval_ms": 500, "ctl": "ctl.json", "state": "state.json", "loops": {}},
                                       indent=1) + "\n")
    d.write_ctl(lambda c: c.pop("stopped", None))    # 上次 down 留下的 stopped 拿掉；loops_ctl 的 loops_added 照留＝上次在跑的照起
    prog = which("aos-daemon")
    if not prog:
        raise Fail("CommandMissing", "PATH 上沒有 aos-daemon", HINTS["CommandMissing"])
    with open(d.dir / "stderr.txt", "a") as err:
        p = subprocess.Popen([prog, str(d.cfg)], cwd=d.dir, env=child_env({"AOS_STACK": str(d.stack) + "/"}),
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=err, start_new_session=True)
    for _ in range(50):
        if ticks(p.pid) is not None:
            break
        time.sleep(0.02)
    write_atomic(d.dir / "up.json", json.dumps({"pid": p.pid, "started_at_ticks": ticks(p.pid), "started_at": now()}) + "\n")
    time.sleep(0.3)
    if p.poll() is not None:
        raise Fail("DaemonFailed", "aos-daemon 起來就結束了（碼 %s）：%s" % (p.returncode, (read_text(d.dir / "stderr.txt") or "")[-300:]))
    return p.pid, False


def cmd_daemon(root, o, pos):
    need(pos, 1, "daemon up|down|status")
    d = Daemon(root)
    if pos[0] == "up":
        pid, already = daemon_up(root)
        out({"ok": True, "pid": pid, "already_running": already, "dir": str(d.dir)})
    elif pos[0] == "down":
        pid = d.running()
        if not pid:
            out({"ok": True, "running": False})
            return
        d.write_ctl(lambda c: c.__setitem__("stopped", True))
        end = time.monotonic() + 20
        while d.running() and time.monotonic() < end:
            time.sleep(0.2)
        st = d.read_state() or {}
        out({"ok": not d.running(), "running": bool(d.running()), "phase": st.get("phase"), "code": st.get("code")})
    elif pos[0] == "status":
        st = d.read_state() or {}
        ls = d.read_lstate() or {}
        out({"ok": True, "running": bool(d.running()), "pid": d.running(), "phase": st.get("phase"),
             "loops": ls.get("loops") or {}, "ctl_seq": st.get("ctl_seq"), "ctl_warning": st.get("ctl_warning"),
             "loops_ctl_seq": ls.get("ctl_seq"), "loops_ctl_warning": ls.get("ctl_warning"),
             "recorded_at": st.get("recorded_at"), "stderr_tail": (read_text(d.dir / "stderr.txt") or "")[-500:] or None})
    else:
        raise Fail("ArgumentsBad", "daemon 只認 up、down、status：%s" % pos[0])


def cmd_start(root, o, pos):
    need(pos, 1, "start NAME [--interval-ms N]")
    a = root.agent(pos[0])
    with open(a.base / ".run.flock", "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise Fail("AgentBusy", "%s 正在前景 aos-ai run" % a.name, "等它跑完")
    daemon_up(root)
    d = Daemon(root)
    spec = {"exec": {"argv": ["aos-exec", "--ws", str(a.ws), str(a.agent)], "envs": {"AOS_STACK": str(a.stack) + "/"}},
            "interval_ms": int(o.get("interval-ms", ["2000"])[-1])}
    row = d.row(a.name)
    if row and row.get("phase") in ("running", "stopping"):
        out({"ok": True, "name": a.name, "already_running": True, "background": row})
        return
    if row:                                            # done／stopped 還在表上：拿掉、等它下表，再放回（daemon 不自己重起）
        seq = d.write_ctl(lambda c: (c.setdefault("loops_added", {}).pop(a.name, None)), d.lctl)
        d.wait_seq(seq, until=lambda st: a.name not in (st.get("loops") or {}))
    seq = d.write_ctl(lambda c: c.setdefault("loops_added", {}).__setitem__(a.name, spec), d.lctl)
    st, acked = d.wait_seq(seq, until=lambda st: a.name in (st.get("loops") or {}))
    row = (st.get("loops") or {}).get(a.name)
    res = {"ok": acked and bool(row), "name": a.name, "background": row, "ctl_warning": st.get("ctl_warning"),
           "next": "aos-ai ask %s …，再 aos-ai wait %s <信號>" % (a.name, a.name)}
    if not res["ok"]:
        res["hint"] = "daemon 沒接到（ctl_warning 或 aos-ai daemon status 看）"
    out(res)


def cmd_stop(root, o, pos):
    need(pos, 1, "stop NAME")
    a = root.agent(pos[0])
    d = Daemon(root)
    if not d.running():
        out({"ok": True, "name": a.name, "background": None, "note": "daemon 沒在跑"})
        return
    seq = d.write_ctl(lambda c: c.setdefault("loops_added", {}).pop(a.name, None), d.lctl)
    st, acked = d.wait_seq(seq, until=lambda st: (st.get("loops") or {}).get(a.name, {}).get("phase") != "running")
    out({"ok": acked, "name": a.name, "background": (st.get("loops") or {}).get(a.name),
         "note": "已叫停；正在跑的那次收完才真的停（stopping → 下表）"})
