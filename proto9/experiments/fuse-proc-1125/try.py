#!/usr/bin/env python3
# 把 FUSE 玩具 aos proc 的實驗（問題 1～8）跑一遍並印結果；只碰 ~/.aos/scratch/proto9-fuse-1125/，結束前收掉自己起的行程與掛載。
import os, re, signal, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
S = os.path.expanduser("~/.aos/scratch/proto9-fuse-1125")
TRACE = os.path.join(S, "trace.log")
PROCS = []          # 我起的 Popen，最後一律收


def hdr(t):
    print("\n" + "=" * 70 + "\n## " + t + "\n" + "=" * 70, flush=True)


def sh(cmd, timeout=10, quiet=False):
    t = time.time()
    try:
        r = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, timeout=timeout, cwd="/")
        out, rc = (r.stdout + r.stderr).rstrip(), r.returncode
    except subprocess.TimeoutExpired:
        out, rc = "(逾時 %ss，被 try.py 放棄)" % timeout, "TIMEOUT"
    if not quiet:
        print("$ %s\n%s\n[rc=%s, %.1f ms]" % (cmd, out, rc, (time.time() - t) * 1000), flush=True)
    return out, rc


def start(script, name, *args, env=None):
    e = dict(os.environ, **(env or {}))
    p = subprocess.Popen([sys.executable, os.path.join(HERE, script), "--name", name] + list(args),
                         stdout=subprocess.PIPE, text=True, env=e, cwd="/")
    PROCS.append(p)
    line = p.stdout.readline().split()
    kids = {}
    if script == "toydaemon.py":
        while line and line[0] == "KID":
            kids[line[1]] = int(line[2])
            line = p.stdout.readline().split()
    pid, mnt = int(line[1]), line[2]
    return p, pid, mnt, kids


def trace_reset():
    open(TRACE, "w").close()


def trace_ops():
    ops = []
    for l in open(TRACE):
        f = l.split()
        ops.append(" ".join(f[1:2] + [x for x in f[2:] if not x.startswith("pid=")]))
    return ops


def status(pid):
    try:
        return dict(l.split(": ", 1) for l in open("/proc/%d/cwd/status" % pid).read().splitlines() if ": " in l)
    except OSError as e:
        return {"ERR": str(e)}


def my_mounts():
    return [l for l in open("/proc/mounts") if "toy-" in l]


def wait_until(fn, t=5):
    end = time.time() + t
    while time.time() < end:
        if fn():
            return True
        time.sleep(0.02)
    return False


def e1():
    hdr("問題 1：不靠 libfuse 掛得起來嗎？每個殼指令送來哪些 FUSE 操作")
    p, pid, mnt, _ = start("toyproc.py", "q1", env={"TOY_TRACE": TRACE})
    print("toyproc pid=%d 掛在 %s" % (pid, mnt))
    sh("grep toy-q1 /proc/mounts; readlink /proc/%d/cwd" % pid)
    base = "/proc/%d/cwd" % pid
    for cmd in ["ls %s/" % base, "ls -l %s/" % base, "cat %s/status" % base, "echo stop-not > %s/ctl" % base,
                "cd %s && pwd && pwd -P && cat settings attrs" % base, "cat %s/ctl" % base, "echo x > %s/status" % base,
                "touch %s/newfile" % base, "printf pause > %s/ctl" % base]:
        time.sleep(1.1)        # 讓 entry 快取（1 秒）過期，每次都看得到完整的操作
        trace_reset()
        sh(cmd)
        print("   FUSE 操作：" + " | ".join(trace_ops()))
    sh("cat %s/status" % base)
    sh("echo stop > %s/ctl" % base)
    p.wait(5)
    print("stop 後：行程退出碼 %s；殘留掛載 %r；掛載點夾還在嗎 %s" % (p.returncode, my_mounts(), os.path.exists(mnt)))


def e2():
    hdr("問題 2：鎖住時別人寫 ctl——OPEN 拒 vs WRITE 拒")
    for mode in ["open", "write"]:
        p, pid, mnt, _ = start("toyproc.py", "q2" + mode, "--busy-check", mode, env={"TOY_TRACE": TRACE})
        base = "/proc/%d/cwd" % pid
        print("\n--- busy-check=%s ---" % mode)
        sh("echo 'slow 2' > %s/ctl; echo rc_of_first=$?" % base)
        trace_reset()
        sh("echo pause > %s/ctl; echo rc=$?" % base)
        print("   FUSE 操作：" + " | ".join(trace_ops()))
        sh("grep aos_ctl %s/status" % base)
        wait_until(lambda: status(pid).get("aos_ctl_state") == "done")
        sh("echo dance > %s/ctl; echo rc=$?; grep aos_ctl %s/status" % (base, base))
        sh("echo stop > %s/ctl" % base)
        p.wait(5)
    print("\n--- 兩人都先開好檔，再先後寫（只在 OPEN 拒的漏洞） ---")
    for mode in ["open", "both"]:
        p, pid, mnt, _ = start("toyproc.py", "q2race" + mode, "--busy-check", mode)
        a = os.open("/proc/%d/cwd/ctl" % pid, os.O_WRONLY)
        b = os.open("/proc/%d/cwd/ctl" % pid, os.O_WRONLY)
        os.write(a, b"slow 1\n")
        try:
            os.write(b, b"pause\n")
            r = "第二個 write 成功（漏掉了鎖）"
        except OSError as e:
            r = "第二個 write 失敗：%s" % e
        os.close(a); os.close(b)
        st = status(pid)
        print("busy-check=%s：%s；status aos_ctl_cmd=%r state=%r" % (mode, r, st.get("aos_ctl_cmd"), st.get("aos_ctl_state")))
        wait_until(lambda: status(pid).get("aos_ctl_state") == "done")
        open("/proc/%d/cwd/ctl" % pid, "w").write("stop\n")
        p.wait(5)


def e3():
    hdr("問題 3：/proc/<PID>/cwd 與連穿兩層 /proc/<daemon>/cwd/procs/<名>")
    p, pid, mnt, kids = start("toydaemon.py", "d1", "--kids", "kid1,kid2,kid3")
    print("daemon pid=%d kids=%r" % (pid, kids))
    D = "/proc/%d/cwd" % pid
    sh("ls -l %s/ %s/procs/" % (D, D))
    sh("cat %s/status" % D)
    sh("cat %s/procs/kid1/status" % D)
    sh("cat %s/proc/kid2/attrs; readlink %s/procs/kid2 %s/proc" % (D, D, D))
    sh("cd %s/procs/kid3 && pwd && pwd -P && ls" % D)
    sh("AOS_ROOT=%s; echo pause > $AOS_ROOT/procs/kid1/ctl; grep -E 'phase|aos_ctl_cmd' $AOS_ROOT/procs/kid1/status" % D)
    sh("grep -c toy- /proc/mounts")
    return p, pid, kids


def e4(dp, dpid, kids):
    hdr("問題 4：kill -9 之後；auto_unmount；正常結束")
    D = "/proc/%d/cwd" % dpid
    print("--- 單獨一隻 toyproc（沒人替它收）：kill -9 ---")
    p, pid, m1, _ = start("toyproc.py", "q4kill")
    os.kill(pid, signal.SIGKILL)
    p.wait()
    sh("ls /proc/%d/cwd/ 2>&1; echo rc=$?" % pid)
    sh("stat %s 2>&1 | head -2; ls %s 2>&1; echo rc=$?" % (m1, m1))
    sh("grep toy-q4kill /proc/mounts")
    sh("fusermount3 -u %s; echo rc=$?; grep -c toy-q4kill /proc/mounts" % m1)
    sh("rmdir %s; echo rc=$?" % m1)

    k1 = kids["kid1"]
    m1 = [l.split()[1] for l in my_mounts() if "toy-kid1 " in l][0]
    print("\n--- daemon 底下的 kid1 pid=%d（掛在 %s）：kill -9，daemon 收屍時順手卸 ---" % (k1, m1))
    os.kill(k1, signal.SIGKILL)
    time.sleep(0.5)
    sh("ls /proc/%d/cwd/ 2>&1; echo rc=$?" % k1)
    sh("grep -c toy-kid1 /proc/mounts; ls -d %s; ls -l %s/procs/; cat %s/procs/kid1/status" % (m1, D, D))

    print("\n--- 另起一隻帶 auto_unmount 的：kill -9 ---")
    p, pid, mnt, _ = start("toyproc.py", "q4auto", "--auto-unmount")
    sh("grep toy-q4auto /proc/mounts; pgrep -a fusermount3")
    os.kill(pid, signal.SIGKILL)
    p.wait()
    gone = wait_until(lambda: not any("toy-q4auto" in l for l in my_mounts()), 3)
    sh("grep toy-q4auto /proc/mounts; echo rc=$?; ls %s; echo rc=$?; pgrep -a fusermount3" % mnt)
    print("auto_unmount 收掉了嗎：%s" % gone)
    try:
        os.rmdir(mnt)
    except OSError as e:
        print("rmdir 掛載點夾：%s" % e)

    print("\n--- 有人站在裡面時 kill -9（殼 cd 進去再殺 server） ---")
    p, pid, mnt, _ = start("toyproc.py", "q4busy")
    holder = subprocess.Popen(["bash", "-c", "cd /proc/%d/cwd && exec python3 -c 'import time; time.sleep(30)'" % pid])
    time.sleep(0.3)
    os.kill(pid, signal.SIGKILL)
    p.wait()
    sh("ls -l /proc/%d/cwd" % holder.pid)
    sh("fusermount3 -u %s; echo rc=$?" % mnt)
    sh("fusermount3 -u -z %s; echo rc=$?; grep -c toy-q4busy /proc/mounts" % mnt)
    holder.kill(); holder.wait()
    try:
        os.rmdir(mnt)
    except OSError as e:
        print("rmdir：%s" % e)

    print("\n--- 正常結束：對 daemon 寫 stop（它先對 kids 寫 stop） ---")
    sh("echo stop > %s/ctl" % D)
    dp.wait(10)
    sh("grep toy- /proc/mounts; echo rc=$?; ls %s/mnt/" % S)


def e5():
    hdr("問題 5：單執行緒伺服器——做很久時讀 status、讀自己的掛載點")
    p, pid, mnt, _ = start("toyproc.py", "q5one", "--threads", "1")
    base = "/proc/%d/cwd" % pid
    sh("echo 'slow 3' > %s/ctl; for i in 1 2 3; do grep aos_ctl_state %s/status; done" % (base, base))
    wait_until(lambda: status(pid).get("aos_ctl_state") == "done")
    sh("echo selfread > %s/ctl" % base, quiet=True)
    wait_until(lambda: status(pid).get("aos_ctl_state") == "done")
    print("另開執行緒（不是 FUSE 處理執行緒）讀自己的掛載點：")
    sh("grep -E 'aos_ctl|selfread' %s/status" % base)
    print("--- 在 FUSE 處理執行緒裡讀自己（threads=1）：背景起寫的人，等 2 秒看狀態 ---")
    w = subprocess.Popen(["bash", "-c", "echo selfread-inline > %s/ctl; echo rc=$?" % base],
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    time.sleep(2)
    sh("ps -o pid,stat,wchan:24,cmd -p %d; for t in /proc/%d/task/*; do echo \"toyproc 執行緒 $(basename $t) $(awk '{print $3}' $t/stat) $(cat $t/wchan)\"; done" % (w.pid, pid))
    w.kill()
    time.sleep(0.5)
    sh("ps -o pid,stat,wchan:24 -p %d; grep -E 'State|SigPnd' /proc/%d/status   # 已送 SIGKILL，仍卡住" % (w.pid, w.pid))
    os.kill(pid, signal.SIGKILL)
    p.wait()
    out = w.communicate(timeout=5)[0]
    print("kill -9 toyproc 之後，卡住的寫者才結束：rc=%s 輸出=%r" % (w.returncode, out))
    sh("fusermount3 -u %s; echo rc=$?" % mnt)
    try:
        os.rmdir(mnt)
    except OSError:
        pass
    print("--- 同一招，threads=2 ---")
    p, pid, mnt, _ = start("toyproc.py", "q5two", "--threads", "2")
    base = "/proc/%d/cwd" % pid
    sh("echo selfread-inline > %s/ctl; grep -E 'aos_ctl|selfread' %s/status" % (base, base), timeout=5)
    sh("echo stop > %s/ctl" % base)
    p.wait(5)


def e6():
    hdr("問題 6：成本")
    p, pid, mnt, _ = start("toyproc.py", "q6")
    base = "/proc/%d/cwd" % pid
    with open("/dev/shm/toy-q6-status", "w") as f:
        f.write(open(base + "/status").read())
    shm_tmp = os.path.join(S, "plainfile")
    with open(shm_tmp, "w") as f:
        f.write(open(base + "/status").read())

    def bench(path, n=2000):
        t = time.perf_counter()
        for _ in range(n):
            with open(path) as f:
                f.read()
        return (time.perf_counter() - t) / n * 1e6

    for path in [base + "/status", mnt + "/status", "/dev/shm/toy-q6-status", shm_tmp]:
        print("open+read+close %-60s %7.1f µs/次" % (path, bench(path)))
    os.unlink("/dev/shm/toy-q6-status")
    os.unlink(shm_tmp)
    ws = []
    for i in range(300):
        t = time.perf_counter()
        with open(base + "/ctl", "w") as f:
            f.write("pause\n" if i % 2 else "resume\n")
        ws.append(time.perf_counter() - t)
        wait_until(lambda: status(pid).get("aos_ctl_state") == "done")
    ws.sort()
    print("寫 ctl（open+write+close，O_TRUNC）中位數 %.1f µs、p90 %.1f µs（300 次）" % (ws[150] * 1e6, ws[270] * 1e6))
    t = time.perf_counter()
    for _ in range(300):
        with open("/dev/shm/toy-q6-ctl", "w") as f:
            f.write("pause\n")
    print("對照：寫 /dev/shm 普通檔 %.1f µs/次" % ((time.perf_counter() - t) / 300 * 1e6))
    os.unlink("/dev/shm/toy-q6-ctl")

    def cpu():
        f = open("/proc/%d/stat" % pid).read().rsplit(")", 1)[1].split()
        return int(f[11]) + int(f[12])
    time.sleep(1)
    c0 = cpu(); time.sleep(3); c1 = cpu()
    print("閒著 3 秒的 CPU tick（utime+stime，1 tick=1/%d 秒）：%d" % (os.sysconf("SC_CLK_TCK"), c1 - c0))
    sh("grep -E 'VmRSS|VmHWM|Threads' /proc/%d/status; for t in /proc/%d/task/*; do echo \"$(cat $t/comm) $(cat $t/wchan)\"; done" % (pid, pid))
    sh("grep -E 'VmRSS' /proc/%d/status | sed 's/^/kid fusermount3 helper? /'; pgrep -a fusermount3; grep -v '^#' /etc/fuse.conf | grep . ; cat /proc/sys/fs/mount-max" % pid)
    open(base + "/ctl", "w").write("stop\n")
    p.wait(5)
    print("--- 一口氣掛 30 隻（看會不會碰上限、要多久）---")
    t = time.time()
    many = [start("toyproc.py", "m%02d" % i, "--threads", "1") for i in range(30)]
    print("起 30 隻共 %.2f 秒；toy- 掛載數 %d" % (time.time() - t, len(my_mounts())))
    rss = [int(re.search(r"VmRSS:\s+(\d+)", open("/proc/%d/status" % m[1]).read()).group(1)) for m in many]
    print("每隻 VmRSS 平均 %d kB" % (sum(rss) / len(rss)))
    for m in many:
        open("/proc/%d/cwd/ctl" % m[1], "w").write("stop\n")
    for m in many:
        m[0].wait(5)
    print("收完後 toy- 掛載數 %d" % len(my_mounts()))


def e7():
    hdr("問題 7：stat size 寫 0；讀到一半內容變了")
    for mode in ["zero-direct", "zero-cache", "real"]:
        p, pid, mnt, _ = start("toyproc.py", "q7" + mode.replace("-", ""), "--size", mode)
        base = "/proc/%d/cwd" % pid
        print("\n--- size=%s ---" % mode)
        sh("stat -c 'size=%%s' %s/status; cat %s/status | head -3; echo; wc -c < %s/status; tail -n 2 %s/status; "
           "head -c 40 %s/status; echo; grep -c . %s/status; python3 -c \"print(len(open('%s/status').read()))\"; "
           "cp %s/status /dev/shm/toy-q7 && wc -c < /dev/shm/toy-q7; rm -f /dev/shm/toy-q7"
           % ((base,) * 8))
        open(base + "/ctl", "w").write("stop\n")
        p.wait(5)
    print("\n--- 讀到一半內容變：status 墊 600 行，每次產生帶一個序號 gen；用 dd bs=1000 分很多次讀 ---")
    for gen in ["open", "read"]:
        p, pid, mnt, _ = start("toyproc.py", "q7gen" + gen, "--gen", gen, env={"TOY_STATUS_PAD": "600"})
        base = "/proc/%d/cwd" % pid
        out, rc = sh("dd if=%s/status bs=1000 2>/dev/null | grep -o 'gen=[0-9]*' | sort | uniq -c | head; "
                     "dd if=%s/status bs=1000 2>/dev/null | grep -vcE '^(pad_[0-9]{4}: gen=[0-9]+|[a-z_]+: ?.*)$'"
                     % (base, base))
        print("gen=%s：上面第一段是讀到幾種版本，最後一行是不成形的行數" % gen)
        open(base + "/ctl", "w").write("stop\n")
        p.wait(5)


def e8():
    hdr("問題 8：別的帳號／bwrap 沙箱")
    p, pid, mnt, _ = start("toyproc.py", "q8")
    base = "/proc/%d/cwd" % pid
    sh("bwrap --dev-bind / / head -2 %s/status" % base)
    sh("bwrap --dev-bind / / --unshare-user head -2 %s/status; echo rc=$?" % base)
    sh("bwrap --dev-bind / / --unshare-user --uid 0 --gid 0 sh -c 'id -u; head -2 %s/status'; echo rc=$?" % base)
    sh("bwrap --dev-bind / / --unshare-user --uid 4242 --gid 4242 sh -c 'id -u; head -2 %s/status; ls -ln %s/'; echo rc=$?" % (base, base))
    sh("bwrap --dev-bind / / --unshare-pid --proc /proc sh -c 'ls %s/ 2>&1; echo rc=$?; head -2 %s/status'" % (base, mnt))
    sh("bwrap --ro-bind / / --dev /dev --proc /proc --unshare-all sh -c 'head -2 %s/status; echo rc=$?'" % mnt)
    open(base + "/ctl", "w").write("stop\n")
    p.wait(5)


def cleanup():
    for p in PROCS:
        if p.poll() is None:
            p.kill()
            p.wait()
    for l in my_mounts():
        m = l.split()[1]
        subprocess.run(["fusermount3", "-u", "-z", m])
    mdir = os.path.join(S, "mnt")
    for d in os.listdir(mdir) if os.path.isdir(mdir) else []:
        try:
            os.rmdir(os.path.join(mdir, d))
        except OSError as e:
            print("收不掉：%s" % e)
    hdr("收尾")
    sh(r"pgrep -af '^\S*python3\S* \S*toy(proc|daemon)[.]py'; grep toy- /proc/mounts; echo '(以上空白＝沒有殘留)'; ls -A %s" % mdir)


def main():
    os.makedirs(os.path.join(S, "mnt"), exist_ok=True)
    which = sys.argv[1:] or ["1", "2", "3", "4", "5", "6", "7", "8"]
    try:
        if "1" in which: e1()
        if "2" in which: e2()
        if "3" in which or "4" in which:
            dp, dpid, kids = e3()
            if "4" in which:
                e4(dp, dpid, kids)
        if "5" in which: e5()
        if "6" in which: e6()
        if "7" in which: e7()
        if "8" in which: e8()
    finally:
        cleanup()


if __name__ == "__main__":
    main()
