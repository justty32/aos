#!/usr/bin/env python3
# run.py：aos-procfs 的測試——起 aos-procfs-demo，逐條驗草稿第 6、7 節的行為，每條印 ok／FAIL，最後印總數並收乾淨。
"""用法：python3 tests/run.py [測試名 ...]   （不給＝全部；名字見 TESTS）"""
import errno, os, signal, socket, subprocess, sys, time
from common import DEMO, MNT, start_demo, sh, bg, status, wait_until, mounted, cleanup, leftovers

results = []


def check(name, cond, detail=""):
    results.append(bool(cond))
    print("%s  %s%s" % ("ok  " if cond else "FAIL", name, "" if cond or not detail else "  -- %s" % (detail,)), flush=True)


def ctl_state(root, want, timeout=5.0):
    return wait_until(lambda: (status(root) or {}).get("aos_ctl_state") == want, timeout)


def t_basic():
    p, pid, root, mnt = start_demo("basic")
    st = status(root) or {}
    want = ["aos_name", "aos_phase", "aos_pid", "aos_started_at", "aos_ctl_cmd", "aos_ctl_state", "aos_ctl_error", "aos_ctl_count"]
    check("status has the 8 lines", all(k in st for k in want), st)
    check("aos_pid is the server pid, aos_name is the name", st.get("aos_pid") == str(pid) and st.get("aos_name") == "basic", st)
    rc, out, _ = sh("cat %s/attrs" % root)
    check("attrs says aos_kind: fuse, aos_live: yes", "aos_kind: fuse\naos_live: yes\n" in out, out)
    rc, out, _ = sh("cat %s/_metainfo.json" % root)
    check("_metainfo.json is readable json", rc == 0 and out.strip().startswith("{"), out)
    rc, _, err = sh("cat %s/ctl" % root)
    check("reading ctl is refused by the kernel", rc != 0 and "Permission denied" in err, err)
    rc, _, err = sh("echo x > %s/status" % root)
    check("writing status is refused", rc != 0, err)

    rc, _, err = sh("echo pause > %s/ctl" % root)
    ok = rc == 0 and wait_until(lambda: (status(root) or {}).get("aos_phase") == "paused")
    check("echo pause > ctl -> aos_phase: paused", ok, err)
    # phase 是做事的線在做的途中改的，done 在它做完之後才記：等 done，不是看到 paused 就讀
    st = ctl_state(root, "done") and status(root) or {}
    check("feedback after pause: cmd pause, done, count 1",
          (st.get("aos_ctl_cmd"), st.get("aos_ctl_state"), st.get("aos_ctl_count")) == ("pause", "done", "1"), st)
    sh("echo resume > %s/ctl" % root)
    ctl_state(root, "done")

    rc, _, err = sh("echo frobnicate > %s/ctl" % root)
    st = status(root) or {}
    check("unknown word: write fails and aos_ctl_state: rejected",
          rc != 0 and st.get("aos_ctl_state") == "rejected" and st.get("aos_ctl_error", "").startswith("CommandUnknown"), (rc, err, st))

    # 用一次 write(2) 寫兩行：bash 的 printf 會把每行拆成各一次 write，量不到「一次寫入多行」
    fd = os.open(root + "/ctl", os.O_WRONLY)
    try:
        os.write(fd, b"pause\nresume\n")
        rc = 0
    except OSError as e:
        rc = e.errno
    os.close(fd)
    st = status(root) or {}
    check("two lines in one write are rejected", rc != 0 and st.get("aos_ctl_state") == "rejected"
          and st.get("aos_ctl_error", "").startswith("LinesTooMany") and st.get("aos_phase") == "running", (rc, st))

    rc, _, err = sh("echo 'slow x' > %s/ctl" % root)
    check("bad argument (slow x) is rejected", rc != 0 and (status(root) or {}).get("aos_ctl_state") == "rejected", err)

    # 鎖：slow 3 進行中，另一個人寫 pause 當場失敗、回饋不動、status 照樣讀得到
    rc, _, _ = sh("echo 'slow 3' > %s/ctl" % root)
    before = status(root) or {}
    rc2, _, err2 = sh("echo pause > %s/ctl" % root)
    t = time.monotonic()
    after = status(root, timeout=1.0)
    dt = time.monotonic() - t
    check("slow 3 accepted and locked (doing)", rc == 0 and before.get("aos_ctl_state") == "doing", before)
    check("second writer during slow 3 fails with busy", rc2 != 0 and "busy" in err2, err2)
    keys = ("aos_ctl_cmd", "aos_ctl_state", "aos_ctl_count")
    check("feedback untouched by the refused write", after and all(after[k] == before[k] for k in keys), (before, after))
    check("status readable during slow 3 (%.1f ms)" % (dt * 1000), after is not None and dt < 0.5)
    check("slow 3 finishes -> done", ctl_state(root, "done", 6))

    # 兩人先把 ctl 開好，再先後寫：第二個失敗
    a = os.open(root + "/ctl", os.O_WRONLY)
    b = os.open(root + "/ctl", os.O_WRONLY)
    os.write(a, b"slow 1\n")
    try:
        os.write(b, b"pause\n")
        second = "succeeded"
    except OSError as e:
        second = errno.errorcode.get(e.errno, e.errno)
    os.close(a)
    os.close(b)
    st = status(root) or {}
    check("both opened first, then wrote: second write fails (EBUSY)", second == "EBUSY" and st.get("aos_ctl_cmd") == "slow 1", (second, st))
    ctl_state(root, "done", 4)

    rc, _, err = sh("echo stop > %s/ctl" % root)
    try:
        code = p.wait(5)
    except subprocess.TimeoutExpired:
        code = None
    check("echo stop > ctl -> process exits 0", rc == 0 and code == 0, (rc, err, code))
    check("after stop the mount is gone and the dir removed", not mounted(mnt) and not os.path.exists(mnt))


def t_kill():
    p, pid, root, mnt = start_demo("kill")
    rc, _, _ = sh("%s --cleanup %s" % (DEMO, mnt))
    check("--cleanup refuses while the server is alive", rc != 0 and mounted(mnt))
    os.kill(pid, signal.SIGKILL)
    p.wait(5)
    check("after kill -9 /proc/<PID>/cwd is gone at once", not os.path.exists(root + "/status"))
    check("after kill -9 the dead mount stays", mounted(mnt))
    rc, out, err = sh("%s --cleanup %s" % (DEMO, mnt))
    check("--cleanup removes the dead mount", rc == 0 and not mounted(mnt) and not os.path.exists(mnt), (rc, out, err))
    rc, _, _ = sh("%s --cleanup %s" % (DEMO, mnt))
    check("--cleanup again: nothing mounted (exit 10)", rc == 10)


def t_abort():
    p, pid, root, mnt = start_demo("abort")
    os.kill(pid, signal.SIGSTOP)
    reader = bg("cat %s/status" % root)
    time.sleep(0.5)
    check("server SIGSTOPped: reader of status hangs", reader.poll() is None)
    with open("/proc/self/mountinfo") as f:
        dev = [l.split()[2] for l in f if l.split()[4] == mnt][0]
    maj, mi = map(int, dev.split(":"))
    with open("/sys/fs/fuse/connections/%d/abort" % ((maj << 20) | mi), "w") as f:
        f.write("1")
    try:
        _, err = reader.communicate(timeout=3)
        rc = reader.returncode
    except subprocess.TimeoutExpired:
        rc, err = None, "still stuck"
    check("abort releases the reader with an error", rc not in (None, 0) and "abort" in err, (rc, err))
    os.kill(pid, signal.SIGCONT)
    try:
        code = p.wait(5)
    except subprocess.TimeoutExpired:
        code = None
    check("server notices the abort, unmounts and exits", code == 0 and not mounted(mnt), code)


def t_socket():
    p, pid, root, mnt = start_demo("sock", "--socket")
    rc, out, _ = sh("stat -c %%F %s/sock" % root)
    check("bind made a socket node in the mount", rc == 0 and "socket" in out, out)
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(3)
        s.connect(root + "/sock")
        s.sendall(b"ping\n")
        got = s.recv(100)
        s.close()
    except OSError as e:
        got = repr(e)
    check("connect via /proc/<PID>/cwd/sock and get a reply", got == b"pong: ping\n", got)
    rc, _, err = sh("touch %s/newfile" % root)
    check("plain files still cannot be created next to it", rc != 0, err)
    rc, _, err = sh("echo stop > %s/ctl" % root)
    try:
        code = p.wait(5)
    except subprocess.TimeoutExpired:
        code = None
    check("socket demo stops cleanly", code == 0 and not mounted(mnt), (code, err))


def t_links():
    p, pid, root, mnt = start_demo("links")
    q, qpid, qroot, qmnt = start_demo("kid")
    rc, _, err = sh("echo 'link kid %s' > %s/ctl" % (qroot, root))
    ctl_state(root, "done")
    st = status(root + "/links/kid") or {}
    check("symlink added at runtime; reading through it reaches the other proc", rc == 0 and st.get("aos_name") == "kid", (err, st))
    rc, _, _ = sh("echo 'unlink kid' > %s/ctl" % root)
    ctl_state(root, "done")
    gone = not os.path.lexists(root + "/links/kid")
    check("symlink removed: gone right away (entry_valid=0)", rc == 0 and gone)
    rc, _, _ = sh("echo 'unlink kid' > %s/ctl" % root)
    st = ctl_state(root, "failed") and status(root) or {}
    check("accepted but failed while carried out: write ok, state failed, error LinkMissing",
          rc == 0 and st.get("aos_ctl_error", "").startswith("LinkMissing"), st)
    sh("echo pause > %s/ctl" % root)
    st = ctl_state(root, "done") and status(root) or {}
    check("done always means it worked: error is -", st.get("aos_ctl_error") == "-", st)
    for r, x in ((root, p), (qroot, q)):
        sh("echo stop > %s/ctl" % r)
        x.wait(5)
    check("both stop cleanly", not mounted(mnt) and not mounted(qmnt))


def t_env():
    m = os.path.join(MNT, "env-%d" % os.getpid())
    base = "AOS_NAME=envkid AOS_MOUNT=%s" % m
    rc, _, err = sh("env -u AOS_NAME_PID %s %s" % (base, DEMO))
    check("AOS_NAME/AOS_MOUNT without AOS_NAME_PID: ignored (exit 1)", rc == 1 and "AOS_NAME_PID" in err, (rc, err))
    # 孫子：殼設 AOS_NAME_PID=$$（殼自己的）再 fork 出 demo（後面多一個 true，殼不會 exec 優化掉）
    rc, _, err = sh("export %s AOS_NAME_PID=$$; %s; true" % (base, DEMO))
    check("grandchild with the shell's AOS_NAME_PID: ignored (no mount)", "AOS_NAME_PID" in err and not mounted(m), (rc, err))
    p = bg("export %s AOS_NAME_PID=$$; exec %s" % (base, DEMO))
    st = wait_until(lambda: os.path.exists(m) and mounted(os.path.realpath(m)) and status(m), 5) or {}
    check("exec with AOS_NAME_PID = own pid: takes the name and mount", st.get("aos_name") == "envkid", st)
    sh("echo stop > %s/ctl" % m)
    try:
        p.wait(5)
    except subprocess.TimeoutExpired:
        pass


TESTS = {"basic": t_basic, "kill": t_kill, "abort": t_abort, "socket": t_socket, "links": t_links, "env": t_env}


def main():
    names = sys.argv[1:] or list(TESTS)
    if not os.path.exists(DEMO):
        print("FAIL  demo not built: %s (run make)" % DEMO)
        return 1
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
