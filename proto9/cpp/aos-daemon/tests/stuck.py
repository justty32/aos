#!/usr/bin/env python3
# stuck.py：aos-daemon 測試裡跟「卡住」有關的幾組——底下的被暫停時 daemon 照常快、kill 放開被拖住的人、procs_ctl 的鎖、帶著卡住的收尾。
import os, signal, subprocess, time
from common import (DEMO, start_daemon, sh, bg, timed, read_kv, table, ctl, wait_until, alive, our_mounts,
                    check, phase_is, pctl_done, stop_daemon)


def t_stuck():
    p, pid, root, base = start_daemon("stuck")
    for n in ("a", "b"):
        ctl(root + "/procs_ctl", "add %s %s" % (n, DEMO))
        phase_is(root, n, "running")
    apid = int(table(root, "a")["pid"])
    os.kill(apid, signal.SIGSTOP)
    ok = wait_until(lambda: table(root, "a").get("stuck", "no") != "no", 4)
    check("a SIGSTOPped -> stuck has a time within seconds", ok, table(root, "a"))
    check("stuck a: procs/a is gone", not os.path.lexists(root + "/procs/a"))
    times = []
    for cmd in ("cat %s/status" % root, "cat %s/procs_status" % root, "echo 'stop b' > %s/procs_ctl" % root,
                "echo 'add c %s' > %s/procs_ctl" % (DEMO, root)):
        rc, _, err, dt = timed(cmd, 3)
        times.append((rc, round(dt * 1000, 1)))
        pctl_done(root)
    check("while a is stuck: status, procs_status, procs_ctl stop b / add c all fast (ms: %s)" % [t[1] for t in times],
          all(rc == 0 and ms < 500 for rc, ms in times), times)
    check("... and they took effect (b stopped, c running)", phase_is(root, "b", "stopped") and phase_is(root, "c", "running"))
    os.kill(apid, signal.SIGCONT)
    ok = wait_until(lambda: table(root, "a").get("stuck") == "no" and os.path.lexists(root + "/procs/a"), 4)
    check("SIGCONT -> stuck no, procs/a back", ok, table(root, "a"))

    os.kill(apid, signal.SIGSTOP)
    wait_until(lambda: table(root, "a").get("stuck", "no") != "no", 4)
    reader = bg("cat /proc/%d/cwd/status" % apid)
    time.sleep(0.3)
    hung = reader.poll() is None
    rc, _, err, dt = timed("echo 'kill a' > %s/procs_ctl" % root, 3)
    try:
        reader.communicate(timeout=3)
        rrc = reader.returncode
    except subprocess.TimeoutExpired:
        rrc = None
    check("kill stuck a: procs_ctl answers fast (%.1f ms), the hung reader is released" % (dt * 1000),
          hung and rc == 0 and dt < 0.5 and rrc not in (None, 0), (hung, rc, err, rrc))
    ok = phase_is(root, "a", "stopped")
    t = table(root, "a")
    check("a is gone: process dead, reason killed by procs_ctl kill, mount cleaned", ok and not alive(apid)
          and t.get("reason") == "killed by procs_ctl kill" and wait_until(lambda: os.path.join(base, "a") not in our_mounts(), 3), t)
    stop_daemon(p, root, "stuck")


def t_lock():
    p, pid, root, base = start_daemon("lock")
    ctl(root + "/procs_ctl", "add z %s" % DEMO)
    phase_is(root, "z", "running")
    zpid = int(table(root, "z")["pid"])
    os.kill(zpid, signal.SIGSTOP)
    # add 的路徑指到卡住的 proc 裡：daemon 只在拋棄式小行程裡讀它，procs_ctl 鎖到 ctl-timeout（1 秒）就放棄
    first = bg("echo 'add y /proc/%d/cwd/_metainfo.json' > %s/procs_ctl" % (zpid, root))
    time.sleep(0.3)
    rc, _, err = ctl(root + "/procs_ctl", "stop z")
    st = read_kv(root + "/status") or {}
    check("procs_ctl locked by a slow command: another writer gets busy", rc != 0 and "busy" in err
          and st.get("aos_procs_ctl_cmd", "").startswith("add y"), (rc, err, st))
    out = first.communicate(timeout=5)
    st = wait_until(lambda: (read_kv(root + "/status") or {}).get("aos_procs_ctl_state") == "failed" and read_kv(root + "/status"), 3) or {}
    check("the slow add gives up after the deadline (failed, PathBad ... timed out), daemon still answers",
          "timed out" in st.get("aos_procs_ctl_error", ""), (out, st))
    os.kill(zpid, signal.SIGCONT)
    stop_daemon(p, root, "lock")


def t_stopstuck():
    p, pid, root, base = start_daemon("stopstuck")
    for n in ("a", "b"):
        ctl(root + "/procs_ctl", "add %s %s" % (n, DEMO))
        phase_is(root, n, "running")
    apid, bpid = int(table(root, "a")["pid"]), int(table(root, "b")["pid"])
    os.kill(apid, signal.SIGSTOP)
    wait_until(lambda: table(root, "a").get("stuck", "no") != "no", 4)
    t0 = time.time()
    ctl(root + "/procs_ctl", "stop a")
    st = pctl_done(root)
    dt = time.time() - t0
    err = st.get("aos_procs_ctl_error", "")
    check("stop on a stuck proc gives up within ctl-timeout (%.2f s): %s" % (dt, err.split(" ")[0]),
          dt < 2 and st.get("aos_procs_ctl_state") == "failed" and (err.startswith("CtlTimeout") or err.startswith("ProcStuck")), st)
    rc, _, e = ctl(root + "/procs_ctl", "kill a")
    check("... then kill goes in", rc == 0 and phase_is(root, "a", "stopped"), e)
    ctl(root + "/procs_ctl", "start a")
    phase_is(root, "a", "running")
    apid = int(table(root, "a")["pid"])
    os.kill(apid, signal.SIGSTOP)
    t0 = time.time()
    rc, _, _ = ctl(root + "/ctl", "stop")
    mid = read_kv(root + "/status", 1) or {}
    try:
        code = p.wait(10)
    except subprocess.TimeoutExpired:
        code = None
    dt = time.time() - t0
    check("daemon stop with a stuck child: status still readable while stopping", mid.get("aos_phase") == "stopping", mid)
    check("... forces it after stop-timeout and exits (%.1f s)" % dt, code == 0 and 2.5 < dt < 8, code)
    check("... both children gone, no mounts left", not alive(apid) and not alive(bpid)
          and wait_until(lambda: our_mounts() == [], 3), our_mounts())
