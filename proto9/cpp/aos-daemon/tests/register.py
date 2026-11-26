#!/usr/bin/env python3
# register.py：aos-daemon 測試裡跟 register（外來登記）有關的兩組——驗身分（status 的 aos_name 要對）、名字不能被搶、只收 rm；proc 自己在 settings 寫 aos_obey 讓 daemon 能 stop／kill 它、daemon 停時一起停。
import os, subprocess
from common import (start_daemon, start_demo, read_kv, table, ctl, wait_until, alive, our_mounts, check, phase_is, pctl,
                    stop_daemon, env)


def _err(st):
    return st.get("aos_procs_ctl_error", "")


def _stop_demo(q, qroot):
    ctl(qroot + "/ctl", "stop")
    try:
        q.wait(5)
    except subprocess.TimeoutExpired:
        pass


def t_register():
    p, pid, root, base = start_daemon("register")
    q, qpid, qroot, qmnt = start_demo("ext")
    rc, err, st = pctl(root, "register ext %d" % qpid)
    ok = phase_is(root, "ext", "running")
    t = table(root, "ext")
    check("register ext PID -> done, procs/ext/status readable, marked external, obey -",
          rc == 0 and st.get("aos_procs_ctl_state") == "done" and ok
          and (read_kv(root + "/procs/ext/status") or {}).get("aos_name") == "ext"
          and t.get("external") == "yes" and t.get("obey") == "-", (err, st, t))
    refused = {w: ctl(root + "/procs_ctl", "%s ext" % w)[0] for w in ("kill", "stop", "start")}
    st = read_kv(root + "/status") or {}
    check("no aos_obey line: kill, stop, start are refused (ProcExternal), process untouched",
          all(rc != 0 for rc in refused.values()) and _err(st).startswith("ProcExternal") and alive(qpid), (refused, st))
    rc, _, _ = ctl(root + "/procs_ctl", "register ext %d" % os.getpid())
    check("a name already in the table cannot be taken by register (ProcExists)", rc != 0
          and _err(read_kv(root + "/status") or {}).startswith("ProcExists"))
    rc, err, st = pctl(root, "rm ext")
    check("rm ext -> off the table; the process and its mount are untouched",
          rc == 0 and st.get("aos_procs_ctl_state") == "done" and table(root, "ext") == {} and alive(qpid)
          and qmnt in our_mounts(), (err, st))
    # 冒名：那隻自己的 status 說 aos_name: ext，拿 other 來登記
    rc, err, st = pctl(root, "register other %d" % qpid)
    check("register other PID where its status says aos_name ext: failed NameMismatch, not on the table",
          rc == 0 and st.get("aos_procs_ctl_state") == "failed" and _err(st).startswith("NameMismatch")
          and table(root, "other") == {}, (err, st))
    sl = subprocess.Popen(["/bin/sleep", "30"], cwd="/", env=env())
    rc, err, st = pctl(root, "register sl %d" % sl.pid)
    sl.kill()
    sl.wait()
    check("register a process that serves no status: failed StatusUnreadable, not on the table",
          rc == 0 and st.get("aos_procs_ctl_state") == "failed" and _err(st).startswith("StatusUnreadable")
          and table(root, "sl") == {}, (err, st))
    pctl(root, "register ext %d" % qpid)
    phase_is(root, "ext", "running")
    stop_daemon(p, root, "register")
    check("daemon stop leaves a registered proc (no aos_obey) alive with its mount", alive(qpid) and qmnt in our_mounts())
    _stop_demo(q, qroot)


def t_obey():
    p, pid, root, base = start_daemon("obey")
    a, apid, aroot, amnt = start_demo("ob", "--obey", "stop kill")
    b, bpid, broot, bmnt = start_demo("os", "--obey", "stop")
    for n, x in (("ob", apid), ("os", bpid)):
        pctl(root, "register %s %d" % (n, x))
        phase_is(root, n, "running")
    check("aos_obey from the proc's own settings lands in the table (ob: stop kill, os: stop)",
          table(root, "ob").get("obey") == "stop kill" and table(root, "os").get("obey") == "stop", (table(root, "ob"), table(root, "os")))
    rc1, _, _ = ctl(root + "/procs_ctl", "kill os")
    rc2, _, _ = ctl(root + "/procs_ctl", "start ob")
    check("os does not obey kill, start is never allowed for registered procs: both refused", rc1 != 0 and rc2 != 0 and alive(bpid))
    rc, err, st = pctl(root, "stop ob")
    ok = phase_is(root, "ob", "stopped")
    check("stop ob (obeys stop) -> stop written to its ctl, it exits, table says stopped",
          rc == 0 and st.get("aos_procs_ctl_state") == "done" and ok and wait_until(lambda: not alive(apid), 3), (err, st, table(root, "ob")))
    a.wait(5)
    pctl(root, "rm ob")
    a, apid, aroot, amnt = start_demo("ob", "--obey", "stop kill", tag="2")
    pctl(root, "register ob %d" % apid)
    phase_is(root, "ob", "running")
    rc, err, st = pctl(root, "kill ob")
    ok = phase_is(root, "ob", "stopped")
    t = table(root, "ob")
    check("kill ob (obeys kill) -> process killed, reason killed by procs_ctl kill, its dead mount cleaned",
          rc == 0 and ok and wait_until(lambda: not alive(apid), 3) and t.get("reason") == "killed by procs_ctl kill"
          and wait_until(lambda: amnt not in our_mounts(), 3), (err, st, t, our_mounts()))
    a.wait(5)
    stop_daemon(p, root, "obey")
    check("daemon stop also stops a registered proc that obeys stop (os exits, its mount is gone)",
          wait_until(lambda: not alive(bpid) and bmnt not in our_mounts(), 3), (alive(bpid), our_mounts()))
    try:
        b.wait(5)
    except subprocess.TimeoutExpired:
        pass
