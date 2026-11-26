#!/usr/bin/env python3
# run.py：aos-daemon2 的測試——不用 root 起來、export 那行、/proc/<PID>/cwd 與 /proc/<PID>/root、start/kill/forget、退出碼、天空表對 mountinfo、Landlock、cgroup、跑的時候掛卸、主 kernel 重起規則、整片跟著 daemon 走、主 kernel 經 /aos（或 ptrace）碰目錄、procs/<名>/ 是真的夾、沒有殘留。
# 用法：python3 tests/run.py [組名…]；組：basic procs sky landlock cgroup mount modes restart teardown access dirs（最後一定跑 leftovers）
import errno, json, os, re, select, shutil, signal, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
BIN = os.path.normpath(os.path.join(HERE, "..", "build", "bin", "aos-daemon2"))
TOYS = HERE
TMP = tempfile.mkdtemp(prefix="aosd2-test-")
RESULTS = []
STARTED = []   # (Popen, daemon pid)


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print("%s %s%s" % ("PASS" if ok else "FAIL", name, "" if ok or not detail else "  -- " + str(detail)), flush=True)
    return ok


def wait_for(cond, timeout=5.0, step=0.02):
    """等 cond() 為真（monotonic 計時）；回最後一次的值。"""
    end = time.monotonic() + timeout
    while True:
        try:
            v = cond()
        except OSError:
            v = None
        if v or time.monotonic() > end:
            return v
        time.sleep(step)


def read(p):
    with open(p) as f:
        return f.read()


def gone(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    st = read("/proc/%d/stat" % pid)
    return st[st.rfind(")") + 2] == "Z"


def base_sky(out):
    return ["bind /usr /usr", "bind /etc /etc", "symlink usr/bin /bin", "symlink usr/lib /lib",
            "symlink usr/lib64 /lib64", "dev /dev", "proc /proc", "tmpfs /tmp",
            "bind %s /toys" % TOYS, "bind -w %s /out" % out]


def config(d, name, toy, sky=None, **extra):
    """寫一份設定檔到 d/name.json，回路徑。toy 是 toys.py 的參數（天空裡的 /toys/toys.py）；extra 可蓋掉 argv 等。"""
    c = {"name": name, "argv": ["/usr/bin/python3", "/toys/toys.py"] + toy, "sky": sky or base_sky(d)}
    c.update(extra)
    p = os.path.join(d, name + ".json")
    with open(p, "w") as f:
        json.dump(c, f)
    return p


class Daemon:
    def __init__(self, test, kernel_argv=None, *flags, kernel_extra=None, wait=10.0):
        self.dir = os.path.join(TMP, test)
        os.makedirs(self.dir, exist_ok=True)
        kcfg = config(self.dir, "main", kernel_argv or ["kernel", "/out"], **(kernel_extra or {}))
        self.err_path = os.path.join(self.dir, "daemon.err")
        self.p = subprocess.Popen([BIN, "--kernel", kcfg, *flags], stdout=subprocess.PIPE,
                                  stderr=open(self.err_path, "w"), cwd="/")
        self.line = self._line(wait)
        m = re.fullmatch(r"export AOS_ROOT=/proc/(\d+)/cwd", self.line or "")
        self.pid = int(m.group(1)) if m else None
        self.root = "/proc/%d/cwd" % self.pid if self.pid else None
        STARTED.append((self.p, self.pid))

    def _line(self, wait):
        end = time.monotonic() + wait
        buf = b""
        fd = self.p.stdout.fileno()
        while time.monotonic() < end and b"\n" not in buf:
            r, _, _ = select.select([fd], [], [], 0.05)
            if r:
                c = os.read(fd, 4096)
                if not c:
                    break
                buf += c
        return buf.decode().split("\n")[0] if b"\n" in buf else None

    def err(self):
        return read(self.err_path)

    def status(self):
        out = {}
        for line in read(self.root + "/status").splitlines():
            k, _, v = line.partition(": ")
            out[k] = v
        return out

    def ctl(self, line, wait=20.0):
        """寫一道指令；回 (寫入的 errno 或 0, state, error)。ctl 是「做完才回」：寫入一回來就讀 status，不再等。
        wait 秒還沒回就用 SIGALRM 打斷（daemon 會回 EINTR），回 (EINTR, …)。"""
        def alarm(*_):
            raise TimeoutError("ctl write did not return in %s s" % wait)
        old = signal.signal(signal.SIGALRM, alarm)
        signal.setitimer(signal.ITIMER_REAL, wait)
        err = 0
        try:
            fd = os.open(self.root + "/ctl", os.O_WRONLY)
            try:
                os.write(fd, (line + "\n").encode())
            finally:
                os.close(fd)
        except OSError as e:
            err = e.errno
        except TimeoutError:
            err = errno.EINTR
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, old)
        s = self.status()
        return err, s.get("aos_ctl_state"), s.get("aos_ctl_error")

    def fact(self, name, f):
        return read("%s/procs/%s/%s" % (self.root, name, f))

    def hostpid(self, name):
        return int(re.search(r"host: (\d+)", self.fact(name, "pid")).group(1))

    def ask(self, q, timeout=5.0):
        """叫主 kernel（toys.py kernel）做一件事：讀一個路徑或寫一行 ctl；回答案。"""
        n = "%d-%d" % (os.getpid(), int(time.monotonic() * 1e6))
        with open(os.path.join(self.dir, ".q"), "w") as f:
            f.write(q)
        os.rename(os.path.join(self.dir, ".q"), os.path.join(self.dir, "ask-" + n))
        ans = os.path.join(self.dir, "ans-" + n)
        if not wait_for(lambda: os.path.exists(ans), timeout):
            return None
        return read(ans).strip()

    def stop(self, sig=signal.SIGTERM, timeout=10.0):
        if self.p.poll() is None:
            self.p.send_signal(sig)
        try:
            return self.p.wait(timeout)
        except subprocess.TimeoutExpired:
            self.p.kill()
            return None


def kernel_file(d, timeout=5.0):
    """主 kernel 起來時寫的 kernel-<PID>.txt（第一行 $AOS_ROOT/status、root …、proc1 …）。"""
    kf = wait_for(lambda: [n for n in os.listdir(d.dir) if n.startswith("kernel-")], timeout)
    return wait_for(lambda: read(os.path.join(d.dir, kf[0])), timeout) if kf else ""


def caps_of(hp):
    st = read("/proc/%d/status" % hp)
    return {k: int(re.search(k + r":\s+(\w+)", st).group(1), 16) for k in ("CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb")}


def started(d, name, timeout=5.0):
    return wait_for(lambda: os.path.exists("%s/procs/%s" % (d.root, name)) and d.fact(name, "state") == "alive\n", timeout)


# ---------------------------------------------------------------- basic

def t_basic():
    check("basic: running as a normal user", os.getuid() != 0)
    d = Daemon("basic")
    check("basic: export line", d.pid is not None, d.line)
    if not d.pid:
        print(d.err())
        return
    st = read("/proc/%d/status" % d.pid)
    nspid = re.search(r"NSpid:\s+(.*)", st).group(1).split()
    check("basic: daemon is PID 1 in its own PID namespace", nspid == [str(d.pid), "1"], nspid)
    um = read("/proc/%d/uid_map" % d.pid).split()
    check("basic: uid map: caller is 0 inside, subuid range after it",
          um[:3] == ["0", str(os.getuid()), "1"] and (len(um) == 3 or um[3] == "1"), um)
    s = d.status()
    check("basic: status via /proc/<PID>/cwd", s.get("pid_ns") == "1" and s.get("pid_host") == str(d.pid), s)
    check("basic: main kernel listed and alive", started(d, "main"))
    root = sorted(os.listdir("/proc/%d/root" % d.pid))
    check("basic: /proc/<PID>/root shows only the small world", root in (["aos"], ["aos", "cgroup"]), root)
    check("basic: cwd is the aos dir inside the small world",
          os.path.samefile("/proc/%d/cwd" % d.pid, "/proc/%d/root/aos" % d.pid))
    check("basic: no host files through /proc/<PID>/root",
          not os.path.exists("/proc/%d/root/etc" % d.pid) and not os.path.exists("/proc/%d/root/usr" % d.pid))
    check("basic: the directory holds ctl, procs/, status (no slots/)", sorted(os.listdir(d.root)) == ["ctl", "procs", "status"],
          sorted(os.listdir(d.root)))
    kt = kernel_file(d)
    check("basic: main kernel reads $AOS_ROOT/status, AOS_ROOT is /aos", kt.startswith("ok pid_ns: 1") and "\nroot /aos\n" in kt, kt)
    caps = re.search(r"CapEff:\s+(\w+)", read("/proc/%d/status" % d.hostpid("main"))).group(1)
    check("basic: main kernel has no capabilities", int(caps, 16) == 0, caps)
    check("basic: SIGTERM -> daemon exits 0", d.stop() == 0)
    check("basic: daemon process gone", wait_for(lambda: gone(d.pid), 3))


# ---------------------------------------------------------------- procs

def t_procs():
    d = Daemon("procs")
    if not check("procs: daemon up", d.pid, d.err()):
        return
    started(d, "main")
    c = config(d.dir, "sleeper", ["sleep"])
    r = d.ctl("start " + c)
    check("procs: start -> write ok, done", r == (0, "done", "-"), r)
    check("procs: when the write returns the proc is already listed and alive",
          os.path.exists(d.root + "/procs/sleeper") and d.fact("sleeper", "state") == "alive\n")
    hp = d.hostpid("sleeper")
    ns = int(re.search(r"ns: (\d+)", d.fact("sleeper", "pid")).group(1))
    nspid = re.search(r"NSpid:\s+(.*)", read("/proc/%d/status" % hp)).group(1).split()
    check("procs: pid file gives both levels (matches NSpid)", nspid == [str(hp), str(ns)], (nspid, ns))
    check("procs: started_at is a UTC time", re.fullmatch(r"\d{4}-\d\d-\d\dT[\d:.]+Z\n", d.fact("sleeper", "started_at")))
    r = d.ctl("start " + c)
    check("procs: same name again -> write error EIO, failed ProcExists",
          r[0] == errno.EIO and r[1] == "failed" and r[2].startswith("ProcExists"), r)
    r = d.ctl("forget sleeper")
    check("procs: forget alive -> write error EINVAL", r[0] == errno.EINVAL and r[2].startswith("ProcAlive"), r)
    r = d.ctl("kill nobody TERM")
    check("procs: kill unknown -> write error", r[0] == errno.EINVAL and r[2].startswith("ProcUnknown"), r)
    r = d.ctl("kill sleeper NOPE")
    check("procs: kill bad signal -> write error", r[0] == errno.EINVAL and r[2].startswith("SignalUnknown"), r)
    r = d.ctl("frobnicate x")
    check("procs: unknown command -> write error", r[0] == errno.EINVAL, r)
    r = d.ctl("start relative.json")
    check("procs: start relative path -> write error", r[0] == errno.EINVAL, r)
    r = d.ctl("start /nonexistent/x.json")
    check("procs: start unreadable config -> write error EIO, failed",
          r[0] == errno.EIO and r[1] == "failed" and r[2].startswith("ConfigUnreadable"), r)
    bad = os.path.join(d.dir, "bad.json")
    with open(bad, "w") as f:
        f.write('{"name": "x", "argv": ["/bin/true"], "locks": {"landlock": false}}')
    r = d.ctl("start " + bad)
    check("procs: landlock off is refused (EIO)", r[0] == errno.EIO and r[1] == "failed" and "landlock" in (r[2] or ""), r)
    r = d.ctl("kill sleeper TERM")
    check("procs: kill -> done", r == (0, "done", "-"), r)
    check("procs: dead after SIGTERM", wait_for(lambda: d.fact("sleeper", "state") == "dead\n", 5))
    check("procs: exit records the signal", d.fact("sleeper", "exit") == "signal 15 SIGTERM\n", d.fact("sleeper", "exit"))
    check("procs: ended_at set", d.fact("sleeper", "ended_at") != "-\n")
    r = d.ctl("kill sleeper KILL")
    check("procs: kill dead -> write error ProcDead", r[0] == errno.EINVAL and r[2].startswith("ProcDead"), r)
    r = d.ctl("forget sleeper")
    check("procs: forget dead -> done, gone from procs/", r == (0, "done", "-") and not os.path.exists(d.root + "/procs/sleeper"), r)
    c7 = config(d.dir, "seven", ["exit", "7"])
    d.ctl("start " + c7)
    check("procs: exit code 7 recorded", wait_for(lambda: d.fact("seven", "exit") == "code 7\n", 5))
    cb = config(d.dir, "noexec", ["x"], argv=["/nonexistent"])
    r = d.ctl("start " + cb)
    check("procs: exec failure -> write error EIO, failed with reason",
          r[0] == errno.EIO and r[1] == "failed" and "exec /nonexistent" in (r[2] or ""), r)
    check("procs: failed start leaves no entry", not os.path.exists(d.root + "/procs/noexec"))
    if d.status().get("subuid") != "none":
        cu = config(d.dir, "alice", ["sleep"], uid=1001)
        d.ctl("start " + cu)
        started(d, "alice")
        hu = re.search(r"Uid:\s+(\d+)", read("/proc/%d/status" % d.hostpid("alice"))).group(1)
        sub0 = int(d.status()["subuid"].split()[0])
        check("procs: uid 1001 runs as subuid (host %d)" % (sub0 + 1000), hu == str(sub0 + 1000) and
              d.fact("alice", "uid") == "sky: 1001\nhost: %d\n" % (sub0 + 1000), (hu, d.fact("alice", "uid")))
    else:
        check("procs: (skip) no subuid range", True)
    # 主 kernel 自己寫 ctl 起一隻
    ck = config(d.dir, "bykernel", ["sleep"])
    a = d.ask("ctl start " + ck)
    check("procs: main kernel writes start into /aos/ctl (alive when the write returns)",
          a == "ok" and os.path.exists(d.root + "/procs/bykernel") and d.fact("bykernel", "state") == "alive\n", a)
    a = d.ask("ctl start /nonexistent/x.json")
    check("procs: main kernel's failing start is a write error EIO", a == "err EIO", a)
    check("procs: SIGTERM -> exit 0", d.stop() == 0)


# ---------------------------------------------------------------- sky

def parse_mountinfo(hp):
    out = []
    for line in read("/proc/%d/mountinfo" % hp).splitlines():
        f = line.split()
        out.append((f[4].replace("\\040", " "), f[5].split(",")[0] == "ro"))
    return out


def t_sky():
    d = Daemon("sky")
    if not check("sky: daemon up", d.pid, d.err()):
        return
    started(d, "main")
    src = os.path.join(d.dir, "data")
    os.makedirs(src, exist_ok=True)
    with open(os.path.join(src, "f"), "w") as f:
        f.write("data")
    sky = base_sky(d.dir) + ["bind %s /ro" % src, "bind -w %s /rw" % src, "symlink /ro/f /link", "tmpfs /scratch"]
    c = config(d.dir, "sk", ["write", "/out", "sk", "/ro/x", "/rw/x", "/x", "/tmp/x", "/scratch/x", "/usr/x"], sky=sky)
    r = d.ctl("start " + c)
    check("sky: start", r == (0, "done", "-"), r)
    started(d, "sk")
    hp = d.hostpid("sk")
    table = [l.split() for l in d.fact("sk", "sky").splitlines()]
    mi = parse_mountinfo(hp)
    check("sky: one table line per mount (same count as mountinfo)", len(table) == len(mi), (len(table), len(mi)))
    check("sky: mount points and ro/rw match mountinfo",
          sorted((t[2], t[3] == "ro") for t in table) == sorted(mi), (table, mi))
    check("sky: sky_check ok", d.fact("sk", "sky_check") == "ok\n", d.fact("sk", "sky_check"))
    same = True
    bad = []
    for t in table:
        if t[0] == "bind":
            a, b = os.stat(t[1]), os.stat("/proc/%d/root%s" % (hp, t[2]))
            if (a.st_dev, a.st_ino) != (b.st_dev, b.st_ino):
                same = False
                bad.append(t)
    check("sky: every bind line's source is the same file as its mount point", same, bad)
    locked = [t for t in table if t[-1] == "locked"]
    wsl = os.path.exists("/usr/lib/wsl")
    check("sky: locked submounts under /usr listed (%s)" % ("WSL" if wsl else "none expected"),
          (len(locked) > 0) == any(l.split()[4].startswith("/usr/") for l in read("/proc/self/mountinfo").splitlines()),
          locked)
    res = wait_for(lambda: os.path.exists(os.path.join(d.dir, "sk.txt")) and read(os.path.join(d.dir, "sk.txt")), 5) or ""
    want = {"/ro/x": "err EROFS", "/rw/x": "ok", "/x": "err EROFS", "/tmp/x": "ok", "/scratch/x": "ok", "/usr/x": "err EROFS"}
    got = dict(l.split(" ", 1) for l in res.strip().splitlines())
    check("sky: read-only and writable places behave as the table says", got == want, got)
    check("sky: the rw write landed in the host dir", os.path.exists(os.path.join(src, "x")))
    root = os.listdir("/proc/%d/root" % hp)
    check("sky: the proc's root holds only what the config put there",
          sorted(root) == sorted(["usr", "etc", "bin", "lib", "lib64", "dev", "proc", "tmp", "toys", "out", "ro", "rw",
                                  "link", "scratch"]), sorted(root))
    d.stop()


# ---------------------------------------------------------------- landlock

def t_landlock():
    d = Daemon("landlock")
    if not check("landlock: daemon up", d.pid, d.err()):
        return
    started(d, "main")
    if int(d.status().get("landlock_abi", "0")) < 1:
        check("landlock: (skip) kernel has no Landlock", True)
        d.stop()
        return
    d.ctl("start " + config(d.dir, "a", ["sleep"]))
    started(d, "a")
    a_ns = re.search(r"ns: (\d+)", d.fact("a", "pid")).group(1)
    d.ctl("start " + config(d.dir, "b", ["probe", "/out", "b", "/proc/1/cwd/status", "/proc/1/root",
                                          "/proc/%s/root" % a_ns, "/proc/%s/environ" % a_ns, "/proc/self/root",
                                          "kill:1"]))
    res = wait_for(lambda: os.path.exists(os.path.join(d.dir, "b.txt")) and read(os.path.join(d.dir, "b.txt")), 5) or ""
    got = {l.split(" ")[0]: " ".join(l.split(" ")[1:3]) for l in res.strip().splitlines()}
    check("landlock: non-main proc cannot read /proc/1/cwd", got.get("/proc/1/cwd/status") == "err EACCES", got)
    check("landlock: non-main proc cannot read /proc/1/root", got.get("/proc/1/root", "").startswith("err"), got)
    check("landlock: non-main proc cannot read a sibling's /proc/<pid>/root",
          got.get("/proc/%s/root" % a_ns, "").startswith("err EACCES"), got)
    check("landlock: ... nor its environ", got.get("/proc/%s/environ" % a_ns, "").startswith("err EACCES"), got)
    check("landlock: its own /proc/self/root still works", got.get("/proc/self/root", "").startswith("ok"), got)
    abi = int(d.status()["landlock_abi"])
    k = got.get("kill:1", "")
    # ABI 6 以前 Landlock 擋不住訊號：照實記下（這條驗的是「量到的跟 ABI 說的一樣」，不是「擋住了」）
    check("landlock: signal to the daemon from a non-main proc: %s (ABI %d)" % (k, abi),
          k == ("err EPERM" if abi >= 6 else "ok"), got)
    ans = d.ask("/proc/%s/root" % a_ns)
    check("landlock: main kernel can read a proc's /proc/<pid>/root", ans and ans.startswith("ok") and "toys" in ans, ans)
    locks = d.fact("b", "locks")
    check("landlock: locks fact names the Landlock domain", locks.startswith("landlock: own domain"), locks)
    check("landlock: main kernel's locks say no Landlock", d.fact("main", "locks").startswith("landlock: none"))
    caps = re.search(r"CapEff:\s+(\w+)", read("/proc/%d/status" % d.hostpid("b"))).group(1)
    check("landlock: non-main proc has no capabilities", int(caps, 16) == 0, caps)
    nnp = re.search(r"NoNewPrivs:\s+(\d)", read("/proc/%d/status" % d.hostpid("b"))).group(1)
    check("landlock: no_new_privs set", nnp == "1")
    d.stop()


# ---------------------------------------------------------------- cgroup

def t_cgroup():
    d = Daemon("cgroup")
    if not check("cgroup: daemon up", d.pid, d.err()):
        return
    started(d, "main")
    cg = d.status().get("cgroup", "")
    if cg.startswith("off"):
        check("cgroup: (skip) %s" % cg, True)
        d.stop()
        return
    ctrls = read(os.path.join(cg, "cgroup.subtree_control")).split()
    limits = {}
    if "memory" in ctrls:
        limits["memory.max"] = "67108864"
    if "pids" in ctrls:
        limits["pids.max"] = "50"
    d.ctl("start " + config(d.dir, "t", ["sleep"], locks={"cgroup": limits}))
    check("cgroup: proc with limits started", started(d, "t"))
    link = "%s/procs/t/cgroup" % d.root
    check("cgroup: procs/<name>/cgroup is a usable directory", os.path.isfile(link + "/cgroup.freeze"))
    hp = d.hostpid("t")
    check("cgroup: the proc is in that cgroup", str(hp) in read(link + "/cgroup.procs").split())
    for k, v in limits.items():
        check("cgroup: %s set from the config" % k, read(link + "/" + k).strip() == v, read(link + "/" + k))
    with open(link + "/cgroup.freeze", "w") as f:
        f.write("1")
    check("cgroup: writing cgroup.freeze freezes it",
          wait_for(lambda: "frozen 1" in read(link + "/cgroup.events"), 3))
    with open(link + "/cgroup.freeze", "w") as f:
        f.write("0")
    check("cgroup: and thaws", wait_for(lambda: "frozen 0" in read(link + "/cgroup.events"), 3))
    name = os.readlink(link).split("/")[-1]
    d.ctl("kill t KILL")
    wait_for(lambda: d.fact("t", "state") == "dead\n", 5)
    r = d.ctl("forget t")
    check("cgroup: forget removes the cgroup dir", r[1] == "done" and not os.path.exists(os.path.join(cg, name)), r)
    if "memory" in ctrls:
        r = d.ctl("start " + config(d.dir, "u", ["sleep"], locks={"cgroup": {"nosuch.max": "1"}}))
        check("cgroup: unknown limit file -> EIO, failed CgroupLimitFailed",
              r[0] == errno.EIO and r[1] == "failed" and "CgroupLimitFailed" in r[2], r)
    d.stop()
    check("cgroup: scope removed after the daemon exits", wait_for(lambda: not os.path.exists(cg), 5), cg)


# ---------------------------------------------------------------- mount

def t_mount():
    d = Daemon("mount")
    if not check("mount: daemon up", d.pid, d.err()):
        return
    started(d, "main")
    src = os.path.join(d.dir, "live")
    os.makedirs(src, exist_ok=True)
    with open(os.path.join(src, "hello"), "w") as f:
        f.write("hi")
    d.ctl("start " + config(d.dir, "m", ["sleep"]))
    started(d, "m")
    hp = d.hostpid("m")
    r = d.ctl("mount m %s /live" % src)
    check("mount: mount into a running proc -> done", r == (0, "done", "-"), r)
    check("mount: visible in its sky", os.path.exists("/proc/%d/root/live/hello" % hp))
    table = [l.split() for l in d.fact("m", "sky").splitlines()]
    check("mount: sky table has the new line (ro)", ["bind", src, "/live", "ro"] in table, table)
    check("mount: table still matches mountinfo",
          sorted((t[2], t[3] == "ro") for t in table) == sorted(parse_mountinfo(hp)))
    r = d.ctl("mount m -w %s /out/sub/live" % src)
    check("mount: -w into a writable place", r == (0, "done", "-") and ["bind", src, "/out/sub/live", "rw"] in
          [l.split() for l in d.fact("m", "sky").splitlines()], r)
    r = d.ctl("umount m /live")
    table = [l.split() for l in d.fact("m", "sky").splitlines()]
    check("mount: umount -> gone from sky and table", r == (0, "done", "-") and
          not os.path.exists("/proc/%d/root/live/hello" % hp) and not any(t[2] == "/live" for t in table), r)
    check("mount: table matches mountinfo after umount",
          sorted((t[2], t[3] == "ro") for t in table) == sorted(parse_mountinfo(hp)))
    r = d.ctl("mount m /nonexistent /x")
    check("mount: bad source -> write error EIO, failed MountFailed",
          r[0] == errno.EIO and r[1] == "failed" and r[2].startswith("MountFailed"), r)
    r = d.ctl("umount m /nothere")
    check("mount: umount of a place not mounted -> write error EIO, failed UmountFailed",
          r[0] == errno.EIO and r[1] == "failed" and r[2].startswith("UmountFailed"), r)
    r = d.ctl("mount m relative /x")
    check("mount: relative path -> write error", r[0] == errno.EINVAL, r)
    d.stop()


# ---------------------------------------------------------------- modes

def t_modes():
    d = Daemon("modes", None, "--cgroup", "off", "--subuid", "off")
    if not check("modes: daemon up with --cgroup off --subuid off", d.pid, d.err()):
        return
    started(d, "main")
    s = d.status()
    check("modes: status says cgroup off and no subuid", s.get("cgroup", "").startswith("off (--cgroup off)") and
          s.get("subuid") == "none", s)
    um = read("/proc/%d/uid_map" % d.pid).split()
    check("modes: only the caller is mapped", um == ["0", str(os.getuid()), "1"], um)
    r = d.ctl("start " + config(d.dir, "c", ["sleep"], locks={"cgroup": {"pids.max": "10"}}))
    check("modes: cgroup limit without cgroup -> EIO, failed CgroupUnavailable", r[0] == errno.EIO and r[1] == "failed" and
          r[2].startswith("CgroupUnavailable"), r)
    r = d.ctl("start " + config(d.dir, "u", ["sleep"], uid=5))
    check("modes: uid 5 without subuid -> EIO, failed UidUnavailable", r[0] == errno.EIO and r[1] == "failed" and
          r[2].startswith("UidUnavailable"), r)
    r = d.ctl("start " + config(d.dir, "p", ["sleep"]))
    check("modes: a plain proc still starts", r[1] == "done" and started(d, "p"))
    check("modes: its locks say groups are kept", "groups: kept" in d.fact("p", "locks"))
    check("modes: no cgroup link", not os.path.lexists(d.root + "/procs/p/cgroup"))
    check("modes: SIGTERM -> exit 0", d.stop() == 0)


# ---------------------------------------------------------------- restart

def t_restart():
    d = Daemon("restart1", ["flaky", "/out", "2"])
    if not check("restart: daemon up", d.pid, d.err()):
        return
    ok = wait_for(lambda: d.status().get("kernel_restarts") == "2" and started(d, "main", 0.1), 10)
    check("restart: kernel that died twice was restarted and runs", ok, d.status())
    check("restart: kernel_last_exit is code 5", d.status().get("kernel_last_exit") == "code 5")
    check("restart: daemon still up", d.p.poll() is None)
    d.stop()

    d = Daemon("restart2", ["exit", "3"], "--restart-limit", "3")
    t0 = time.monotonic()
    rc = d.p.wait(15) if d.pid else None
    check("restart: limit reached -> daemon exits 1", rc == 1, (rc, d.err()[-500:] if d.pid else ""))
    starts = d.err().count("started main")
    check("restart: started 4 times (1 + 3 restarts), stopped at the 4th death", starts == 4, starts)
    check("restart: says why", "more than --restart-limit 3" in d.err())
    check("restart: took < 10 s", time.monotonic() - t0 < 10)

    d = Daemon("restart3", ["exit", "4"], "--on-kernel-exit", "exit")
    rc = d.p.wait(10) if d.pid else None
    check("restart: --on-kernel-exit exit -> daemon exits with the kernel's code 4", rc == 4, rc)
    check("restart: ... without restarting", d.err().count("started main") == 1)

    d = Daemon("restart4", ["exit", "0"], "--restart-limit", "0")
    rc = d.p.wait(10) if d.pid else None
    check("restart: --restart-limit 0 -> first death ends the daemon", rc == 1, rc)


# ---------------------------------------------------------------- teardown

def t_teardown():
    d = Daemon("teardown")
    if not check("teardown: daemon up", d.pid, d.err()):
        return
    started(d, "main")
    for n in ("s1", "s2", "s3"):
        d.ctl("start " + config(d.dir, n, ["sleep"]))
        started(d, n)
    pids = [d.hostpid(n) for n in ("main", "s1", "s2", "s3")]
    t0 = time.monotonic()
    os.kill(d.pid, signal.SIGKILL)
    check("teardown: kill -9 daemon -> all procs gone", wait_for(lambda: all(gone(p) for p in pids), 3), pids)
    check("teardown: ... within 1 s", time.monotonic() - t0 < 1.0, time.monotonic() - t0)
    rc = d.p.wait(5)
    check("teardown: launcher exits with 128+9", rc == 137, rc)

    d = Daemon("teardown2")
    started(d, "main")
    d.ctl("start " + config(d.dir, "s1", ["sleep"]))
    started(d, "s1")
    pids = [d.hostpid("main"), d.hostpid("s1")]
    lp = d.p.pid
    os.kill(lp, signal.SIGKILL)
    check("teardown: kill -9 of the launcher also takes the daemon and procs",
          wait_for(lambda: gone(d.pid) and all(gone(p) for p in pids), 3))
    d.p.wait(5)


# ---------------------------------------------------------------- access

def t_access():
    """主 kernel 怎麼碰 daemon 的目錄：預設 mount（天空裡的 /aos、零 caps），設定 daemon_access ptrace 走 /proc/1/cwd。"""
    d = Daemon("access")
    if not check("access: daemon up", d.pid, d.err()):
        return
    started(d, "main")
    s = d.status()
    check("access: status says main_kernel_access: mount /aos", s.get("main_kernel_access") == "mount /aos", s)
    hp = d.hostpid("main")
    c = caps_of(hp)
    check("access: mount mode: main kernel has zero capabilities (inh, prm, eff, bnd, amb)", not any(c.values()), c)
    kt = kernel_file(d)
    check("access: AOS_ROOT=/aos, reads /aos/status", kt.startswith("ok pid_ns: 1") and "\nroot /aos\n" in kt, kt)
    check("access: ... and cannot read /proc/1/cwd (EACCES)", "\nproc1 err EACCES\n" in kt, kt)
    table = [l.split() for l in d.fact("main", "sky").splitlines()]
    cg_on = not s.get("cgroup", "off").startswith("off")
    check("access: kernel's sky table has 'aos - /aos rw'%s" % (" and the cgroup line" if cg_on else ""),
          ["aos", "-", "/aos", "rw"] in table and (not cg_on or ["cgroup", s["cgroup"], "/cgroup", "rw"] in table), table)
    check("access: sky_check ok", d.fact("main", "sky_check") == "ok\n", d.fact("main", "sky_check"))
    mi = [l.split() for l in read("/proc/%d/mountinfo" % hp).splitlines()]
    aos = [l for l in mi if l[4] == "/aos"]
    check("access: /aos in the kernel's mountinfo is the daemon's FUSE mount",
          aos and aos[0][aos[0].index("-") + 1] == "fuse.aosproc", aos)
    check("access: kernel's locks say no capabilities, directory at /aos",
          "capabilities: none" in d.fact("main", "locks") and "daemon directory: /aos" in d.fact("main", "locks"),
          d.fact("main", "locks"))
    a = d.ask("/aos")
    check("access: kernel lists /aos", a == "ok ctl procs status", a)
    cw = config(d.dir, "w", ["sleep"], locks={"cgroup": {"pids.max": "20"}} if cg_on else {})
    a = d.ask("ctl start " + cw)
    check("access: kernel writes 'start' into /aos/ctl; when the write returns the proc is alive",
          a == "ok" and d.fact("w", "state") == "alive\n", a)
    a = d.ask("/aos/procs/w/state")
    check("access: kernel reads /aos/procs/w/state", a == "ok alive|", a)
    a = d.ask("ctl start /nonexistent/x.json")
    check("access: kernel's failing start is EIO", a == "err EIO", a)
    a = d.ask("/aos/status")
    check("access: ... and the reason is in /aos/status", a and "aos_ctl_state: failed" in a.replace("|", "\n"), a)
    if cg_on:
        a = d.ask("/aos/procs/w/cgroup/pids.max")
        check("access: kernel follows procs/w/cgroup (relative link to /cgroup) and reads pids.max", a == "ok 20|", a)
    a = d.ask("ctl umount main /aos")
    check("access: ctl umount of /aos in the kernel's sky is refused (EINVAL)", a == "err EINVAL", a)
    a = d.ask("ctl mount main /usr /aos")
    check("access: ctl mount over /aos is refused (EINVAL)", a == "err EINVAL" and
          d.status().get("aos_ctl_error", "").startswith("PathReserved"), (a, d.status().get("aos_ctl_error")))
    a = d.ask("ctl kill w KILL")
    wait_for(lambda: d.fact("w", "state") == "dead\n", 5)
    a2 = d.ask("ctl forget w")
    check("access: kernel kills and forgets; /aos/procs/w is gone for it", a == "ok" and a2 == "ok" and
          d.ask("/aos/procs/w") == "err ENOENT", (a, a2))
    # 非主 kernel 的：沒有 /aos、讀不到 /proc/1/cwd、沒有 AOS_ROOT
    d.ctl("start " + config(d.dir, "np", ["probe", "/out", "np", "/aos", "/proc/1/cwd/status", "env:AOS_ROOT",
                                           "env:AOS_NAME", "/cgroup"]))
    res = wait_for(lambda: os.path.exists(os.path.join(d.dir, "np.txt")) and read(os.path.join(d.dir, "np.txt")), 5) or ""
    got = {l.split(" ")[0]: " ".join(l.split(" ")[1:]) for l in res.strip().splitlines()}
    check("access: non-main proc has no /aos", got.get("/aos") == "err ENOENT", got)
    check("access: non-main proc has no /cgroup", got.get("/cgroup") == "err ENOENT", got)
    check("access: non-main proc cannot read /proc/1/cwd", got.get("/proc/1/cwd/status") == "err EACCES", got)
    check("access: non-main proc gets no AOS_ROOT (but gets AOS_NAME)",
          got.get("env:AOS_ROOT") == "err unset" and got.get("env:AOS_NAME") == "ok np", got)
    bad = config(d.dir, "dacc", ["sleep"], daemon_access="ptrace")
    r = d.ctl("start " + bad)
    check("access: daemon_access in a non-main config -> EIO, failed ConfigBad",
          r[0] == errno.EIO and r[1] == "failed" and "daemon_access" in (r[2] or ""), r)
    check("access: /proc/<PID>/cwd from outside still works", d.status().get("pid_ns") == "1")
    d.stop()

    # ptrace 模式（舊的做法，設定裡選）
    d = Daemon("access-ptrace", kernel_extra={"daemon_access": "ptrace"})
    if not check("access: ptrace mode: daemon up", d.pid, d.err()):
        return
    started(d, "main")
    check("access: ptrace mode: status says ptrace /proc/1/cwd",
          d.status().get("main_kernel_access") == "ptrace /proc/1/cwd", d.status())
    c = caps_of(d.hostpid("main"))
    check("access: ptrace mode: kernel keeps only cap_sys_ptrace", c["CapEff"] == 1 << 19 and c["CapBnd"] == 1 << 19, c)
    kt = kernel_file(d)
    check("access: ptrace mode: AOS_ROOT=/proc/1/cwd and it reads it",
          kt.startswith("ok pid_ns: 1") and "\nroot /proc/1/cwd\n" in kt, kt)
    check("access: ptrace mode: no /aos in its sky", d.ask("/aos") == "err ENOENT")
    a = d.ask("ctl start " + config(d.dir, "pw", ["sleep"]))
    check("access: ptrace mode: kernel's start through /proc/1/cwd/ctl works", a == "ok" and d.fact("pw", "state") == "alive\n", a)
    d.stop()

    # 主 kernel 的天空自己用了 /aos：daemon 起不來，說明原因
    d = Daemon("access-clash", kernel_extra={"sky": base_sky(os.path.join(TMP, "access-clash")) + ["tmpfs /aos"]})
    rc = d.p.wait(10)
    check("access: kernel sky using /aos -> daemon exits 2 and says why", rc == 2 and "/aos" in d.err() and
          "daemon_access" in d.err(), (rc, d.err()[-300:]))


# ---------------------------------------------------------------- dirs

def t_dirs():
    """procs/<名>/ 是真的夾：start 時建、forget 時連同底下整個拿掉；同名再起看到新的。"""
    d = Daemon("dirs")
    if not check("dirs: daemon up", d.pid, d.err()):
        return
    started(d, "main")
    c = config(d.dir, "x", ["sleep"])
    d.ctl("start " + c)
    p = d.root + "/procs/x"
    check("dirs: procs/x is a real directory, not a symlink", os.path.isdir(p) and not os.path.islink(p))
    want = {"name", "pid", "state", "exit", "started_at", "ended_at", "sky", "sky_check", "uid", "locks", "config"}
    if not d.status().get("cgroup", "off").startswith("off"):
        want.add("cgroup")
    check("dirs: it holds the facts", set(os.listdir(p)) == want, sorted(os.listdir(p)))
    check("dirs: ls procs/ lists main and x", sorted(os.listdir(d.root + "/procs")) == ["main", "x"])
    hp1 = d.hostpid("x")
    os.stat(p + "/state")   # 讓核心快取這條路
    f = open(p + "/name")
    d.ctl("kill x KILL")
    wait_for(lambda: d.fact("x", "state") == "dead\n", 5)
    r = d.ctl("forget x")
    check("dirs: forget -> done and procs/x is gone at once (with what was under it)",
          r == (0, "done", "-") and not os.path.lexists(p) and not os.path.lexists(p + "/state"), r)
    check("dirs: ls procs/ lists only main", os.listdir(d.root + "/procs") == ["main"])
    check("dirs: a fact file opened before forget still reads", f.read() == "x\n")
    f.close()
    r = d.ctl("start " + c)
    check("dirs: same name again: new directory with the new proc", r == (0, "done", "-") and d.hostpid("x") != hp1)
    ok = True
    for i in range(10):
        n = "c%d" % i
        if d.ctl("start " + config(d.dir, n, ["exit", "0"]))[1] != "done":
            ok = False
        wait_for(lambda: d.fact(n, "state") == "dead\n", 5)
        if d.ctl("forget " + n)[1] != "done" or os.path.lexists(d.root + "/procs/" + n):
            ok = False
    check("dirs: 10 start/forget rounds, each directory made and removed", ok)
    check("dirs: procs/ is back to main and x", sorted(os.listdir(d.root + "/procs")) == ["main", "x"],
          os.listdir(d.root + "/procs"))
    check("dirs: status counts 2 procs", d.status().get("procs") == "2")
    d.stop()


# ---------------------------------------------------------------- leftovers

def t_leftovers():
    for p, pid in STARTED:
        if p.poll() is None:
            p.kill()
            p.wait(5)
    time.sleep(0.2)
    left = []
    for d in os.listdir("/proc"):
        if d.isdigit():
            try:
                args = read("/proc/%s/cmdline" % d).split("\0")
            except OSError:
                continue
            # daemon、起動那一層（argv[0]）、天空裡的 toys.py（argv[1]）
            if args[0] == BIN or args[0].endswith("/aos-daemon2") or args[1:2] == ["/toys/toys.py"]:
                left.append((d, " ".join(args)))
    check("leftovers: no processes", not left, left)
    units = subprocess.run(["systemctl", "--user", "list-units", "--all", "--no-legend", "aos-daemon2-*"],
                           capture_output=True, text=True).stdout.strip() if shutil.which("systemctl") else ""
    check("leftovers: no systemd units", units == "", units)
    cgs = []
    for root, dirs, _ in os.walk("/sys/fs/cgroup/user.slice"):
        cgs += [os.path.join(root, x) for x in dirs if x.startswith("aos-daemon2-")]
    check("leftovers: no cgroups", not cgs, cgs)
    mi = [l for l in read("/proc/self/mountinfo").splitlines() if "aosdaemon2" in l or TMP in l]
    check("leftovers: no mounts", not mi, mi)


GROUPS = {"basic": t_basic, "procs": t_procs, "sky": t_sky, "landlock": t_landlock, "cgroup": t_cgroup,
          "mount": t_mount, "modes": t_modes, "restart": t_restart, "teardown": t_teardown, "access": t_access,
          "dirs": t_dirs}


def main():
    if not os.path.exists(BIN):
        sys.exit("missing %s: run make first" % BIN)
    names = sys.argv[1:] or list(GROUPS)
    try:
        for n in names:
            try:
                GROUPS[n]()
            except Exception as e:
                check("%s: raised %r" % (n, e), False)
    finally:
        t_leftovers()
        shutil.rmtree(TMP, ignore_errors=True)
    fails = sum(1 for _, ok in RESULTS if not ok)
    print("SUMMARY %d passed, %d failed" % (len(RESULTS) - fails, fails))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
