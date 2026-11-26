#!/usr/bin/env python3
# run.py：aos-daemon 的測試——起根 daemon、用 aos-procfs-demo 當底下的 proc，逐條驗 procs/、procs_ctl、procs_status、卡住、嵌套、收尾；每條印 ok／FAIL，最後印總數並收乾淨（卡住的幾組在 stuck.py）。
"""用法：python3 tests/run.py [測試名 ...]   （不給＝全部；名字見 TESTS）"""
import json, os, signal, subprocess, sys, time
from common import (DAEMON, DEMO, SCRATCH, FAST, start_daemon, start_demo, sh, read_kv, table, ctl, wait_until, alive,
                    our_mounts, marked, cleanup, leftovers, env, results, check, spec, phase_is, pctl_done, pctl, own_ctl,
                    stop_daemon)
from stuck import t_stuck, t_lock, t_stopstuck
from register import t_register, t_obey

def t_self():
    p, pid, root, base = start_daemon("self")
    st = read_kv(root + "/status") or {}
    want = ["aos_name", "aos_phase", "aos_pid", "aos_started_at", "aos_ctl_cmd", "aos_ctl_state", "aos_ctl_error",
            "aos_ctl_count", "aos_procs", "aos_procs_ctl_cmd", "aos_procs_ctl_state", "aos_procs_ctl_error", "aos_procs_ctl_count"]
    check("status has the 8 lines + aos_procs + 4 procs_ctl lines", all(k in st for k in want), st)
    check("root: aos_name is /, aos_pid is the daemon", st.get("aos_name") == "/" and st.get("aos_pid") == str(pid), st)
    rc, out, _ = sh("cat %s/attrs %s/settings %s/_metainfo.json; ls %s/procs %s/proc/" % ((root,) * 5))
    check("attrs, settings, _metainfo.json, procs/ and proc/ readable", rc == 0 and "aos_live: yes" in out and "aos_persists" in out, out)
    own_ctl(root, "pause")
    st = read_kv(root + "/status") or {}
    rc, _, err = ctl(root + "/procs_ctl", "add x %s" % DEMO)
    check("pause -> aos_phase paused; add is refused while paused", st.get("aos_phase") == "paused" and rc != 0
          and (read_kv(root + "/status") or {}).get("aos_procs_ctl_error", "").startswith("DaemonPaused"), (st, err))
    own_ctl(root, "resume")
    rc, _, err = ctl(root + "/procs_ctl", "frobnicate x")
    st = read_kv(root + "/status") or {}
    check("unknown procs_ctl word: write fails, rejected CommandUnknown", rc != 0 and st.get("aos_procs_ctl_state") == "rejected"
          and st.get("aos_procs_ctl_error", "").startswith("CommandUnknown"), (rc, st))
    rc1, _, _ = ctl(root + "/procs_ctl", "add x relative/path")
    rc2, _, _ = ctl(root + "/procs_ctl", "stop nosuch")
    rc3, _, _ = ctl(root + "/procs_ctl", "add ../x %s" % DEMO)
    check("relative path, unknown name, bad name: all refused", rc1 != 0 and rc2 != 0 and rc3 != 0, (rc1, rc2, rc3))
    stop_daemon(p, root, "self")


def t_add():
    p, pid, root, base = start_daemon("add")
    rc, _, err = ctl(root + "/procs_ctl", "add kid %s" % DEMO)
    ok = phase_is(root, "kid", "running")
    st = read_kv(root + "/procs/kid/status") or {}
    check("add kid DEMO -> procs/kid/status readable (aos_name kid)", rc == 0 and ok and st.get("aos_name") == "kid", (err, st))
    t = table(root, "kid")
    check("procs_status has kid: running, want up, pid, stuck no", t.get("want") == "up" and t.get("pid") == st.get("aos_pid")
          and t.get("stuck") == "no", t)
    check("proc/kid is the same place", (read_kv(root + "/proc/kid/status") or {}).get("aos_pid") == st.get("aos_pid"))
    kmnt = os.path.join(base, "kid")
    check("kid is mounted under --mount-base", kmnt in our_mounts(), our_mounts())
    s = spec(os.path.join(SCRATCH, "persists.json"), [DEMO, "--persists", "/tmp/aos-test-persists"])
    pctl(root, "add pj %s" % s)
    ok = phase_is(root, "pj", "running")
    check("add via json spec; settings aos_persists recorded in the table", ok and table(root, "pj").get("persists") == "/tmp/aos-test-persists",
          table(root, "pj"))

    rc, _, err = ctl(root + "/procs_ctl", "stop kid")
    ok = phase_is(root, "kid", "stopped")
    t = table(root, "kid")
    check("stop kid -> stopped, want down, code 0, reason stopped", rc == 0 and ok and t.get("want") == "down"
          and t.get("code") == "0" and t.get("reason") == "stopped", (err, t))
    check("after stop: link gone, mount gone, still on the table",
          wait_until(lambda: not os.path.lexists(root + "/procs/kid") and kmnt not in our_mounts(), 3) and "pid" in t)
    rc, _, err = ctl(root + "/procs_ctl", "start kid")
    ok = phase_is(root, "kid", "running")
    check("start kid -> running again, procs/kid readable", rc == 0 and ok and read_kv(root + "/procs/kid/status") is not None, err)
    kpid = int(table(root, "kid").get("pid", "0"))
    rc, _, err = ctl(root + "/procs_ctl", "rm kid")
    gone = wait_until(lambda: table(root, "kid") == {} and not alive(kpid))
    check("rm kid -> off the table, process gone", rc == 0 and gone, (err, table(root, "kid")))
    stop_daemon(p, root, "add")


def t_crash():
    p, pid, root, base = start_daemon("crash")
    ctl(root + "/procs_ctl", "add kid %s" % DEMO)
    phase_is(root, "kid", "running")
    kpid = int(table(root, "kid")["pid"])
    os.kill(kpid, signal.SIGKILL)
    ok = phase_is(root, "kid", "stopped")
    t = table(root, "kid")
    check("kid killed -9 -> stopped, signal 9, reason names SIGKILL", ok and t.get("signal") == "9" and "SIGKILL" in t.get("reason", ""), t)
    kmnt = os.path.join(base, "kid")
    clean = wait_until(lambda: kmnt not in our_mounts() and not os.path.exists(kmnt), 3)
    check("link gone, dead mount cleaned, mount dir removed", not os.path.lexists(root + "/procs/kid") and clean, our_mounts())
    stop_daemon(p, root, "crash")


def t_regfail():
    p, pid, root, base = start_daemon("regfail")
    s = spec(os.path.join(SCRATCH, "sleep.json"), ["/bin/sleep", "60"])
    t0 = time.monotonic()
    rc, _, err = ctl(root + "/procs_ctl", "add sl %s" % s)
    spid = int(wait_until(lambda: table(root, "sl").get("pid", "-") != "-" and table(root, "sl")["pid"], 2) or 0)
    ok = phase_is(root, "sl", "failed", 6)
    t = table(root, "sl")
    check("add sleep 60 (never registers) -> failed after the 3 s deadline (%.1f s), reason RegisterTimeout" % (time.monotonic() - t0),
          rc == 0 and ok and t.get("reason", "").startswith("RegisterTimeout"), (err, t))
    check("... and the process was killed", spid > 0 and wait_until(lambda: not alive(spid), 2), spid)
    pctl(root, "add fl /bin/false")
    ok = phase_is(root, "fl", "failed", 3)
    check("add /bin/false -> failed, exited before registering", ok and "before registering" in table(root, "fl").get("reason", ""),
          table(root, "fl"))
    _, _, st = pctl(root, "add nx /no/such/file")
    check("add a missing path -> failed with PathBad, not on the table", st.get("aos_procs_ctl_state") == "failed"
          and st.get("aos_procs_ctl_error", "").startswith("PathBad") and table(root, "nx") == {}, st)
    stop_daemon(p, root, "regfail")


def t_nested():
    p, pid, root, base = start_daemon("nested")
    s = spec(os.path.join(SCRATCH, "d1.json"), [DAEMON, "--mount-base", base, *FAST])
    rc, _, err = ctl(root + "/procs_ctl", "add d1 %s" % s)
    ok = phase_is(root, "d1", "running")
    st = read_kv(root + "/procs/d1/status") or {}
    check("add d1 (another aos-daemon) -> running, aos_name d1", rc == 0 and ok and st.get("aos_name") == "d1", (err, st))
    rc, _, err = ctl(root + "/procs/d1/procs_ctl", "add kid %s" % DEMO)
    st = wait_until(lambda: read_kv(root + "/procs/d1/procs/kid/status"), 5) or {}
    check("$AOS_ROOT/procs/d1/procs/kid/status readable, aos_name d1/kid", rc == 0 and st.get("aos_name") == "d1/kid", (err, st))
    check("kid's mount is d1%kid under the mount base", os.path.join(base, "d1%kid") in our_mounts(), our_mounts())
    ctl(root + "/procs_ctl", "add solo %s" % DEMO)
    phase_is(root, "solo", "running")
    before = marked()
    stop_daemon(p, root, "nested")
    check("daemon stop: every process below (2 levels) is gone",
          wait_until(lambda: not any(alive(x) for x in before), 3), [x for x in before if alive(x)])
    check("daemon stop: no mounts left", wait_until(lambda: our_mounts() == [], 3), our_mounts())


def t_startup():
    q, qpid, qroot, qmnt = start_demo("dead")
    base = os.path.join(os.path.dirname(qmnt), "..", "base", "startup")
    os.makedirs(base, exist_ok=True)
    # 在 mount-base 底下留一個死掛載：外面起的 demo 掛在那裡、再 kill -9
    q2 = subprocess.Popen([DEMO, "old", os.path.join(base, "old")], stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd="/",
                          env=env())
    wait_until(lambda: os.path.realpath(os.path.join(base, "old")) in our_mounts(), 3)
    q2.kill()
    q2.wait(3)
    dead = os.path.realpath(os.path.join(base, "old"))
    had = dead in our_mounts()
    p, pid, root, _ = start_daemon("startup")
    check("start: dead mounts under --mount-base are cleaned", had and dead not in our_mounts(), (had, our_mounts()))
    os.kill(pid, signal.SIGKILL)
    p.wait(3)
    p2, pid2, root2, _ = start_daemon("startup")
    check("root killed -9 and restarted on the same mountpoint: comes up", (read_kv(root2 + "/status") or {}).get("aos_pid") == str(pid2))
    stop_daemon(p2, root2, "startup")
    ctl(qroot + "/ctl", "stop")
    q.wait(5)


def t_sigterm():
    p, pid, root, base = start_daemon("sigterm")
    ctl(root + "/procs_ctl", "add k %s" % DEMO)
    phase_is(root, "k", "running")
    kpid = int(table(root, "k")["pid"])
    os.kill(pid, signal.SIGTERM)
    try:
        code = p.wait(6)
    except subprocess.TimeoutExpired:
        code = None
    check("SIGTERM to the daemon = stop: child stopped politely, daemon exits 0", code == 0 and not alive(kpid)
          and wait_until(lambda: our_mounts() == [], 3), (code, our_mounts()))


def t_envpid():
    p, pid, root, base = start_daemon("envpid")
    ctl(root + "/procs_ctl", "add kid %s" % DEMO)
    ok = phase_is(root, "kid", "running")
    kpid = int(table(root, "kid").get("pid", "0"))
    with open("/proc/%d/environ" % kpid, "rb") as f:
        envs = dict(x.split(b"=", 1) for x in f.read().split(b"\0") if b"=" in x)
    check("child gets AOS_NAME_PID = its own pid and still registers", ok and envs.get(b"AOS_NAME_PID") == str(kpid).encode(),
          envs.get(b"AOS_NAME_PID"))
    # 殼包一層、有 exec：PID 不變，照樣登記
    s = spec(os.path.join(SCRATCH, "wrap-exec.json"), ["/bin/sh", "-c", "exec %s" % DEMO])
    ctl(root + "/procs_ctl", "add wx %s" % s)
    check("wrapper that execs the demo: registers (aos_name wx)", phase_is(root, "wx", "running")
          and (read_kv(root + "/procs/wx/status") or {}).get("aos_name") == "wx", table(root, "wx"))
    # 殼包一層、沒有 exec：demo 是孫子，繼承到的 AOS_NAME_PID 是殼的，它不理 AOS_NAME／AOS_MOUNT
    err, rcf = os.path.join(SCRATCH, "grand.err"), os.path.join(SCRATCH, "grand.rc")
    for f in (err, rcf):
        if os.path.exists(f):
            os.unlink(f)
    s = spec(os.path.join(SCRATCH, "wrap-fork.json"), ["/bin/sh", "-c", "%s 2>%s; echo $? >%s" % (DEMO, err, rcf)])
    ctl(root + "/procs_ctl", "add gc %s" % s)
    ok = phase_is(root, "gc", "failed", 6)
    rc = open(rcf).read().strip() if os.path.exists(rcf) else None
    msg = open(err).read() if os.path.exists(err) else ""
    check("grandchild (wrapper without exec) does not take the child's name/mount: demo exits 1, nothing mounted",
          ok and rc == "1" and "AOS_NAME_PID" in msg and os.path.join(base, "gc") not in our_mounts(), (table(root, "gc"), rc, msg))
    stop_daemon(p, root, "envpid")


def t_mailbox():
    p, pid, root, base = start_daemon("mailbox")
    ctl(root + "/procs_ctl", "add kid %s" % DEMO)
    phase_is(root, "kid", "running")
    mb = root + "/procs/kid/mailbox"
    rc, _, err = sh("printf 'via the daemon\n' > %s/tmp/m1 && mv %s/tmp/m1 %s/new/m1" % (mb, mb, mb))
    rc2, out, _ = sh("cat %s/new/m1" % mb)
    st = read_kv(root + "/procs/kid/status") or {}
    check("deliver to $AOS_ROOT/procs/kid/mailbox/ (tmp/ then mv to new/): lands, kid counts it",
          rc == 0 and out == "via the daemon\n" and st.get("mail_waiting") == "1", (err, out, st))
    check("procs_status kid.mailbox stays the settings line (the on-disk box, -)", table(root, "kid").get("mailbox") == "-",
          table(root, "kid"))
    stop_daemon(p, root, "mailbox")


TESTS = {"self": t_self, "add": t_add, "crash": t_crash, "stuck": t_stuck, "regfail": t_regfail,
         "register": t_register, "obey": t_obey, "lock": t_lock, "nested": t_nested, "startup": t_startup,
         "stopstuck": t_stopstuck, "sigterm": t_sigterm, "envpid": t_envpid, "mailbox": t_mailbox}


def main():
    names = sys.argv[1:] or list(TESTS)
    for b in (DAEMON, DEMO):
        if not os.path.exists(b):
            print("FAIL  not built: %s (run make here and in ../aos-procfs)" % b)
            return 1
    os.makedirs(SCRATCH, exist_ok=True)
    try:
        for n in names:
            print("== %s" % n, flush=True)
            try:
                TESTS[n]()
            except Exception as e:
                check("%s raised" % n, False, repr(e))
    finally:
        cleanup()
    procs, mounts = leftovers()
    check("no leftover processes or mounts", not procs and not mounts, (procs, mounts))
    print("%d/%d passed" % (sum(results), len(results)))
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
