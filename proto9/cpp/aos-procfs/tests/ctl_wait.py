#!/usr/bin/env python3
# ctl_wait.py：「做完才回」ctl 的測試（demo --ctl-wait）——寫入等做完才回、failed 寫入失敗 EIO、等的時候別人照讀照擋、被訊號放開、卸載時放開。
"""用法：python3 tests/ctl_wait.py [測試名 ...]   （不給＝全部；名字見 TESTS）"""
import errno, os, signal, subprocess, sys, time
from common import start_demo, sh, status, wait_until, mounted, cleanup, leftovers, check, RESULTS, _stuck

# 寫 ctl 的人：另開一支 python（卡住也不拖住測試）。argv: 路徑 指令 [gate]；gate＝開好檔先印 opened、等 stdin 一行再寫。
# 印「結果 秒數」：ok、errno 名、或 interrupted（SIGINT 的 KeyboardInterrupt）
WRITER = r'''
import errno, os, sys, time
fd = os.open(sys.argv[1], os.O_WRONLY)
if len(sys.argv) > 3:
    print("opened", flush=True)
    sys.stdin.readline()
t = time.monotonic()
try:
    os.write(fd, sys.argv[2].encode() + b"\n")
    r = "ok"
except OSError as e:
    r = errno.errorcode.get(e.errno, str(e.errno))
except KeyboardInterrupt:
    r = "interrupted"
print(r, "%.3f" % (time.monotonic() - t), flush=True)
'''


def writer(root, line, gate=False):
    args = [sys.executable, "-c", WRITER, root + "/ctl", line] + (["gate"] if gate else [])
    p = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    _stuck.append(p)
    if gate:
        p.stdout.readline()   # "opened"
    return p


def result(p, timeout=10.0):
    """等寫的人結束；回 (結果, 秒數)，到時沒結束回 (None, None)。"""
    try:
        out, _ = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, None
    parts = out.split()
    return (parts[0], float(parts[1])) if len(parts) == 2 else (out.strip() or "rc=%s" % p.returncode, None)


def write(root, line, timeout=10.0):
    return result(writer(root, line), timeout)


def fb(root):
    st = status(root) or {}
    return st.get("aos_ctl_cmd"), st.get("aos_ctl_state"), st.get("aos_ctl_error")


def doing(root, timeout=5.0):
    return wait_until(lambda: (status(root) or {}).get("aos_ctl_state") == "doing", timeout)


def stop(p, root):
    sh("echo stop > %s/ctl" % root)
    try:
        return p.wait(5)
    except subprocess.TimeoutExpired:
        return None


def t_default():
    # 沒給 --ctl-wait：照舊「寫回來＝收到」，ctl 的大小照舊是 0
    p, pid, root, mnt = start_demo("cwdef")
    rc, out, _ = sh("stat -c %%s %s/ctl" % root)
    check("default ctl: size 0", out.strip() == "0", out)
    r, dt = write(root, "slow 1")
    check("default ctl: write returns at once (state still doing)", r == "ok" and dt < 0.5 and fb(root)[1] == "doing", (r, dt))
    wait_until(lambda: fb(root)[1] == "done", 5)
    r, _ = write(root, "unlink nosuch")
    check("default ctl: failed while carried out is still a successful write", r == "ok", r)
    check("default ctl stops", stop(p, root) == 0)


def t_basic():
    p, pid, root, mnt = start_demo("cwait", "--ctl-wait")
    r, _ = write(root, "pause")
    st = status(root) or {}
    check("pause: write ok, and right after it status says done and paused",
          r == "ok" and (st.get("aos_ctl_cmd"), st.get("aos_ctl_state"), st.get("aos_ctl_error"), st.get("aos_phase"))
          == ("pause", "done", "-", "paused"), (r, st))
    r, dt = write(root, "slow 1")
    check("slow 1: the write takes about 1 s and status is done right after",
          r == "ok" and dt is not None and dt >= 0.9 and fb(root) == ("slow 1", "done", "-"), (r, dt, fb(root)))
    r, _ = write(root, "unlink nosuch")
    c = fb(root)
    check("failed while carried out: write fails EIO, status failed + reason",
          r == "EIO" and c[1] == "failed" and (c[2] or "").startswith("LinkMissing"), (r, c))
    r, dt = write(root, "frobnicate")
    check("unknown word: EINVAL at once, rejected (unchanged)", r == "EINVAL" and fb(root)[1] == "rejected", (r, dt))
    rc, _, err = sh("echo > %s/ctl" % root)
    check("empty write: succeeds, nothing changes", rc == 0 and fb(root)[1] == "rejected", err)
    rc, _, err = sh("echo 'slow 0.2' > %s/ctl" % root)
    check("shell echo waits too and succeeds", rc == 0 and fb(root)[1] == "done", err)
    rc, out, _ = sh("stat -c %%s %s/ctl" % root)
    check("a reply-when-done ctl reports a large size (so open-first writers are not queued)", out.strip() == str(1 << 30), out)
    rc, _, err = sh("echo stop > %s/ctl" % root)
    try:
        code = p.wait(5)
    except subprocess.TimeoutExpired:
        code = None
    check("stop (hold_until_exit): write ok, process exits 0", rc == 0 and code == 0, (rc, err, code))
    check("after stop the mount is gone", not mounted(mnt))


def t_lock():
    p, pid, root, mnt = start_demo("cwlock", "--ctl-wait")
    a = writer(root, "slow 2")
    doing(root)
    before = fb(root)
    t = time.monotonic()
    st = status(root, timeout=1.0)
    dt = time.monotonic() - t
    check("while a write waits, status reads fine (%.1f ms)" % (dt * 1000), st is not None and dt < 0.5)
    t = time.monotonic()
    rc, _, err = sh("echo pause > %s/ctl" % root)
    dt = time.monotonic() - t
    check("second writer gets busy at once (%.0f ms)" % (dt * 1000), rc != 0 and "busy" in err and dt < 1.0, (rc, err))
    check("feedback untouched by the refused write", fb(root) == before, (before, fb(root)))
    r, dt = result(a)
    check("first writer returns ok after the 2 s", r == "ok" and dt is not None and dt >= 1.9 and fb(root)[1] == "done", (r, dt))
    # 兩人先把 ctl 開好，再先後寫：第二個當場 EBUSY，不排在第一個人的檔鎖後面
    a = writer(root, "slow 2", gate=True)
    b = writer(root, "pause", gate=True)
    a.stdin.write("go\n")
    a.stdin.flush()
    doing(root)
    b.stdin.write("go\n")
    b.stdin.flush()
    rb, dtb = result(b, 5)
    check("both opened first: second write EBUSY at once", rb == "EBUSY" and dtb is not None and dtb < 1.0, (rb, dtb))
    ra, _ = result(a)
    check("... and the first still finishes ok", ra == "ok" and fb(root) == ("slow 2", "done", "-"), (ra, fb(root)))
    check("lock demo stops", stop(p, root) == 0)


def interrupts(name, *extra):
    p, pid, root, mnt = start_demo(name, "--ctl-wait", *extra)
    a = writer(root, "slow 3")
    doing(root)
    time.sleep(0.2)
    t = time.monotonic()
    a.send_signal(signal.SIGINT)
    r, _ = result(a, 5)
    dt = time.monotonic() - t
    check("%s: SIGINT frees the waiting writer at once (%.0f ms)" % (name, dt * 1000), r == "interrupted" and dt < 1.0, r)
    check("%s: ... the command goes on (still doing)" % name, fb(root)[1] == "doing", fb(root))
    check("%s: ... and ends done" % name, wait_until(lambda: fb(root)[1] == "done", 5), fb(root))
    a = writer(root, "slow 3")
    doing(root)
    time.sleep(0.2)
    t = time.monotonic()
    a.kill()
    try:
        a.wait(3)
        dt = time.monotonic() - t
    except subprocess.TimeoutExpired:
        dt = None
    check("%s: SIGKILL of the waiting writer works at once" % name, dt is not None and dt < 1.0, dt)
    check("%s: ... the command still ends done" % name, wait_until(lambda: fb(root)[1] == "done", 5), fb(root))
    r, _ = write(root, "slow 0.1")
    check("%s: next write after an interrupt works" % name, r == "ok" and fb(root) == ("slow 0.1", "done", "-"), (r, fb(root)))
    check("%s: stops" % name, stop(p, root) == 0)


def t_interrupt():
    interrupts("cwint")


def t_threads():
    interrupts("cwthr", "--threads", "4")


def t_teardown():
    p, pid, root, mnt = start_demo("cwdown", "--ctl-wait")
    a = writer(root, "slow 10")
    doing(root)
    t = time.monotonic()
    p.send_signal(signal.SIGTERM)
    r, _ = result(a, 5)
    dt = time.monotonic() - t
    check("server stops while a write waits: the writer gets ECONNABORTED (%.0f ms)" % (dt * 1000),
          r == "ECONNABORTED" and dt < 3.0, r)
    try:
        code = p.wait(5)
    except subprocess.TimeoutExpired:
        code = None
    check("... the server exits 0 and the mount is gone", code == 0 and not mounted(mnt), code)


TESTS = {"default": t_default, "basic": t_basic, "lock": t_lock, "interrupt": t_interrupt, "threads": t_threads,
         "teardown": t_teardown}


def main():
    names = sys.argv[1:] or list(TESTS)
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
    print("%d/%d passed" % (sum(RESULTS), len(RESULTS)))
    return 0 if all(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
