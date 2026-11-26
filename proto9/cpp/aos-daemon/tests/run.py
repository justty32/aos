#!/usr/bin/env python3
# run.py：aos-daemon 的測試——不用 root 起來、export 那行、/proc/<PID>/cwd 與 /proc/<PID>/root、start/kill/forget、退出碼、天空表對 mountinfo、Landlock、cgroup、跑的時候掛卸、init 重起規則、整片跟著 daemon 走、init 經 /aos（或 ptrace）碰目錄、procs/<名>/ 是真的夾、daemon 設定檔、結束寬限、起動那一層死了留下、forget -k、改名 init、沒有 init、到重起上限留著、daemon_path、init 進 Landlock、exit_code、net none／host、seccomp（內建的擋單、off、自己的名單）、疊 daemon 量到的界線、--cgroup PATH、停止訊號只收外面與 init 送的、普通 proc 經 init 的 /proc/<PID>/root 進不去、bind 來源卡住時不跟著卡、ns.json 的 by／at、overlay、合併目錄 B、restart-init、介面宣告、沒有殘留。
# 用法：python3 tests/run.py [組名…]；組：basic procs nsconf ns landlock cgroup mount modes restart teardown access dirs stdio dconf grace pdeath forgetk rename noinit rlstay dpath ilandlock exitcode net seccomp nest cgpath sigsrc ipath stuck nsby overlay merge rinit iface（最後一定跑 leftovers）
import errno, json, os, re, select, shutil, signal, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
BIN = os.path.normpath(os.path.join(HERE, "..", "build", "bin", "aos-daemon"))
TOYS = HERE
TMP = tempfile.mkdtemp(prefix="aosd-test-")
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


def bind(src, dst, rw=None):
    e = {"type": "bind", "src": src, "dst": dst}
    if rw is not None:
        e["rw"] = rw
    return e


def ent(type_, dst):
    return {"type": type_, "dst": dst}


def symlink(target, dst):
    return {"type": "symlink", "target": target, "dst": dst}


def base_ns(out):
    return [bind("/usr", "/usr"), bind("/etc", "/etc"), symlink("usr/bin", "/bin"), symlink("usr/lib", "/lib"),
            symlink("usr/lib64", "/lib64"), ent("dev", "/dev"), ent("proc", "/proc"), ent("tmpfs", "/tmp"),
            bind(TOYS, "/toys"), bind(out, "/out", True)]


def config(d, name, toy, ns=None, **extra):
    """寫一份設定檔到 d/name.json，回路徑。toy 是 toys.py 的參數（天空裡的 /toys/toys.py）；extra 可蓋掉 argv 等。"""
    c = {"name": name, "argv": ["/usr/bin/python3", "/toys/toys.py"] + toy, "ns": ns or base_ns(d)}
    c.update(extra)
    p = os.path.join(d, name + ".json")
    with open(p, "w") as f:
        json.dump(c, f)
    return p


def write_json(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        f.write(obj if isinstance(obj, str) else json.dumps(obj))
    return p


class Daemon:
    def __init__(self, test, init_argv=None, *flags, init_extra=None, wait=10.0, args=None, cwd="/", cmd=None):
        """args：給了就用 [BIN, *args] 起（不帶 --init；init 設定照樣寫在 dir/main.json）。cmd：給了就整個照它起（cmd 可以是
        函式，拿 init 設定檔的路徑回命令列）。"""
        self.dir = os.path.join(TMP, test)
        os.makedirs(self.dir, exist_ok=True)
        kcfg = config(self.dir, "main", init_argv or ["init", "/out"], **(init_extra or {}))
        self.err_path = os.path.join(self.dir, "daemon.err")
        argv = cmd(kcfg) if cmd else [BIN, *(args if args is not None else ["--init", kcfg, *flags])]
        self.p = subprocess.Popen(argv, stdout=subprocess.PIPE,
                                  stderr=open(self.err_path, "w"), cwd=cwd)
        self.line = self._line(wait)
        m = re.fullmatch(r"export AOS_DAEMON=/proc/(\d+)/cwd", self.line or "")
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
        """叫 init（toys.py init）做一件事：讀一個路徑或寫一行 ctl；回答案。"""
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


def init_file(d, timeout=5.0):
    """init 起來時寫的 init-<PID>.txt（第一行 $AOS_DAEMON/status、root …、proc1 …）。"""
    kf = wait_for(lambda: [n for n in os.listdir(d.dir) if n.startswith("init-")], timeout)
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
    check("basic: init listed and alive", started(d, "main"))
    root = sorted(os.listdir("/proc/%d/root" % d.pid))
    check("basic: /proc/<PID>/root shows only the small world", root in (["aos"], ["aos", "cgroup"]), root)
    check("basic: cwd is the aos dir inside the small world",
          os.path.samefile("/proc/%d/cwd" % d.pid, "/proc/%d/root/aos" % d.pid))
    check("basic: no host files through /proc/<PID>/root",
          not os.path.exists("/proc/%d/root/etc" % d.pid) and not os.path.exists("/proc/%d/root/usr" % d.pid))
    check("basic: the directory holds __meta/, ctl, procs/, status (no slots/)", sorted(os.listdir(d.root)) == ["__meta", "ctl", "procs", "status"],
          sorted(os.listdir(d.root)))
    kt = init_file(d)
    check("basic: init reads $AOS_DAEMON/status, AOS_DAEMON is /aos", kt.startswith("ok pid_ns: 1") and "\nroot /aos\n" in kt, kt)
    caps = re.search(r"CapEff:\s+(\w+)", read("/proc/%d/status" % d.hostpid("main"))).group(1)
    check("basic: init has no capabilities", int(caps, 16) == 0, caps)
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
              d.fact("alice", "uid") == "ns: 1001\nhost: %d\n" % (sub0 + 1000), (hu, d.fact("alice", "uid")))
    else:
        check("procs: (skip) no subuid range", True)
    # init 自己寫 ctl 起一隻
    ck = config(d.dir, "byinit", ["sleep"])
    a = d.ask("ctl start " + ck)
    check("procs: init writes start into /aos/ctl (alive when the write returns)",
          a == "ok" and os.path.exists(d.root + "/procs/byinit") and d.fact("byinit", "state") == "alive\n", a)
    a = d.ask("ctl start /nonexistent/x.json")
    check("procs: init's failing start is a write error EIO", a == "err EIO", a)
    check("procs: SIGTERM -> exit 0", d.stop() == 0)


# ---------------------------------------------------------------- ns

def nsrow(j):
    """ns.json 的一筆拿掉 by、at（比的時候只看 type、src、lower、dst、rw、locked）。"""
    return {k: v for k, v in j.items() if k not in ("by", "at")}


def parse_mountinfo(hp):
    out = []
    for line in read("/proc/%d/mountinfo" % hp).splitlines():
        f = line.split()
        out.append((f[4].replace("\\040", " "), f[5].split(",")[0] == "ro"))
    return out


def t_ns():
    d = Daemon("ns")
    if not check("ns: daemon up", d.pid, d.err()):
        return
    started(d, "main")
    src = os.path.join(d.dir, "data")
    os.makedirs(src, exist_ok=True)
    with open(os.path.join(src, "f"), "w") as f:
        f.write("data")
    spsrc = os.path.join(d.dir, "dir with space")
    os.makedirs(spsrc, exist_ok=True)
    ns = base_ns(d.dir) + [bind(src, "/ro"), bind(src, "/rw", True), symlink("/ro/f", "/link"), ent("tmpfs", "/scratch"),
                           bind(spsrc, "/with space")]
    c = config(d.dir, "sk", ["write", "/out", "sk", "/ro/x", "/rw/x", "/x", "/tmp/x", "/scratch/x", "/usr/x"], ns=ns)
    r = d.ctl("start " + c)
    check("ns: start", r == (0, "done", "-"), r)
    started(d, "sk")
    hp = d.hostpid("sk")
    table = [[w.replace("\\040", " ") for w in l.split()] for l in d.fact("sk", "ns").splitlines()]
    mi = parse_mountinfo(hp)
    check("ns: one table line per mount (same count as mountinfo)", len(table) == len(mi), (len(table), len(mi)))
    check("ns: mount points and ro/rw match mountinfo",
          sorted((t[2], t[3] == "ro") for t in table) == sorted(mi), (table, mi))
    check("ns: ns_check ok", d.fact("sk", "ns_check") == "ok\n", d.fact("sk", "ns_check"))
    same = True
    bad = []
    for t in table:
        if t[0] == "bind":
            a, b = os.stat(t[1]), os.stat("/proc/%d/root%s" % (hp, t[2]))
            if (a.st_dev, a.st_ino) != (b.st_dev, b.st_ino):
                same = False
                bad.append(t)
    check("ns: every bind line's source is the same file as its mount point", same, bad)
    locked = [t for t in table if t[-1] == "locked"]
    wsl = os.path.exists("/usr/lib/wsl")
    check("ns: locked submounts under /usr listed (%s)" % ("WSL" if wsl else "none expected"),
          (len(locked) > 0) == any(l.split()[4].startswith("/usr/") for l in read("/proc/self/mountinfo").splitlines()),
          locked)
    res = wait_for(lambda: os.path.exists(os.path.join(d.dir, "sk.txt")) and read(os.path.join(d.dir, "sk.txt")), 5) or ""
    want = {"/ro/x": "err EROFS", "/rw/x": "ok", "/x": "err EROFS", "/tmp/x": "ok", "/scratch/x": "ok", "/usr/x": "err EROFS"}
    got = dict(l.split(" ", 1) for l in res.strip().splitlines())
    check("ns: read-only and writable places behave as the table says", got == want, got)
    check("ns: the rw write landed in the host dir", os.path.exists(os.path.join(src, "x")))
    root = os.listdir("/proc/%d/root" % hp)
    check("ns: the proc's root holds only what the config put there",
          sorted(root) == sorted(["usr", "etc", "bin", "lib", "lib64", "dev", "proc", "tmp", "toys", "out", "ro", "rw",
                                  "link", "scratch", "with space"]), sorted(root))
    # ns.json：同一張表的 JSON
    raw = d.fact("sk", "ns.json")
    lines = raw.splitlines()
    check("nsjson: layout is [ / one object per line with commas / ]",
          lines[0] == "[" and lines[-1] == "]" and raw.endswith("]\n") and
          all(l.endswith("},") for l in lines[1:-2]) and lines[-2].endswith("}"), raw[:200])
    try:
        js = json.loads(raw)
    except ValueError as e:
        js = None
        check("nsjson: parses as JSON", False, e)
    if js is not None:
        check("nsjson: parses as JSON", isinstance(js, list))
        check("nsjson: same number of entries as ns lines", len(js) == len(table), (len(js), len(table)))
        check("nsjson: entries match ns lines (type, dst, rw, locked)",
              [(j["type"], j["dst"], j["rw"], bool(j.get("locked"))) for j in js] ==
              [(t[0], t[2], t[3] == "rw", t[-1] == "locked") for t in table], js)
        check("nsjson: rw always present, locked only when true, src omitted only where text has -",
              all(isinstance(j["rw"], bool) and j.get("locked", True) is True and ("src" not in j) == (t[1] == "-")
                  for j, t in zip(js, table)), js)
        sp = [j for j in js if j["dst"] == "/with space"]
        check("nsjson: a path with a space is a plain string", len(sp) == 1 and sp[0]["src"] == spsrc and
              "\\040" not in raw and '"dst": "/with space"' in raw, sp)
        check("nsjson: ns text keeps the \\040 form", "/with\\040space" in d.fact("sk", "ns"), d.fact("sk", "ns"))
        check("nsjson: ro/rw of the object-form binds (default ro, rw true writable)",
              {j["dst"]: j["rw"] for j in js if j["dst"] in ("/ro", "/rw", "/out")} == {"/ro": False, "/rw": True, "/out": True}, js)
    d.stop()


# ---------------------------------------------------------------- nsconf（設定的 ns 每條一個物件）

def t_nsconf():
    d = Daemon("nsconf")
    if not check("nsconf: daemon up", d.pid, d.err()):
        return
    started(d, "main")
    good = config(d.dir, "g", ["sleep"], ns=base_ns(d.dir) + [bind("/usr/bin", "/ub", False), ent("tmpfs", "/t2")])
    r = d.ctl("start " + good)
    check("nsconf: object entries start (rw optional)", r == (0, "done", "-") and started(d, "g"), r)
    cases = [
        ("string entry", base_ns(d.dir) + ["bind /usr /u2"], "object"),
        ("unknown entry key", base_ns(d.dir) + [{"type": "tmpfs", "dst": "/z", "mode": "1777"}], "unknown key"),
        ("missing dst", base_ns(d.dir) + [{"type": "tmpfs"}], "dst"),
        ("missing src", base_ns(d.dir) + [{"type": "bind", "dst": "/z"}], "src"),
        ("rw on a non-bind", base_ns(d.dir) + [{"type": "tmpfs", "dst": "/z", "rw": True}], "unknown key"),
        ("rw not boolean", base_ns(d.dir) + [bind("/usr", "/z", "yes")], "rw"),
        ("unknown type", base_ns(d.dir) + [{"type": "fuse", "dst": "/z"}], "unknown ns entry type"),
        ("dst not a string", base_ns(d.dir) + [{"type": "tmpfs", "dst": 5}], "dst"),
    ]
    for i, (what, ns, word) in enumerate(cases):
        r = d.ctl("start " + config(d.dir, "b%d" % i, ["sleep"], ns=ns))
        check("nsconf: %s rejected (EIO, failed, ConfigBad, clear message)" % what,
              r[0] == errno.EIO and r[1] == "failed" and "ConfigBad" in (r[2] or "") and word in (r[2] or ""), r)
    check("nsconf: rejected ones left nothing in procs/", sorted(os.listdir(d.root + "/procs")) == ["g", "main"],
          sorted(os.listdir(d.root + "/procs")))
    d.stop()
    d = Daemon("nsconf-init", init_extra={"ns": base_ns(os.path.join(TMP, "nsconf-init")) + ["tmpfs /x"]})
    rc = d.p.wait(10)
    check("nsconf: string entry in the --init file -> exit 2 with a message", rc == 2 and "ConfigBad" in d.err(),
          (rc, d.err()[-300:]))


# ---------------------------------------------------------------- landlock

def t_landlock():
    d = Daemon("landlock")
    if not check("landlock: daemon up", d.pid, d.err()):
        return
    started(d, "main")
    if int(d.status().get("landlock_abi", "0")) < 1:
        check("landlock: (skip) this Linux has no Landlock", True)
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
    check("landlock: init can read a proc's /proc/<pid>/root", ans and ans.startswith("ok") and "toys" in ans, ans)
    locks = d.fact("b", "locks")
    check("landlock: locks fact names the Landlock domain", locks.startswith("landlock: own domain"), locks)
    check("landlock: init's locks say no Landlock", d.fact("main", "locks").startswith("landlock: none"))
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
    check("mount: visible in its ns", os.path.exists("/proc/%d/root/live/hello" % hp))
    table = [l.split() for l in d.fact("m", "ns").splitlines()]
    check("mount: ns table has the new line (ro)", ["bind", src, "/live", "ro"] in table, table)
    nj = json.loads(d.fact("m", "ns.json"))
    check("mount: ns.json has the new mount too", {"type": "bind", "src": src, "dst": "/live", "rw": False} in map(nsrow, nj) and
          len(nj) == len(d.fact("m", "ns").splitlines()), nj)
    check("mount: table still matches mountinfo",
          sorted((t[2], t[3] == "ro") for t in table) == sorted(parse_mountinfo(hp)))
    r = d.ctl("mount m -w %s /out/sub/live" % src)
    check("mount: -w into a writable place", r == (0, "done", "-") and ["bind", src, "/out/sub/live", "rw"] in
          [l.split() for l in d.fact("m", "ns").splitlines()], r)
    r = d.ctl("umount m /live")
    table = [l.split() for l in d.fact("m", "ns").splitlines()]
    check("mount: umount -> gone from ns and table", r == (0, "done", "-") and
          not os.path.exists("/proc/%d/root/live/hello" % hp) and not any(t[2] == "/live" for t in table), r)
    nj = json.loads(d.fact("m", "ns.json"))
    check("mount: ns.json drops it after umount", not any(j["dst"] == "/live" for j in nj) and
          len(nj) == len(d.fact("m", "ns").splitlines()), nj)
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
    ok = wait_for(lambda: d.status().get("init_restarts") == "2" and started(d, "main", 0.1), 10)
    check("restart: init that died twice was restarted and runs", ok, d.status())
    check("restart: init_last_exit is code 5", d.status().get("init_last_exit") == "code 5")
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

    d = Daemon("restart3", ["exit", "4"], "--on-init-exit", "exit")
    rc = d.p.wait(10) if d.pid else None
    check("restart: --on-init-exit exit -> daemon exits with init's code 4", rc == 4, rc)
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
    """init 怎麼碰 daemon 的目錄：預設 mount（天空裡的 /aos、零 caps），設定 daemon_access ptrace 走 /proc/1/cwd。"""
    d = Daemon("access")
    if not check("access: daemon up", d.pid, d.err()):
        return
    started(d, "main")
    s = d.status()
    check("access: status says init_access: mount /aos", s.get("init_access") == "mount /aos", s)
    hp = d.hostpid("main")
    c = caps_of(hp)
    check("access: mount mode: init has zero capabilities (inh, prm, eff, bnd, amb)", not any(c.values()), c)
    kt = init_file(d)
    check("access: AOS_DAEMON=/aos, reads /aos/status", kt.startswith("ok pid_ns: 1") and "\nroot /aos\n" in kt, kt)
    check("access: ... and cannot read /proc/1/cwd (EACCES)", "\nproc1 err EACCES\n" in kt, kt)
    table = [l.split() for l in d.fact("main", "ns").splitlines()]
    cg_on = not s.get("cgroup", "off").startswith("off")
    check("access: init's ns table has 'aos - /aos rw'%s" % (" and the cgroup line" if cg_on else ""),
          ["aos", "-", "/aos", "rw"] in table and (not cg_on or ["cgroup", s["cgroup"], "/cgroup", "rw"] in table), table)
    check("access: ns_check ok", d.fact("main", "ns_check") == "ok\n", d.fact("main", "ns_check"))
    mi = [l.split() for l in read("/proc/%d/mountinfo" % hp).splitlines()]
    aos = [l for l in mi if l[4] == "/aos"]
    check("access: /aos in init's mountinfo is the daemon's FUSE mount",
          aos and aos[0][aos[0].index("-") + 1] == "fuse.aosproc", aos)
    check("access: init's locks say no capabilities, directory at /aos",
          "capabilities: none" in d.fact("main", "locks") and "daemon directory: /aos" in d.fact("main", "locks"),
          d.fact("main", "locks"))
    a = d.ask("/aos")
    check("access: init lists /aos", a == "ok __meta ctl procs status", a)
    cw = config(d.dir, "w", ["sleep"], locks={"cgroup": {"pids.max": "20"}} if cg_on else {})
    a = d.ask("ctl start " + cw)
    check("access: init writes 'start' into /aos/ctl; when the write returns the proc is alive",
          a == "ok" and d.fact("w", "state") == "alive\n", a)
    a = d.ask("/aos/procs/w/state")
    check("access: init reads /aos/procs/w/state", a == "ok alive|", a)
    a = d.ask("ctl start /nonexistent/x.json")
    check("access: init's failing start is EIO", a == "err EIO", a)
    a = d.ask("/aos/status")
    check("access: ... and the reason is in /aos/status", a and "aos_ctl_state: failed" in a.replace("|", "\n"), a)
    if cg_on:
        a = d.ask("/aos/procs/w/cgroup/pids.max")
        check("access: init follows procs/w/cgroup (relative link to /cgroup) and reads pids.max", a == "ok 20|", a)
    a = d.ask("ctl umount main /aos")
    check("access: ctl umount of /aos in init's ns is refused (EINVAL)", a == "err EINVAL", a)
    a = d.ask("ctl mount main /usr /aos")
    check("access: ctl mount over /aos is refused (EINVAL)", a == "err EINVAL" and
          d.status().get("aos_ctl_error", "").startswith("PathReserved"), (a, d.status().get("aos_ctl_error")))
    a = d.ask("ctl kill w KILL")
    wait_for(lambda: d.fact("w", "state") == "dead\n", 5)
    a2 = d.ask("ctl forget w")
    check("access: init kills and forgets; /aos/procs/w is gone for it", a == "ok" and a2 == "ok" and
          d.ask("/aos/procs/w") == "err ENOENT", (a, a2))
    # 非 init 的：沒有 /aos、讀不到 /proc/1/cwd、沒有 AOS_DAEMON
    d.ctl("start " + config(d.dir, "np", ["probe", "/out", "np", "/aos", "/proc/1/cwd/status", "env:AOS_DAEMON",
                                           "env:AOS_NAME", "/cgroup"]))
    res = wait_for(lambda: os.path.exists(os.path.join(d.dir, "np.txt")) and read(os.path.join(d.dir, "np.txt")), 5) or ""
    got = {l.split(" ")[0]: " ".join(l.split(" ")[1:]) for l in res.strip().splitlines()}
    check("access: non-main proc has no /aos", got.get("/aos") == "err ENOENT", got)
    check("access: non-main proc has no /cgroup", got.get("/cgroup") == "err ENOENT", got)
    check("access: non-main proc cannot read /proc/1/cwd", got.get("/proc/1/cwd/status") == "err EACCES", got)
    check("access: non-main proc gets no AOS_DAEMON (but gets AOS_NAME)",
          got.get("env:AOS_DAEMON") == "err unset" and got.get("env:AOS_NAME") == "ok np", got)
    bad = config(d.dir, "dacc", ["sleep"], daemon_access="ptrace")
    r = d.ctl("start " + bad)
    check("access: daemon_access in a non-main config -> EIO, failed ConfigBad",
          r[0] == errno.EIO and r[1] == "failed" and "daemon_access" in (r[2] or ""), r)
    check("access: /proc/<PID>/cwd from outside still works", d.status().get("pid_ns") == "1")
    d.stop()

    # ptrace 模式（舊的做法，設定裡選）
    d = Daemon("access-ptrace", init_extra={"daemon_access": "ptrace"})
    if not check("access: ptrace mode: daemon up", d.pid, d.err()):
        return
    started(d, "main")
    check("access: ptrace mode: status says ptrace /proc/1/cwd",
          d.status().get("init_access") == "ptrace /proc/1/cwd", d.status())
    c = caps_of(d.hostpid("main"))
    check("access: ptrace mode: init keeps only cap_sys_ptrace", c["CapEff"] == 1 << 19 and c["CapBnd"] == 1 << 19, c)
    kt = init_file(d)
    check("access: ptrace mode: AOS_DAEMON=/proc/1/cwd and it reads it",
          kt.startswith("ok pid_ns: 1") and "\nroot /proc/1/cwd\n" in kt, kt)
    check("access: ptrace mode: no /aos in its ns", d.ask("/aos") == "err ENOENT")
    a = d.ask("ctl start " + config(d.dir, "pw", ["sleep"]))
    check("access: ptrace mode: init's start through /proc/1/cwd/ctl works", a == "ok" and d.fact("pw", "state") == "alive\n", a)
    d.stop()

    # init 的天空自己用了 /aos：daemon 起不來，說明原因
    d = Daemon("access-clash", init_extra={"ns": base_ns(os.path.join(TMP, "access-clash")) + [ent("tmpfs", "/aos")]})
    rc = d.p.wait(10)
    check("access: init ns using /aos -> daemon exits 2 and says why", rc == 2 and "/aos" in d.err() and
          "daemon_access" in d.err(), (rc, d.err()[-300:]))

    # init 的 uid 不是 0：兩種模式都起不來
    for mode in ("mount", "ptrace"):
        d = Daemon("access-uid-" + mode, init_extra={"uid": 5, "daemon_access": mode})
        rc = d.p.wait(10)
        check("access: %s mode: init uid 5 -> daemon exits 2 and mentions uid" % mode,
              rc == 2 and "uid" in d.err() and "uid 0" in d.err(), (rc, d.err()[-300:]))


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
    want = {"name", "pid", "state", "exit", "started_at", "ended_at", "ns", "ns.json", "ns_check", "uid", "locks", "config", "__meta"}
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


def t_stdio():
    """proc 的 stdout／stderr 沒設就是 /dev/null（使用者 11-26 定）；設了的那條進檔，另一條仍無處去。"""
    d = Daemon("stdio", ["ichatter", "/out"])
    if not check("stdio: daemon up", d.pid, d.err()):
        return
    started(d, "main")
    errs = d.err()
    r = d.ctl("start " + config(d.dir, "plain", ["chatter", "/out"]))
    done = os.path.join(d.dir, "chatter.done")
    wait_for(lambda: os.path.exists(done), 5)
    check("stdio: proc without stdout/stderr started and wrote", r == (0, "done", "-") and os.path.exists(done), r)
    time.sleep(0.2)
    check("stdio: its output is not in the daemon's stderr", "CHATTER" not in d.err(), d.err()[-300:])
    check("stdio: init without stdout/stderr is silent too", "CHATTER" not in errs and "CHATTER" not in d.err())
    hp = d.hostpid("plain")
    fds = [os.readlink("/proc/%d/fd/%d" % (hp, i)) for i in (0, 1, 2)]
    check("stdio: fds 0, 1, 2 are all /dev/null", fds == ["/dev/null"] * 3, fds)
    kfds = [os.readlink("/proc/%d/fd/%d" % (d.hostpid("main"), i)) for i in (0, 1, 2)]
    check("stdio: init fds 0, 1, 2 are all /dev/null", kfds == ["/dev/null"] * 3, kfds)
    os.unlink(done)
    fo = os.path.join(d.dir, "only-out.log")
    r = d.ctl("start " + config(d.dir, "oo", ["chatter", "/out"], stdout=fo))
    wait_for(lambda: os.path.exists(done), 5)
    time.sleep(0.2)
    check("stdio: with stdout set the output lands in the file, stderr goes nowhere",
          r == (0, "done", "-") and read(fo) == "CHATTER-OUT\n" and "CHATTER" not in d.err(), (r, read(fo) if os.path.exists(fo) else None))
    fe = [os.readlink("/proc/%d/fd/%d" % (d.hostpid("oo"), i)) for i in (1, 2)]
    check("stdio: ... fd 2 is /dev/null", fe[1] == "/dev/null" and fe[0] == fo, fe)
    os.unlink(done)
    fe2 = os.path.join(d.dir, "only-err.log")
    r = d.ctl("start " + config(d.dir, "oe", ["chatter", "/out"], stderr=fe2))
    wait_for(lambda: os.path.exists(done), 5)
    time.sleep(0.2)
    check("stdio: with only stderr set it lands in the file, stdout goes nowhere",
          r == (0, "done", "-") and read(fe2) == "CHATTER-ERR\n" and "CHATTER" not in d.err(), r)
    check("stdio: the daemon's stdout stays at the export line only", d.line.startswith("export AOS_DAEMON="))
    d.stop()



# ---------------------------------------------------------------- dconf（daemon 設定檔，使用者 11-26 定）

def t_dconf():
    d = Daemon("dconf-flags")
    if not check("dconf: flags-only start still works", d.pid, d.err()):
        return
    s = d.status()
    check("dconf: flags only -> status config is -", s.get("config") == "-", s.get("config"))
    check("dconf: defaults: exit_grace 0 s, on_parent_death exit", s.get("exit_grace") == "0 s" and
          s.get("on_parent_death") == "exit", s)
    cg_on = not s.get("cgroup", "off").startswith("off")
    d.stop()

    # init 給絕對路徑
    dd = os.path.join(TMP, "dconf-abs")
    dj = write_json(os.path.join(dd, "daemon.json"), {"init": os.path.join(dd, "main.json")})
    d = Daemon("dconf-abs", args=[dj])
    if check("dconf: daemon.json with an absolute init path", d.pid and started(d, "main"), d.err()):
        s = d.status()
        check("dconf: status config is the daemon config path", s.get("config") == dj, s.get("config"))
        check("dconf: procs/main/config is init path", d.fact("main", "config") == os.path.join(dd, "main.json") + "\n",
              d.fact("main", "config"))
        check("dconf: cgroup auto still works with a daemon config (re-exec carried it)",
              s.get("cgroup", "off").startswith("off") != cg_on, s.get("cgroup"))
        check("dconf: SIGTERM -> exit 0", d.stop() == 0)

    # init 給相對路徑：從 daemon 設定檔的夾算，不是從 cwd
    dd = os.path.join(TMP, "dconf-rel")
    os.makedirs(os.path.join(dd, "k"), exist_ok=True)
    config(os.path.join(dd, "k"), "main", ["init", "/out"])
    dj = write_json(os.path.join(dd, "daemon.json"), {"init": "k/main.json"})
    d = Daemon("dconf-rel", args=[dj], cwd="/")
    if check("dconf: relative init path is relative to the daemon config's folder (cwd /)", d.pid and started(d, "main"), d.err()):
        check("dconf: ... procs/main/config shows the resolved path",
              d.fact("main", "config") == os.path.join(dd, "k", "main.json") + "\n", d.fact("main", "config"))
        check("dconf: ... that init is the one running", bool(wait_for(lambda: [n for n in os.listdir(os.path.join(dd, "k"))
                                                                               if n.startswith("init-")], 5)))
        d.stop()

    # daemon 設定檔本身給相對路徑（從 cwd 算），status 寫絕對路徑；經 systemd-run 重跑時也帶得過去
    dd = os.path.join(TMP, "dconf-relconf")
    write_json(os.path.join(dd, "daemon.json"), {"init": "main.json"})
    d = Daemon("dconf-relconf", args=["daemon.json"], cwd=dd)
    if check("dconf: daemon config given as a relative path", d.pid and started(d, "main"), d.err()):
        s = d.status()
        check("dconf: ... status config is absolute", s.get("config") == os.path.join(dd, "daemon.json"), s.get("config"))
        check("dconf: ... and cgroup is the same as with flags", s.get("cgroup", "off").startswith("off") != cg_on, s.get("cgroup"))
        d.stop()

    # 內嵌的 init 設定
    dd = os.path.join(TMP, "dconf-inline")
    os.makedirs(dd, exist_ok=True)
    kc = {"name": "inl", "argv": ["/usr/bin/python3", "/toys/toys.py", "init", "/out"], "ns": base_ns(dd)}
    dj = write_json(os.path.join(dd, "daemon.json"), {"init": kc})
    d = Daemon("dconf-inline", args=[dj])
    if check("dconf: inline init object starts", d.pid and started(d, "inl"), d.err()):
        check("dconf: ... status init is its name", d.status().get("init") == "inl", d.status())
        check("dconf: ... procs/inl/config is '<daemon.json>#/init'", d.fact("inl", "config") == dj + "#/init\n",
              d.fact("inl", "config"))
        kt = init_file(d)
        check("dconf: ... and it reads $AOS_DAEMON/status", kt.startswith("ok pid_ns: 1"), kt)
        d.stop()

    # 設定檔的值，與命令列蓋過它
    dd = os.path.join(TMP, "dconf-vals")
    vals = {"init": "main.json", "on_init_exit": "exit", "restart_limit": 2, "restart_window": 30, "exit_grace": 1.5,
            "on_parent_death": "stay", "cgroup": "off", "subuid": "off", "on_restart_limit": "stay", "exit_code": "own"}
    dj = write_json(os.path.join(dd, "daemon.json"), vals)
    d = Daemon("dconf-vals", args=[dj])
    if check("dconf: every key read from the file", d.pid and started(d, "main"), d.err()):
        s = d.status()
        check("dconf: status shows the file's values (on_init_exit, restart_limit, on_restart_limit, exit_code, exit_grace, "
              "on_parent_death, cgroup, subuid)",
              s.get("on_init_exit") == "exit" and s.get("restart_limit") == "2 deaths within 30 s" and
              s.get("on_restart_limit") == "stay" and s.get("exit_code") == "own" and
              s.get("exit_grace") == "1.5 s" and s.get("on_parent_death") == "stay" and
              s.get("cgroup") == 'off ("cgroup": "off" in the daemon config)' and s.get("subuid") == "none", s)
        check("dconf: ... SIGTERM -> exit 0", d.stop() == 0)
    d = Daemon("dconf-vals", args=[dj, "--on-init-exit", "restart", "--restart-limit", "7", "--exit-grace", "0",
                                   "--on-parent-death", "exit", "--cgroup", "auto", "--on-restart-limit", "exit",
                                   "--exit-code", "init"])
    if check("dconf: flags override the file", d.pid and started(d, "main"), d.err()):
        s = d.status()
        check("dconf: ... status shows the flags' values and keeps the rest from the file",
              s.get("on_init_exit") == "restart" and s.get("restart_limit") == "7 deaths within 30 s" and
              s.get("on_restart_limit") == "exit" and s.get("exit_code") == "init" and
              s.get("exit_grace") == "0 s" and s.get("on_parent_death") == "exit" and s.get("subuid") == "none", s)
        check("dconf: ... --cgroup auto beats \"cgroup\": \"off\" (and the flags survive the re-exec)",
              s.get("cgroup", "off").startswith("off") != cg_on, s.get("cgroup"))
        d.stop()

    # --init 蓋過 "init"
    dd = os.path.join(TMP, "dconf-kflag")
    os.makedirs(dd, exist_ok=True)
    kflag = config(dd, "kflag", ["init", "/out"])
    dj = write_json(os.path.join(dd, "daemon.json"), {"init": "main.json"})
    d = Daemon("dconf-kflag", args=[dj, "--init", kflag])
    if check("dconf: --init beats \"init\" in the file", d.pid and started(d, "kflag") and
             d.status().get("init") == "kflag" and not os.path.exists(d.root + "/procs/main"), d.err()):
        d.stop()

    # 起不來：退出碼 2，stderr 說明
    dd = os.path.join(TMP, "dconf-bad")
    os.makedirs(dd, exist_ok=True)
    config(dd, "main", ["init", "/out"])
    cases = [
        ("unknown key", {"init": "main.json", "colour": "red"}, 'unknown key "colour"'),
        ("restart_limit as a string", {"init": "main.json", "restart_limit": "5"}, "restart_limit"),
        ("restart_limit not an integer", {"init": "main.json", "restart_limit": 2.5}, "restart_limit"),
        ("on_init_exit bad value", {"init": "main.json", "on_init_exit": "maybe"}, "on_init_exit"),
        ("negative exit_grace", {"init": "main.json", "exit_grace": -1}, "exit_grace"),
        ("exit_grace as a string", {"init": "main.json", "exit_grace": "2"}, "exit_grace"),
        ("on_parent_death bad value", {"init": "main.json", "on_parent_death": "linger"}, "on_parent_death"),
        ("cgroup bad value", {"init": "main.json", "cgroup": True}, "cgroup"),
        ("init a number", {"init": 5}, '"init"'),
                ("not JSON", "{", "not JSON"),
        ("top level not an object", [], "object"),
        ("init file missing", {"init": "nope.json"}, "cannot read"),
        ("inline init without argv", {"init": {"name": "x"}}, "ConfigBad"),
    ]
    for i, (what, obj, word) in enumerate(cases):
        p = write_json(os.path.join(dd, "bad%d.json" % i), obj)
        r = subprocess.run([BIN, p], capture_output=True, text=True, timeout=20, cwd="/")
        check("dconf: %s -> exit 2 with a message" % what, r.returncode == 2 and word in r.stderr, (r.returncode, r.stderr[-300:]))
    good = os.path.join(dd, "bad0.json")
    for what, argv, word in [
        ("unreadable daemon config", ["/nonexistent/daemon.json"], "cannot read"),
        ("two daemon configs", [good, good], "only one"),
        ("--exit-grace not a number", ["--init", os.path.join(dd, "main.json"), "--exit-grace", "abc"], "--exit-grace"),
        ("--exit-grace negative", ["--init", os.path.join(dd, "main.json"), "--exit-grace", "-1"], "--exit-grace"),
        ("--on-parent-death bad value", ["--init", os.path.join(dd, "main.json"), "--on-parent-death", "maybe"], "--on-parent-death"),
    ]:
        r = subprocess.run([BIN, *argv], capture_output=True, text=True, timeout=20, cwd="/")
        check("dconf: %s -> exit 2 with a message" % what, r.returncode == 2 and word in r.stderr, (r.returncode, r.stderr[-300:]))


# ---------------------------------------------------------------- grace（結束寬限 exit_grace，使用者 11-26 定）

def stop_timed(d, sig=signal.SIGTERM, timeout=15):
    t0 = time.monotonic()
    d.p.send_signal(sig)
    try:
        rc = d.p.wait(timeout)
    except subprocess.TimeoutExpired:
        rc = None
    return rc, time.monotonic() - t0


def init_up(d):
    """init（toys.py init／igrace）alive 而且寫了 init-<PID>.txt（訊號處理已經裝好）。"""
    return started(d, "main") and init_file(d).startswith("ok")


def t_grace():
    d = Daemon("grace-clean", ["igrace", "/out", "clean"], "--exit-grace", "5")
    if not check("grace: daemon up with --exit-grace 5", d.pid and init_up(d), d.err()):
        return
    check("grace: status exit_grace: 5 s", d.status().get("exit_grace") == "5 s", d.status())
    d.ctl("start " + config(d.dir, "s1", ["sleep"]))
    started(d, "s1")
    pids = [d.hostpid("main"), d.hostpid("s1")]
    rc, el = stop_timed(d)
    check("grace: init that cleans up on SIGTERM: cleanup done, daemon exits 0",
          rc == 0 and os.path.exists(os.path.join(d.dir, "cleanup")), (rc, d.err()[-400:]))
    check("grace: ... stopped waiting as soon as init exited (%.1f s < 3 s of 5)" % el, el < 3, el)
    check("grace: ... the other procs were killed too", wait_for(lambda: all(gone(p) for p in pids), 3), pids)
    check("grace: ... init was not restarted", d.err().count("started main") == 1, d.err()[-400:])

    d = Daemon("grace-ignore", ["igrace", "/out", "ignore"], "--exit-grace", "2")
    init_up(d)
    d.ctl("start " + config(d.dir, "s1", ["sleep"]))
    started(d, "s1")
    pids = [d.hostpid("main"), d.hostpid("s1")]
    t0 = time.monotonic()
    d.p.send_signal(signal.SIGTERM)
    time.sleep(1.0)
    check("grace: during the grace only init got SIGTERM: init and other procs still alive, daemon still up",
          d.p.poll() is None and not any(gone(p) for p in pids) and d.status().get("pid_ns") == "1")
    try:
        rc = d.p.wait(10)
    except subprocess.TimeoutExpired:
        rc = None
    el = time.monotonic() - t0
    check("grace: init ignoring SIGTERM with --exit-grace 2: daemon exits 0 after about 2 s (%.2f s)" % el,
          rc == 0 and 1.8 <= el < 4, (rc, el))
    check("grace: ... then everything was killed", wait_for(lambda: all(gone(p) for p in pids), 3), pids)
    check("grace: ... and says why", "still running after exit_grace 2 s" in d.err(), d.err()[-300:])

    d = Daemon("grace-die", ["igrace", "/out", "die"], "--exit-grace", "5")
    init_up(d)
    rc, el = stop_timed(d)
    check("grace: init exiting with 3 during the grace is not restarted (on_init_exit restart); daemon exits 0 at once",
          rc == 0 and el < 2.5 and d.err().count("started main") == 1 and os.path.exists(os.path.join(d.dir, "term")),
          (rc, el, d.err()[-300:]))

    d = Daemon("grace-ctl", ["igrace", "/out", "ctl"], "--exit-grace", "5")
    init_up(d)
    d.ctl("start " + config(d.dir, "w", ["sleep"]))
    started(d, "w")
    rc, el = stop_timed(d)
    res = read(os.path.join(d.dir, "cleanup")).strip() if os.path.exists(os.path.join(d.dir, "cleanup")) else None
    check("grace: init uses ctl (kill, forget) during the grace", res == "ok ok err ENOENT" and rc == 0 and el < 4,
          (res, rc, el))

    d = Daemon("grace-stay", ["igrace", "/out", "stay"], "--exit-grace", "3")
    init_up(d)
    d.ctl("start " + config(d.dir, "s1", ["sleep"]))
    started(d, "s1")
    t0 = time.monotonic()
    d.p.send_signal(signal.SIGTERM)
    wait_for(lambda: os.path.exists(os.path.join(d.dir, "term")), 3)
    r = d.ctl("start " + config(d.dir, "s2", ["sleep"]))
    check("grace: ctl from outside works during the grace (start)", r == (0, "done", "-") and started(d, "s2"), r)
    a = d.ask("ctl kill s1 KILL")
    check("grace: init's ctl works during the grace (kill)", a == "ok" and wait_for(lambda: d.fact("s1", "state") == "dead\n", 3), a)
    d.p.send_signal(signal.SIGTERM)   # 寬限裡再來一次：不管，照樣等到時間到
    time.sleep(0.5)
    check("grace: a second SIGTERM during the grace does not cut it short", d.p.poll() is None and time.monotonic() - t0 < 2.8)
    s2 = d.hostpid("s2")
    try:
        rc = d.p.wait(10)
    except subprocess.TimeoutExpired:
        rc = None
    el = time.monotonic() - t0
    check("grace: ... daemon exits 0 after the 3 s (%.2f s), procs gone" % el, rc == 0 and 2.8 <= el < 5 and
          wait_for(lambda: gone(s2), 3), (rc, el))

    d = Daemon("grace-zero", ["igrace", "/out", "clean"])
    init_up(d)
    kp = d.hostpid("main")
    rc, el = stop_timed(d)
    check("grace: --exit-grace 0 (default): SIGTERM to init then SIGKILL at once, no cleanup, exit 0",
          rc == 0 and el < 1.5 and not os.path.exists(os.path.join(d.dir, "cleanup")) and wait_for(lambda: gone(kp), 3),
          (rc, el))

    d = Daemon("grace-int", ["igrace", "/out", "clean"], "--exit-grace", "5")
    init_up(d)
    rc, el = stop_timed(d, signal.SIGINT)
    check("grace: SIGINT gets the same grace", rc == 0 and os.path.exists(os.path.join(d.dir, "cleanup")) and el < 3, (rc, el))

    d = Daemon("grace-kexit", ["exit", "4"], "--on-init-exit", "exit", "--exit-grace", "5")
    t0 = time.monotonic()
    rc = d.p.wait(10) if d.pid else None
    check("grace: init already dead (on_init_exit exit): no grace, exits with its code 4 at once",
          rc == 4 and time.monotonic() - t0 < 3, rc)
    d = Daemon("grace-klimit", ["exit", "3"], "--restart-limit", "0", "--exit-grace", "5")
    t0 = time.monotonic()
    rc = d.p.wait(10) if d.pid else None
    check("grace: restart limit reached: no grace, exits 1 at once", rc == 1 and time.monotonic() - t0 < 3, rc)


# ---------------------------------------------------------------- pdeath（on_parent_death，使用者 11-26 定）

def our_scope_names():
    """proto8 的 daemon 也叫 aos-daemon，所以只認「aos-daemon-<我們起過的 PID>.scope」。"""
    return {"aos-daemon-%d.scope" % p.pid for p, _ in STARTED}


def units_left():
    if not shutil.which("systemctl"):
        return ""
    out = subprocess.run(["systemctl", "--user", "list-units", "--all", "--no-legend", "aos-daemon-*"],
                         capture_output=True, text=True).stdout
    ours = our_scope_names()
    return "\n".join(l for l in out.splitlines() if l.split()[:1] and l.split()[0].lstrip("●* ") in ours).strip()


def t_pdeath():
    d = Daemon("pdeath", None, "--on-parent-death", "stay")
    if not check("pdeath: daemon up with --on-parent-death stay", d.pid and started(d, "main"), d.err()):
        return
    s = d.status()
    check("pdeath: status on_parent_death: stay", s.get("on_parent_death") == "stay", s)
    cg = s.get("cgroup", "off")
    d.ctl("start " + config(d.dir, "s1", ["sleep"]))
    started(d, "s1")
    pids = [d.hostpid("main"), d.hostpid("s1")]
    os.kill(d.p.pid, signal.SIGKILL)
    d.p.wait(5)
    time.sleep(1.0)
    check("pdeath: kill -9 of the launcher: daemon keeps running", not gone(d.pid))
    check("pdeath: ... its directory is still readable through /proc/<daemon pid>/cwd", d.status().get("pid_ns") == "1")
    check("pdeath: ... its procs keep running", not any(gone(p) for p in pids), pids)
    r = d.ctl("start " + config(d.dir, "s2", ["sleep"]))
    check("pdeath: ... ctl still works", r == (0, "done", "-") and started(d, "s2"), r)
    pids.append(d.hostpid("s2"))
    if not cg.startswith("off"):
        check("pdeath: ... its cgroup scope is still there", os.path.isdir(cg), cg)
    os.kill(d.pid, signal.SIGTERM)
    check("pdeath: SIGTERM to the daemon itself ends it and all procs",
          wait_for(lambda: gone(d.pid) and all(gone(p) for p in pids), 5), pids)
    if not cg.startswith("off"):
        check("pdeath: ... systemd removes the scope once it is empty (the launcher's cleanup did not run)",
              wait_for(lambda: not os.path.exists(cg), 5), cg)
        check("pdeath: ... and the unit is gone", wait_for(lambda: units_left() == "", 5), units_left())


# ---------------------------------------------------------------- forgetk（forget -k，使用者 11-26 定）

def ns_to_host(ns_pid, word):
    """天空裡的 PID（daemon 那一層）→ 外面的 PID：找 cmdline 有 word、NSpid 最後一格是 ns_pid 的。"""
    for p in os.listdir("/proc"):
        if not p.isdigit():
            continue
        try:
            if word not in read("/proc/%s/cmdline" % p).split("\0"):
                continue
            nspid = re.search(r"NSpid:\s+(.*)", read("/proc/%s/status" % p)).group(1).split()
        except OSError:
            continue
        if len(nspid) == 2 and nspid[1] == str(ns_pid):
            return int(p)
    return None


def t_forgetk():
    d = Daemon("forgetk")
    if not check("forgetk: daemon up", d.pid and started(d, "main"), d.err()):
        return
    cg = d.status().get("cgroup", "off")
    if cg.startswith("off"):
        check("forgetk: (skip) %s" % cg, True)
        d.stop()
        return
    d.ctl("start " + config(d.dir, "orph", ["orphan", "/out", "orph"]))
    wait_for(lambda: d.fact("orph", "state") == "dead\n" and os.path.exists(os.path.join(d.dir, "orph.orphan")), 5)
    link = d.root + "/procs/orph/cgroup"
    host_cg = os.path.join(cg, os.readlink(link).split("/")[-1])
    left = [int(x) for x in read(link + "/cgroup.procs").split()]
    check("forgetk: dead proc left a child in its cgroup", d.fact("orph", "state") == "dead\n" and left and
          not any(gone(p) for p in left), left)
    r = d.ctl("forget orph")
    check("forgetk: plain forget still refuses (EIO, failed CgroupNotEmpty, hints at forget -k)",
          r[0] == errno.EIO and r[1] == "failed" and (r[2] or "").startswith("CgroupNotEmpty") and "forget -k" in r[2] and
          os.path.isdir(d.root + "/procs/orph") and not any(gone(p) for p in left), r)
    r = d.ctl("forget -k orph")
    check("forgetk: forget -k -> done", r == (0, "done", "-"), r)
    check("forgetk: ... procs/orph is gone when the write returns", not os.path.lexists(d.root + "/procs/orph"))
    check("forgetk: ... the leftover child is gone", wait_for(lambda: all(gone(p) for p in left), 3), left)
    check("forgetk: ... its cgroup dir is removed", not os.path.exists(host_cg), host_cg)
    check("forgetk: ... the daemon logged cgroup.kill", "wrote cgroup.kill" in d.err())
    r = d.ctl("forget -k main")
    check("forgetk: forget -k of a live proc -> EINVAL ProcAlive", r[0] == errno.EINVAL and (r[2] or "").startswith("ProcAlive"), r)
    r = d.ctl("forget -k nobody")
    check("forgetk: forget -k of an unknown name -> EINVAL ProcUnknown", r[0] == errno.EINVAL and
          (r[2] or "").startswith("ProcUnknown"), r)
    r1, r2 = d.ctl("forget -k"), d.ctl("forget -x main")
    check("forgetk: bad usage -> EINVAL ArgumentsBad", r1[0] == errno.EINVAL and r2[0] == errno.EINVAL and
          (r1[2] or "").startswith("ArgumentsBad") and (r2[2] or "").startswith("ArgumentsBad"), (r1, r2))
    d.ctl("start " + config(d.dir, "e0", ["exit", "0"]))
    wait_for(lambda: d.fact("e0", "state") == "dead\n", 5)
    r = d.ctl("forget -k e0")
    check("forgetk: forget -k of a dead proc with an empty cgroup -> done", r == (0, "done", "-") and
          not os.path.lexists(d.root + "/procs/e0"), r)
    d.ctl("start " + config(d.dir, "orph2", ["orphan", "/out", "orph2"]))
    wait_for(lambda: d.fact("orph2", "state") == "dead\n" and os.path.exists(os.path.join(d.dir, "orph2.orphan")), 5)
    left = [int(x) for x in read(d.root + "/procs/orph2/cgroup/cgroup.procs").split()]
    a = d.ask("ctl forget -k orph2")
    check("forgetk: init's forget -k through /aos/ctl works", a == "ok" and left and
          not os.path.lexists(d.root + "/procs/orph2") and wait_for(lambda: all(gone(p) for p in left), 3), (a, left))
    d.stop()

    d = Daemon("forgetk-off", None, "--cgroup", "off")
    if not check("forgetk: --cgroup off: daemon up", d.pid and started(d, "main"), d.err()):
        return
    d.ctl("start " + config(d.dir, "orph", ["orphan", "/out", "orph"]))
    wait_for(lambda: d.fact("orph", "state") == "dead\n" and os.path.exists(os.path.join(d.dir, "orph.orphan")), 5)
    child = ns_to_host(read(os.path.join(d.dir, "orph.orphan")).strip(), "orphan")
    r = d.ctl("forget -k orph")
    check("forgetk: --cgroup off: forget -k is plain forget (done, procs/orph gone)",
          r == (0, "done", "-") and not os.path.lexists(d.root + "/procs/orph"), r)
    check("forgetk: --cgroup off: ... its leftover child is untouched (nothing to clear without a cgroup)",
          child is not None and not gone(child), child)
    d.stop()
    check("forgetk: --cgroup off: ... and goes with the daemon", child is not None and wait_for(lambda: gone(child), 3), child)


# ---------------------------------------------------------------- rename（主 kernel 改名 init，使用者 11-26 定）

def t_rename():
    d = Daemon("rename")
    if not check("rename: daemon up with --init", d.pid and started(d, "main"), d.err()):
        return
    s = d.status()
    want = {"init": "main", "init_state": "alive", "on_init_exit": "restart", "on_restart_limit": "exit", "exit_code": "init",
            "init_restarts": "0", "init_deaths_in_window": "0", "init_last_exit": "-", "init_access": "mount /aos"}
    check("rename: status has the init lines with today's defaults", {k: s.get(k) for k in want} == want, s)
    check("rename: no status line is named after the kernel any more", not any("kernel" in k for k in s), list(s))
    check("rename: the daemon's log says init",
          wait_for(lambda: re.search(r"started main \(pid \d+, host pid \d+, init\)", d.err()), 3), d.err()[-300:])
    d.stop()
    dd = os.path.join(TMP, "rename-bad")
    os.makedirs(dd, exist_ok=True)
    main = config(dd, "main", ["init", "/out"])
    for i, (what, obj, word) in enumerate([
        ('old key "kernel"', {"kernel": "main.json"}, 'unknown key "kernel"'),
        ('old key "on_kernel_exit"', {"init": "main.json", "on_kernel_exit": "exit"}, 'unknown key "on_kernel_exit"'),
        ("on_restart_limit bad value", {"init": "main.json", "on_restart_limit": "maybe"}, "on_restart_limit"),
        ("exit_code bad value", {"init": "main.json", "exit_code": 3}, "exit_code"),
    ]):
        p = write_json(os.path.join(dd, "bad%d.json" % i), obj)
        r = subprocess.run([BIN, p], capture_output=True, text=True, timeout=20, cwd="/")
        check("rename: %s -> exit 2 with a message" % what, r.returncode == 2 and word in r.stderr, (r.returncode, r.stderr[-300:]))
    for what, argv, word in [
        ("old flag --kernel", ["--kernel", main], "unknown argument --kernel"),
        ("old flag --on-kernel-exit", ["--init", main, "--on-kernel-exit", "exit"], "unknown argument --on-kernel-exit"),
        ("--on-init-exit bad value", ["--init", main, "--on-init-exit", "maybe"], "--on-init-exit"),
        ("--on-restart-limit bad value", ["--init", main, "--on-restart-limit", "maybe"], "--on-restart-limit"),
        ("--exit-code bad value", ["--init", main, "--exit-code", "maybe"], "--exit-code"),
        ("flags only without --init", ["--exit-grace", "1"], '--init CONFIG is required'),
    ]:
        r = subprocess.run([BIN, *argv], capture_output=True, text=True, timeout=20, cwd="/")
        check("rename: %s -> exit 2 with a message" % what, r.returncode == 2 and word in r.stderr, (r.returncode, r.stderr[-300:]))
    r = subprocess.run([BIN, "--exit-grace", "1"], capture_output=True, text=True, timeout=20, cwd="/")
    check("rename: ... and that message points at a daemon config without \"init\"", 'without "init"' in r.stderr, r.stderr)
    r = subprocess.run([BIN, "--help"], capture_output=True, text=True, timeout=20)
    check("rename: --help speaks of init, not the main kernel", r.returncode == 0 and "--init CONFIG" in r.stdout and
          "main kernel" not in r.stdout and "--kernel" not in r.stdout, r.stdout[:200])


# ---------------------------------------------------------------- noinit（daemon 設定檔不寫 init，使用者 11-26 定）

def t_noinit():
    dd = os.path.join(TMP, "noinit")
    dj = write_json(os.path.join(dd, "daemon.json"), {"exit_grace": 5})
    d = Daemon("noinit", args=[dj])
    if not check("noinit: daemon config without \"init\": daemon up", d.pid, d.err()):
        return
    s = d.status()
    check("noinit: status init -, init_state none, init_access -", s.get("init") == "-" and
          s.get("init_state", "").startswith("none") and s.get("init_access") == "-", s)
    check("noinit: procs/ is empty", os.listdir(d.root + "/procs") == [] and s.get("procs") == "0", os.listdir(d.root + "/procs"))
    check("noinit: the daemon logs that it has no init", "no init" in d.err(), d.err()[-300:])
    r = d.ctl("start " + config(d.dir, "np", ["probe", "/out", "np", "env:AOS_DAEMON", "env:AOS_NAME", "/aos", "/proc/1/cwd/status"]))
    check("noinit: start from outside (/proc/<PID>/cwd/ctl) works", r == (0, "done", "-") and started(d, "np"), r)
    res = wait_for(lambda: os.path.exists(os.path.join(d.dir, "np.txt")) and read(os.path.join(d.dir, "np.txt")), 5) or ""
    got = {l.split(" ")[0]: " ".join(l.split(" ")[1:]) for l in res.strip().splitlines()}
    check("noinit: the proc gets no AOS_DAEMON (AOS_NAME yes), no /aos, no /proc/1/cwd",
          got.get("env:AOS_DAEMON") == "err unset" and got.get("env:AOS_NAME") == "ok np" and got.get("/aos") == "err ENOENT" and
          got.get("/proc/1/cwd/status") == "err EACCES", got)
    r1 = d.ctl("kill np KILL")
    wait_for(lambda: d.fact("np", "state") == "dead\n", 5)
    r2 = d.ctl("forget np")
    check("noinit: kill and forget from outside", r1 == (0, "done", "-") and r2 == (0, "done", "-") and
          not os.path.lexists(d.root + "/procs/np"), (r1, r2))
    d.ctl("start " + config(d.dir, "s1", ["sleep"]))
    started(d, "s1")
    hp = d.hostpid("s1")
    rc, el = stop_timed(d)
    check("noinit: SIGTERM with exit_grace 5: nobody to wait for, exits 0 at once (%.2f s)" % el, rc == 0 and el < 2, (rc, el))
    check("noinit: ... the procs are gone", wait_for(lambda: gone(hp), 3))
    check("noinit: ... and the log says why", "no init" in d.err().splitlines()[-1], d.err()[-200:])
    d = Daemon("noinit-flag", args=[dj, "--init", os.path.join(TMP, "noinit-flag", "main.json")])
    check("noinit: --init with that daemon config gives an init", d.pid and started(d, "main") and d.status().get("init") == "main",
          d.err()[-300:])
    d.stop()


# ---------------------------------------------------------------- rlstay（on_restart_limit stay，使用者 11-26 定）

def t_rlstay():
    d = Daemon("rlstay", ["sleep"], "--restart-limit", "1", "--on-restart-limit", "stay")
    if not check("rlstay: daemon up with --on-restart-limit stay", d.pid and started(d, "main"), d.err()):
        return
    check("rlstay: status on_restart_limit: stay", d.status().get("on_restart_limit") == "stay", d.status())
    d.ctl("start " + config(d.dir, "w", ["sleep"]))
    started(d, "w")
    wp = d.hostpid("w")
    d.ctl("kill main KILL")
    check("rlstay: first death: init restarted", wait_for(lambda: d.status().get("init_restarts") == "1" and started(d, "main", 0.1), 5),
          d.status())
    d.ctl("kill main KILL")
    st = wait_for(lambda: d.status().get("init_state", "").startswith("gone") and d.status(), 5) or d.status()
    time.sleep(0.3)
    check("rlstay: past the limit the daemon stays up", d.p.poll() is None and d.status().get("pid_ns") == "1")
    check("rlstay: status says init is gone because the limit was hit", st.get("init") == "main" and
          "restart limit reached" in st.get("init_state", "") and "stay" in st.get("init_state", "") and
          st.get("init_restarts") == "1", st)
    check("rlstay: the dead init stays listed (dead, signal 9)", d.fact("main", "state") == "dead\n" and
          d.fact("main", "exit") == "signal 9 SIGKILL\n", d.fact("main", "exit"))
    check("rlstay: it was not restarted again", d.err().count("started main") == 2 and "not restarting" in d.err(), d.err()[-300:])
    check("rlstay: the other proc keeps running", not gone(wp) and d.fact("w", "state") == "alive\n")
    r = d.ctl("start " + config(d.dir, "s2", ["sleep"]))
    check("rlstay: outside ctl still works (start)", r == (0, "done", "-") and started(d, "s2"), r)
    r = d.ctl("forget main")
    check("rlstay: the dead init can be forgotten", r == (0, "done", "-") and not os.path.lexists(d.root + "/procs/main"), r)
    rc, el = stop_timed(d)
    check("rlstay: SIGTERM: exits 0 at once, procs gone", rc == 0 and el < 2 and wait_for(lambda: gone(wp), 3), (rc, el))


# ---------------------------------------------------------------- dpath（init 的 daemon_path，使用者 11-26 定）

def t_dpath():
    dd = os.path.join(TMP, "dpath")
    d = Daemon("dpath", None, init_extra={"daemon_path": "/run/aos", "ns": base_ns(dd) + [ent("tmpfs", "/aos")]})
    if not check("dpath: daemon up with daemon_path /run/aos", d.pid and started(d, "main"), d.err()):
        return
    s = d.status()
    cg_on = not s.get("cgroup", "off").startswith("off")
    check("dpath: status init_access: mount /run/aos", s.get("init_access") == "mount /run/aos", s)
    kt = init_file(d)
    check("dpath: AOS_DAEMON=/run/aos and init reads $AOS_DAEMON/status", kt.startswith("ok pid_ns: 1") and "\nroot /run/aos\n" in kt, kt)
    table = [l.split() for l in d.fact("main", "ns").splitlines()]
    check("dpath: ns rows at the configured places ('aos - /run/aos rw'%s)" % (", cgroup at /run/cgroup" if cg_on else ""),
          ["aos", "-", "/run/aos", "rw"] in table and (not cg_on or ["cgroup", s["cgroup"], "/run/cgroup", "rw"] in table) and
          d.fact("main", "ns_check") == "ok\n", table)
    nj = json.loads(d.fact("main", "ns.json"))
    check("dpath: ns.json too", {"type": "aos", "dst": "/run/aos", "rw": True} in map(nsrow, nj), nj)
    locks = d.fact("main", "locks")
    check("dpath: locks name the configured places", "daemon directory: /run/aos" in locks and
          (not cg_on or "cgroup directory at /run/cgroup" in locks), locks)
    check("dpath: /aos is now just its own tmpfs (empty)", d.ask("/aos") == "ok", d.ask("/aos"))
    cw = config(d.dir, "w", ["sleep"], locks={"cgroup": {"pids.max": "20"}} if cg_on else {})
    a = d.ask("ctl start " + cw)
    check("dpath: init starts a proc through /run/aos/ctl", a == "ok" and d.fact("w", "state") == "alive\n", a)
    if cg_on:
        a = d.ask("/run/aos/procs/w/cgroup/pids.max")
        check("dpath: procs/w/cgroup (../../../cgroup/…) resolves to /run/cgroup inside init", a == "ok 20|", a)
        check("dpath: ... /run/cgroup holds the proc's cgroup dir",
              (d.ask("/run/cgroup") or "").split()[1:].count(os.readlink(d.root + "/procs/w/cgroup").split("/")[-1]) == 1)
    a = d.ask("ctl umount main /run/aos")
    check("dpath: ctl umount of /run/aos is refused (EINVAL PathReserved)", a == "err EINVAL" and
          d.status().get("aos_ctl_error", "").startswith("PathReserved /run/aos"), (a, d.status().get("aos_ctl_error")))
    if cg_on:
        a = d.ask("ctl mount main /usr /run/cgroup/x")
        check("dpath: ctl mount under /run/cgroup is refused (EINVAL PathReserved)", a == "err EINVAL" and
              d.status().get("aos_ctl_error", "").startswith("PathReserved /run/cgroup"), (a, d.status().get("aos_ctl_error")))
    a = d.ask("ctl mount main /usr /aos")
    check("dpath: /aos is not reserved any more: ctl mount over it works", a == "ok" and
          ["bind", "/usr", "/aos", "ro"] in [l.split() for l in d.fact("main", "ns").splitlines()], a)
    r = d.ctl("start " + config(d.dir, "dp", ["sleep"], daemon_path="/run/aos"))
    check("dpath: daemon_path in a non-init config -> EIO, failed ConfigBad", r[0] == errno.EIO and r[1] == "failed" and
          "daemon_path" in (r[2] or ""), r)
    d.stop()
    d = Daemon("dpath-clash", init_extra={"daemon_path": "/run/aos", "ns": base_ns(os.path.join(TMP, "dpath-clash")) +
                                                                          [ent("tmpfs", "/run/aos")]})
    rc = d.p.wait(10)
    check("dpath: init ns using its daemon_path -> exit 2 and says why", rc == 2 and "/run/aos" in d.err() and
          "daemon_path" in d.err(), (rc, d.err()[-300:]))
    for i, (what, extra) in enumerate([("relative", {"daemon_path": "run/aos"}), ("/", {"daemon_path": "/"}),
                                       ("trailing /", {"daemon_path": "/run/aos/"}), ("..", {"daemon_path": "/run/../aos"}),
                                       ("/cgroup (where the cgroup dir goes)", {"daemon_path": "/cgroup"}),
                                       ("/x/cgroup", {"daemon_path": "/x/cgroup"}), ("a number", {"daemon_path": 5}),
                                       ("with ptrace", {"daemon_path": "/run/aos", "daemon_access": "ptrace"})]):
        d = Daemon("dpath-bad%d" % i, init_extra=extra)
        rc = d.p.wait(10)
        check("dpath: daemon_path %s -> exit 2 with a message" % what, rc == 2 and "daemon_path" in d.err(), (rc, d.err()[-300:]))


# ---------------------------------------------------------------- ilandlock（init 的 locks.landlock，使用者 11-26 定）

def t_ilandlock():
    d = Daemon("ilandlock", None, init_extra={"locks": {"landlock": True}})
    if not check("ilandlock: daemon up with init locks.landlock true", d.pid and started(d, "main"), d.err()):
        return
    if int(d.status().get("landlock_abi", "0")) < 1:
        check("ilandlock: (skip) this Linux has no Landlock", True)
        d.stop()
        return
    s = d.status()
    cg_on = not s.get("cgroup", "off").startswith("off")
    locks = d.fact("main", "locks")
    check("ilandlock: init's locks say it has its own Landlock domain", locks.startswith("landlock: own domain") and
          "init asked for it" in locks, locks)
    check("ilandlock: ... and still no capabilities", not any(caps_of(d.hostpid("main")).values()))
    kt = init_file(d)
    check("ilandlock: init reads $AOS_DAEMON/status", kt.startswith("ok pid_ns: 1") and "\nroot /aos\n" in kt, kt)
    cw = config(d.dir, "w", ["sleep"], locks={"cgroup": {"pids.max": "20"}} if cg_on else {})
    a = d.ask("ctl start " + cw)
    check("ilandlock: init starts a proc through /aos/ctl", a == "ok" and d.fact("w", "state") == "alive\n", a)
    check("ilandlock: init reads /aos/procs/w/state", d.ask("/aos/procs/w/state") == "ok alive|")
    if cg_on:
        check("ilandlock: init reads the proc's cgroup folder", d.ask("/aos/procs/w/cgroup/pids.max") == "ok 20|")
        a = d.ask("put:/aos/procs/w/cgroup/cgroup.freeze=1")
        check("ilandlock: init writes the proc's cgroup.freeze (frozen)", a == "ok" and
              wait_for(lambda: "frozen 1" in read(d.root + "/procs/w/cgroup/cgroup.events"), 3), a)
        d.ask("put:/aos/procs/w/cgroup/cgroup.freeze=0")
    w_ns = re.search(r"ns: (\d+)", d.fact("w", "pid")).group(1)
    a = d.ask("/proc/%s/root" % w_ns)
    check("ilandlock: measured: in its own domain init cannot read a proc's /proc/<pid>/root (%s)" % a,
          (a or "").startswith("err EACCES"), a)
    a1 = d.ask("ctl kill w KILL")
    wait_for(lambda: d.fact("w", "state") == "dead\n", 5)
    a2 = d.ask("ctl forget w")
    check("ilandlock: init kills and forgets", a1 == "ok" and a2 == "ok" and not os.path.lexists(d.root + "/procs/w"), (a1, a2))
    d.stop()


# ---------------------------------------------------------------- exitcode（exit_code init|own，使用者 11-26 定）

def t_exitcode():
    d = Daemon("exitcode", ["exit", "4"], "--on-init-exit", "exit", "--exit-code", "own")
    rc = d.p.wait(10) if d.pid else None
    check("exitcode: own: init exits 4 -> daemon exits 3", rc == 3, (rc, d.err()[-300:]))
    check("exitcode: ... and says so", "exit_code own" in d.err(), d.err()[-300:])
    d = Daemon("exitcode-sig", ["sleep"], "--on-init-exit", "exit", "--exit-code", "own")
    started(d, "main")
    os.kill(d.hostpid("main"), signal.SIGKILL)   # 不經 ctl：daemon 馬上結束，ctl 之後讀 status 會斷
    rc = d.p.wait(10) if d.pid else None
    check("exitcode: own: init killed by SIGKILL -> daemon exits 3 (not 137)", rc == 3, rc)
    d = Daemon("exitcode-init", ["exit", "4"], "--on-init-exit", "exit", "--exit-code", "init")
    rc = d.p.wait(10) if d.pid else None
    check("exitcode: init (default): daemon exits with init's code 4", rc == 4, rc)
    d = Daemon("exitcode-term", None, "--exit-code", "own")
    started(d, "main")
    check("exitcode: own: status exit_code own; SIGTERM still exits 0", d.status().get("exit_code") == "own" and d.stop() == 0)
    d = Daemon("exitcode-limit", ["exit", "3"], "--restart-limit", "0", "--exit-code", "own")
    rc = d.p.wait(10) if d.pid else None
    check("exitcode: own: restart limit still exits 1", rc == 1, rc)


# ---------------------------------------------------------------- net（net none|host，使用者 11-26 定）

def t_net():
    import socket
    lis = socket.socket()
    lis.bind(("127.0.0.1", 0))
    lis.listen(16)
    port = lis.getsockname()[1]
    try:
        d = Daemon("net")
        if not check("net: daemon up", d.pid and started(d, "main"), d.err()):
            return
        mynet = os.readlink("/proc/self/ns/net")
        check("net: init defaults to net none", "net: none (own netns, loopback only)" in d.fact("main", "locks") and
              os.readlink("/proc/%d/ns/net" % d.hostpid("main")) != mynet, d.fact("main", "locks"))

        def result(name):
            return wait_for(lambda: os.path.exists(os.path.join(d.dir, name + ".txt")) and read(os.path.join(d.dir, name + ".txt")), 8) or ""

        r = d.ctl("start " + config(d.dir, "nn", ["net", "/out", "nn", str(port)]))
        got = dict(l.split(" ", 1) for l in result("nn").strip().splitlines())
        check("net: default proc started", r == (0, "done", "-"), r)
        check("net: none: cannot reach a port listening on the outside's 127.0.0.1 (%s)" % got.get("host"),
              got.get("host", "").startswith("err"), got)
        check("net: none: its own 127.0.0.1 works (bind, connect, send)", got.get("loop") == "ok", got)
        check("net: none: /proc/net/dev lists only lo", got.get("ifaces") == "lo", got)
        check("net: none: locks say so", "net: none (own netns, loopback only)" in d.fact("nn", "locks"), d.fact("nn", "locks"))
        check("net: none: its own network namespace", os.readlink("/proc/%d/ns/net" % d.hostpid("nn")) != mynet)
        r = d.ctl("start " + config(d.dir, "nh", ["net", "/out", "nh", str(port)], net="host"))
        got = dict(l.split(" ", 1) for l in result("nh").strip().splitlines())
        hostifs = ",".join(sorted(l.split(":")[0].strip() for l in read("/proc/net/dev").splitlines()[2:]))
        check("net: host: started", r == (0, "done", "-"), r)
        check("net: host: reaches the port on the outside's 127.0.0.1", got.get("host") == "ok", got)
        check("net: host: its own 127.0.0.1 works too", got.get("loop") == "ok", got)
        check("net: host: sees the outside's interfaces", got.get("ifaces") == hostifs, (got, hostifs))
        check("net: host: locks say so", "net: host" in d.fact("nh", "locks"), d.fact("nh", "locks"))
        check("net: host: same network namespace as the daemon", os.readlink("/proc/%d/ns/net" % d.hostpid("nh")) == mynet)
        for i, v in enumerate(["maybe", 5]):
            r = d.ctl("start " + config(d.dir, "nb%d" % i, ["sleep"], net=v))
            check("net: net %r -> EIO, failed ConfigBad" % (v,), r[0] == errno.EIO and r[1] == "failed" and
                  "ConfigBad" in (r[2] or "") and "net" in (r[2] or ""), r)
        d.stop()
        d = Daemon("net-init", None, init_extra={"net": "host"})
        check("net: init with net host shares the daemon's network namespace", d.pid and started(d, "main") and
              "net: host" in d.fact("main", "locks") and os.readlink("/proc/%d/ns/net" % d.hostpid("main")) == mynet, d.err()[-300:])
        d.stop()
    finally:
        lis.close()


# ---------------------------------------------------------------- seccomp

SC_DENIED = ["ptrace", "bpf", "init_module", "finit_module", "kcmp", "personality_aslr", "keyctl", "userfaultfd",
             "io_uring_setup", "name_to_handle_at", "syslog", "process_vm_readv", "reboot", "swapon", "acct", "clock_settime"]
SC_OFF_OK = ["kcmp", "personality_aslr", "process_vm_readv"]   # 核心本來就放（不用權限），只有內建的擋單擋
SC_ALLOWED = ["getpid", "getppid", "personality_query"]


def seccomp_filters(pid="self"):
    st = read("/proc/%s/status" % pid)
    return re.search(r"Seccomp:\s+(\d+)", st).group(1), int(re.search(r"Seccomp_filters:\s+(\d+)", st).group(1))


def results(d, name, timeout=8):
    p = os.path.join(d.dir, name + ".txt")
    t = wait_for(lambda: os.path.exists(p) and read(p), timeout) or ""
    return dict(l.split(" ", 1) for l in t.strip().splitlines() if " " in l)


def x86_64_names():
    """系統呼叫名字（從 asm/unistd_64.h 讀；編 daemon 本來就要 linux 的標頭）。"""
    for h in ("/usr/include/x86_64-linux-gnu/asm/unistd_64.h", "/usr/include/asm/unistd_64.h"):
        if os.path.exists(h):
            return re.findall(r"#define __NR_(\w+) \d+", read(h))
    return []


def t_seccomp():
    mine = seccomp_filters()[1]   # 起測試的這一層本身可能已經有過濾器（例：沙盒），daemon 與底下都會繼承
    d = Daemon("seccomp", ["isys", "/out"] + SC_DENIED + SC_ALLOWED)
    if not check("seccomp: daemon up (init runs with the built-in list)", d.pid and started(d, "main"), d.err()):
        return
    got = results(d, "isys")
    check("seccomp: init: the built-in list denies %s with EPERM" % ", ".join(SC_DENIED),
          all(got.get(c) == "err EPERM" for c in SC_DENIED), got)
    check("seccomp: init: getpid, getppid, personality(0xffffffff) still work", all(got.get(c) == "ok" for c in SC_ALLOWED), got)
    lk = d.fact("main", "locks")
    check("seccomp: init: locks say seccomp: builtin (44 syscalls denied ...)",
          "\nseccomp: builtin (44 syscalls denied with EPERM, personality limited to safe values; other arch and x32 calls kill the process)\n" in lk, lk)
    hp = d.hostpid("main")
    check("seccomp: init: /proc status shows mode 2 and one more filter than the outside", seccomp_filters(hp) == ("2", mine + 1),
          (seccomp_filters(hp), mine))
    check("seccomp: init still does its job with the built-in list (reads $AOS_DAEMON/status)", init_file(d).startswith("ok pid_ns: 1"))
    r = d.ask("ctl start " + config(d.dir, "via", ["sleep"]))
    check("seccomp: ... and starts a proc through its ctl", r == "ok" and started(d, "via"), r)
    check("seccomp: the daemon itself has no filter of its own (only what it inherited)", seccomp_filters(d.pid)[1] == mine,
          seccomp_filters(d.pid))

    # 一般 proc：預設（不寫）
    r = d.ctl("start " + config(d.dir, "sb", ["sys", "/out", "sb"] + SC_DENIED + SC_ALLOWED))
    got = results(d, "sb")
    check("seccomp: default proc started", r == (0, "done", "-"), r)
    check("seccomp: default proc: the built-in list denies them all with EPERM", all(got.get(c) == "err EPERM" for c in SC_DENIED), got)
    check("seccomp: default proc: getpid, getppid, personality query work", all(got.get(c) == "ok" for c in SC_ALLOWED), got)
    check("seccomp: default proc: locks line", "\nseccomp: builtin (44 syscalls denied" in d.fact("sb", "locks"), d.fact("sb", "locks"))
    check("seccomp: default proc: one filter more than the outside", seccomp_filters(d.hostpid("sb")) == ("2", mine + 1))
    r = d.ctl("start " + config(d.dir, "sbx", ["sys", "/out", "sbx", "kcmp"], locks={"seccomp": "builtin"}))
    check("seccomp: \"seccomp\": \"builtin\" is the same as not writing it", r == (0, "done", "-") and
          results(d, "sbx").get("kcmp") == "err EPERM" and "\nseccomp: builtin (44" in d.fact("sbx", "locks"), r)

    # off
    r = d.ctl("start " + config(d.dir, "so", ["sys", "/out", "so"] + SC_OFF_OK + SC_ALLOWED, locks={"seccomp": "off"}))
    got = results(d, "so")
    check("seccomp: off: started", r == (0, "done", "-"), r)
    check("seccomp: off: kcmp, personality(ADDR_NO_RANDOMIZE), process_vm_readv on itself work (the kernel allows them)",
          all(got.get(c) == "ok" for c in SC_OFF_OK + SC_ALLOWED), got)
    check("seccomp: off: locks say seccomp: off", "\nseccomp: off\n" in d.fact("so", "locks"), d.fact("so", "locks"))
    check("seccomp: off: no filter added", seccomp_filters(d.hostpid("so"))[1] == mine, seccomp_filters(d.hostpid("so")))

    # 別的架構與 x32：整個行程被 SIGSYS 殺掉
    for kind in ("x32", "i386"):
        n = "a" + kind
        r = d.ctl("start " + config(d.dir, n, ["arch", "/out", n, kind]))
        dead = wait_for(lambda: d.fact(n, "state") == "dead\n", 5)
        check("seccomp: a %s syscall kills the process with SIGSYS" % kind, r == (0, "done", "-") and dead and
              d.fact(n, "exit") == "signal 31 SIGSYS\n" and os.path.exists(os.path.join(d.dir, n + ".before")) and
              not os.path.exists(os.path.join(d.dir, n + ".txt")), (r, d.fact(n, "exit")))
        n = "o" + kind
        r = d.ctl("start " + config(d.dir, n, ["arch", "/out", n, kind], locks={"seccomp": "off"}))
        got = wait_for(lambda: os.path.exists(os.path.join(d.dir, n + ".txt")) and read(os.path.join(d.dir, n + ".txt")), 5)
        check("seccomp: off: the same %s syscall goes through (this kernel has it)" % kind, (got or "").startswith("survived"),
              (got, d.fact(n, "exit")))

    # 使用者的名單：default allow＋deny
    lst = write_json(os.path.join(d.dir, "deny.json"), {"default": "allow", "deny": ["getppid", "kcmp", "getppid"]})
    r = d.ctl("start " + config(d.dir, "ua", ["sys", "/out", "ua", "getppid", "kcmp", "getpid", "personality_aslr"], locks={"seccomp": lst}))
    got = results(d, "ua")
    check("seccomp: own list (default allow): started", r == (0, "done", "-"), r)
    check("seccomp: own list (default allow): getppid and kcmp EPERM, getpid and personality(ADDR_NO_RANDOMIZE) ok (no built-in list)",
          got.get("getppid") == "err EPERM" and got.get("kcmp") == "err EPERM" and got.get("getpid") == "ok" and
          got.get("personality_aslr") == "ok", got)
    check("seccomp: own list (default allow): locks line (duplicates counted once)",
          "\nseccomp: %s (default allow, 2 denied with EPERM; other arch and x32 calls kill the process)\n" % lst in d.fact("ua", "locks"),
          d.fact("ua", "locks"))
    # default deny＋allow：全部名字減掉 getppid
    names = [n for n in x86_64_names() if n != "getppid"]
    lst = write_json(os.path.join(d.dir, "allow.json"), {"default": "deny", "allow": names})
    r = d.ctl("start " + config(d.dir, "ud", ["sys", "/out", "ud", "getppid", "getpid", "kcmp"], locks={"seccomp": lst}))
    got = results(d, "ud")
    check("seccomp: own list (default deny, every name but getppid): started", len(names) > 300 and r == (0, "done", "-"), (len(names), r))
    check("seccomp: own list (default deny): getppid EPERM, getpid and kcmp ok", got.get("getppid") == "err EPERM" and
          got.get("getpid") == "ok" and got.get("kcmp") == "ok", got)
    check("seccomp: own list (default deny): locks line", "\nseccomp: %s (default deny, %d allowed, the rest EPERM;" % (lst, len(names))
          in d.fact("ud", "locks"), d.fact("ud", "locks"))
    lst = write_json(os.path.join(d.dir, "tiny.json"), {"default": "deny", "allow": ["read", "write"]})
    r = d.ctl("start " + config(d.dir, "ut", ["sleep"], locks={"seccomp": lst}))
    check("seccomp: own list (default deny) without execve: start fails EIO, exec: Operation not permitted",
          r[0] == errno.EIO and r[1] == "failed" and "exec" in (r[2] or "") and "Operation not permitted" in (r[2] or "") and
          not os.path.exists(d.root + "/procs/ut"), r)

    # 寫錯的
    bad = [("unknown syscall name", {"default": "allow", "deny": ["ptrace", "nosuchcall"]}, "unknown syscall name \"nosuchcall\""),
           ("list key does not match default", {"default": "allow", "allow": ["ptrace"]}, "unknown key \"allow\""),
           ("no default", {"deny": ["ptrace"]}, "\"default\""),
           ("default not allow/deny", {"default": "kill", "deny": []}, "\"default\""),
           ("item not a string", {"default": "allow", "deny": [101]}, "names"),
           ("top level not an object", ["ptrace"], "object"),
           ("not json", "{nope", "not json")]
    for i, (what, body, want) in enumerate(bad):
        lst = write_json(os.path.join(d.dir, "bad%d.json" % i), body if isinstance(body, str) else json.dumps(body))
        r = d.ctl("start " + config(d.dir, "ub%d" % i, ["sleep"], locks={"seccomp": lst}))
        check("seccomp: own list %s -> EIO, failed ConfigBad, no procs/ folder" % what, r[0] == errno.EIO and r[1] == "failed" and
              (r[2] or "").startswith("ConfigBad locks.seccomp list") and want in (r[2] or "") and
              not os.path.exists(d.root + "/procs/ub%d" % i), r)
    for i, v in enumerate([5, "relative.json", "/nonexistent/list.json", "/a/../b.json", True]):
        r = d.ctl("start " + config(d.dir, "uv%d" % i, ["sleep"], locks={"seccomp": v}))
        check("seccomp: \"seccomp\": %r -> EIO, failed ConfigBad" % (v,), r[0] == errno.EIO and r[1] == "failed" and
              (r[2] or "").startswith("ConfigBad") and "seccomp" in (r[2] or ""), r)
    d.stop()

    # init：寫錯的名單起不來（退出碼 2）；init 也能 off、也能用自己的名單
    lst = write_json(os.path.join(TMP, "seccomp-i", "bad.json"), {"default": "allow", "deny": ["nosuchcall"]})
    d = Daemon("seccomp-i", init_extra={"locks": {"seccomp": lst}})
    rc = d.stop() if d.pid else d.p.wait(10)
    check("seccomp: init with an unknown syscall name in its list -> daemon exits 2 and says why",
          d.pid is None and rc == 2 and "unknown syscall name \"nosuchcall\"" in d.err(), (rc, d.err()[-300:]))
    d = Daemon("seccomp-ioff", init_extra={"locks": {"seccomp": "off"}})
    check("seccomp: init with \"seccomp\": \"off\" runs with no filter", d.pid and started(d, "main") and
          "\nseccomp: off\n" in d.fact("main", "locks") and seccomp_filters(d.hostpid("main"))[1] == mine, d.err()[-300:])
    d.stop()
    lst = write_json(os.path.join(TMP, "seccomp-ilist", "deny.json"), {"default": "allow", "deny": ["kcmp"]})
    d = Daemon("seccomp-ilist", ["isys", "/out", "kcmp", "personality_aslr"], init_extra={"locks": {"seccomp": lst}})
    got = results(d, "isys") if d.pid else {}
    check("seccomp: init with its own list: kcmp EPERM, personality(ADDR_NO_RANDOMIZE) ok, still reads $AOS_DAEMON",
          got.get("kcmp") == "err EPERM" and got.get("personality_aslr") == "ok" and init_file(d).startswith("ok pid_ns: 1"), got)
    d.stop()

    # 建 namespace、mount 不擋（使用者 11-26 定，為了在 proc 裡再起 daemon）：在 init（沒有 Landlock）裡試
    d = Daemon("seccomp-ns", ["insmount", "/out", "0 0 1"])
    got = results(d, "insmount") if d.pid else {}
    check("seccomp: built-in list allows unshare of user, mount, pid, net, uts, ipc, cgroup namespaces (init)",
          got.get("unshare") == "ok", got)
    check("seccomp: ... and mount, umount2, setns inside its own user namespace", got.get("mount") == "ok" and
          got.get("umount") == "ok" and got.get("setns") == "ok", got)
    check("seccomp: ... (kernel, not seccomp: uid 0 cannot map itself into a new userns without CAP_SETFCAP -> uid_map EPERM)",
          got.get("uid_map") == "err EPERM", got)
    d.stop()


# ---------------------------------------------------------------- nest

def our_bin_pids():
    """exe 是我們這份 build/bin/aos-daemon 的行程（比 dev＋inode：天空裡的行程 readlink 看到的是天空裡的路徑，例 /inner/aos-daemon）。"""
    st = os.stat(BIN)
    out = []
    for p in os.listdir("/proc"):
        if p.isdigit():
            try:
                e = os.stat("/proc/%s/exe" % p)
            except OSError:
                continue
            if (e.st_dev, e.st_ino) == (st.st_dev, st.st_ino):
                out.append(int(p))
    return out


def t_nest():
    """疊 daemon：proc 裡再跑一份 build/bin/aos-daemon。照預設的鎖起不來，這裡驗量到的界線（README「疊 daemon」）。"""
    sky = [bind("/usr", "/usr"), bind("/etc", "/etc"), symlink("usr/bin", "/bin"), symlink("usr/lib", "/lib"),
           symlink("usr/lib64", "/lib64"), ent("dev", "/dev"), ent("proc", "/proc"), ent("tmpfs", "/tmp"),
           bind("/toys", "/toys"), bind("/out", "/out", True)]
    d = Daemon("nest")
    if not check("nest: outer daemon up", d.pid and started(d, "main"), d.err()):
        return
    # 裡面那份 daemon 的設定（路徑是 proc 天空裡看到的）
    write_json(os.path.join(d.dir, "inner.json"), {"init": {"name": "iinit", "argv": ["/usr/bin/python3", "/toys/toys.py", "init", "/out"],
                                                            "ns": sky}, "cgroup": "off", "subuid": "off"})
    inner_ns = base_ns(d.dir) + [bind(os.path.dirname(BIN), "/inner")]

    def inner(name, **extra):
        r = d.ctl("start " + config(d.dir, name, [], ns=inner_ns, argv=["/inner/aos-daemon", "/out/inner.json"],
                                    stderr=os.path.join(d.dir, name + ".err"), **extra))
        dead = wait_for(lambda: d.fact(name, "state") == "dead\n", 8)
        return r, dead and d.fact(name, "exit"), read(os.path.join(d.dir, name + ".err"))

    r, ex, err = inner("n0")
    check("nest: proc with default locks (uid 0) runs the inner aos-daemon: it exits 2, could not write the uid/gid maps",
          r == (0, "done", "-") and ex == "code 2\n" and "could not write the uid/gid maps" in err, (r, ex, err))
    r, ex, err = inner("n1", uid=1)
    check("nest: same as uid 1 (subuid): maps are fine, then Landlock refuses mounts: make mounts private: Operation not permitted",
          r == (0, "done", "-") and ex == "code 2\n" and "make mounts private: Operation not permitted" in err, (r, ex, err))
    r, ex, err = inner("n2", uid=1, locks={"seccomp": "off"})
    check("nest: ... seccomp off changes nothing (it is Landlock, not seccomp)",
          ex == "code 2\n" and "make mounts private: Operation not permitted" in err, (r, ex, err))
    # 拆開量：開 namespace 都行；uid 0 對照不了自己；Landlock 擋 mount
    os.chmod(d.dir, 0o777)   # uid 1 的 proc（外面是 subuid）要能在 /out 寫結果
    for name, uid, line, sc in (("m0", 0, "0 0 1", None), ("m1", 1, "0 1 1", None), ("m1off", 1, "0 1 1", "off")):
        extra = {"uid": uid}
        if sc:
            extra["locks"] = {"seccomp": sc}
        d.ctl("start " + config(d.dir, name, ["nsmount", "/out", name, line], **extra))
        got = results(d, name)
        want_map = "err EPERM" if uid == 0 else "ok"
        check("nest: proc uid %d%s: unshare ok, uid_map %r %s, mount EPERM (Landlock)" % (uid, " seccomp off" if sc else "", line, want_map),
              got.get("unshare") == "ok" and got.get("uid_map") == want_map and got.get("mount") == "err EPERM", got)
    hp = [d.hostpid(n) for n in ("main", "m0", "m1")]
    check("nest: SIGTERM -> outer exits 0", d.stop() == 0)
    check("nest: ... nothing of it is left (by exe dev+inode, nested ones too)",
          wait_for(lambda: all(gone(p) for p in hp) and not our_bin_pids(), 3), our_bin_pids())

    # init（沒有 Landlock）跑裡面那份：uid 0 一樣對照不了自己
    d = Daemon("nest-init", None, "--on-init-exit", "exit", init_extra={
        "argv": ["/inner/aos-daemon", "/out/inner.json"], "ns": base_ns(os.path.join(TMP, "nest-init")) + [bind(os.path.dirname(BIN), "/inner")],
        "stderr": os.path.join(TMP, "nest-init", "init.err")})
    write_json(os.path.join(d.dir, "inner.json"), {"init": {"name": "iinit", "argv": ["/usr/bin/true"], "ns": sky}, "cgroup": "off", "subuid": "off"})
    try:
        rc = d.p.wait(10)
    except subprocess.TimeoutExpired:
        rc = d.stop()
    ierr = read(os.path.join(d.dir, "init.err")) if os.path.exists(os.path.join(d.dir, "init.err")) else ""
    check("nest: as init (no Landlock, must be uid 0): the inner daemon exits 2 (could not write the uid/gid maps), outer exits 2",
          rc == 2 and "could not write the uid/gid maps" in ierr, (rc, ierr, d.err()[-300:]))


# ---------------------------------------------------------------- cgpath

def t_cgpath():
    """--cgroup PATH：用一個已經交給自己的 cgroup 夾（這裡用 systemd-run 開一個 Delegate=yes 的 scope，把 scope 的夾給它）。"""
    dd = os.path.join(TMP, "cgpath")
    os.makedirs(dd, exist_ok=True)
    sh = os.path.join(dd, "run.sh")
    with open(sh, "w") as f:
        f.write('exec "$1" --cgroup "/sys/fs/cgroup$(sed -n "s/^0:://p" /proc/self/cgroup)" --init "$2"\n')
    if not check("cgpath: systemd-run is there", shutil.which("systemd-run")):
        return
    d = Daemon("cgpath", cmd=lambda k: ["sh", "-c", 'exec systemd-run --user --scope --quiet --collect -p Delegate=yes '
                                         '--unit=aos-daemon-$$ -- /bin/sh "$0" "$1" "$2"', sh, BIN, k])
    if not check("cgpath: daemon up with --cgroup <a delegated scope folder>", d.pid and started(d, "main"), d.err()):
        return
    scope = "aos-daemon-%d.scope" % d.p.pid
    cg = d.status().get("cgroup", "")
    check("cgpath: status cgroup is that folder", cg.startswith("/sys/fs/cgroup/") and cg.endswith("/" + scope), cg)
    check("cgpath: the daemon sits in <folder>/daemon", read("/proc/%d/cgroup" % d.pid).strip().endswith("/" + scope + "/daemon"),
          read("/proc/%d/cgroup" % d.pid))
    r = d.ctl("start " + config(d.dir, "w", ["sleep"], locks={"cgroup": {"pids.max": "33"}}))
    check("cgpath: a proc with a cgroup limit starts", r == (0, "done", "-"), r)
    check("cgpath: ... its limit is in its folder under the given one", d.fact("w", "cgroup/pids.max") == "33\n" and
          ("/%s/p-w-" % scope) in read("/proc/%d/cgroup" % d.hostpid("w")), read("/proc/%d/cgroup" % d.hostpid("w")))
    check("cgpath: SIGTERM -> exit 0", d.stop() == 0)
    check("cgpath: ... the scope folder is gone afterwards", wait_for(lambda: not os.path.exists(cg), 5), cg)
    for what, args, want in (("--cgroup /nonexistent/x", ["--cgroup", "/nonexistent/x"], "--cgroup /nonexistent/x"),
                             ("--cgroup on a folder that is not a cgroup", ["--cgroup", dd], "not a cgroup v2 folder"),
                             ("--cgroup relative/x", ["--cgroup", "relative/x"], "--cgroup is auto, off or an absolute path")):
        p = subprocess.run([BIN, "--init", os.path.join(dd, "main.json"), *args], capture_output=True, text=True, timeout=20)
        check("cgpath: %s -> exit 2 and says why" % what, p.returncode == 2 and want in p.stderr, (p.returncode, p.stderr))
    for v in ("relative/x", 5):
        dj = write_json(os.path.join(dd, "dc.json"), {"init": "main.json", "cgroup": v})
        p = subprocess.run([BIN, dj], capture_output=True, text=True, timeout=20)
        check("cgpath: daemon.json \"cgroup\": %r -> exit 2" % (v,), p.returncode == 2 and "absolute path to a delegated cgroup folder" in p.stderr,
              (p.returncode, p.stderr))
    dj = write_json(os.path.join(dd, "dc.json"), {"init": "main.json", "cgroup": "/nonexistent/y"})
    p = subprocess.run([BIN, dj], capture_output=True, text=True, timeout=20)
    check("cgpath: daemon.json \"cgroup\": \"/nonexistent/y\" -> exit 2", p.returncode == 2 and "/nonexistent/y" in p.stderr,
          (p.returncode, p.stderr))


# ---------------------------------------------------------------- sigsrc（停止訊號只收外面與 init 送的，使用者 11-26 定）

ISO = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$")


def ns_pid(d, name):
    return int(re.search(r"ns: (\d+)", d.fact(name, "pid")).group(1))


def t_sigsrc():
    d = Daemon("sigsrc")
    if not check("sigsrc: daemon up", d.pid and init_up(d), d.err()):
        return
    abi = int(d.status().get("landlock_abi", "0"))
    ip = ns_pid(d, "main")
    sigs = ["sig:1:15", "sig:1:1", "sig:1:2"]
    d.ctl("start " + config(d.dir, "s", ["probe", "/out", "s"] + sigs))
    got = results(d, "s")
    sp = ns_pid(d, "s")
    want = "ok" if abi < 6 else "err EPERM"
    check("sigsrc: a sky proc sends SIGTERM, SIGHUP, SIGINT to the daemon (PID 1): %s (Landlock ABI %d)" % (got.get(sigs[0]), abi),
          all(got.get(k) == want for k in sigs), got)
    lines = ["ignored %s from pid %d (s) in the daemon's PID namespace" % (n, sp) for n in ("SIGTERM", "SIGHUP", "SIGINT")]
    if abi < 6:
        wait_for(lambda: all(l in d.err() for l in lines), 3)
    else:
        time.sleep(0.5)
    check("sigsrc: ... the daemon does not stop: still up, status reads", d.p.poll() is None and d.status().get("pid_ns") == "1")
    if abi < 6:
        check("sigsrc: ... and logs one line each (ignored SIGTERM/SIGHUP/SIGINT from pid N (s) …)", all(l in d.err() for l in lines),
              d.err()[-800:])
        # 一般訊號同號的還沒讀走時第二個會被併掉：一隻一個、等到記下來再送下一個
        for name, fake, want_line in (("f0", 0, "ignored SIGTERM from outside the daemon's PID namespace with si_code -1"),
                                      ("fi", ip, "ignored SIGTERM from pid %d (main) in the daemon's PID namespace with si_code -1" % ip)):
            d.ctl("start " + config(d.dir, name, ["probe", "/out", name, "forge:1:15:%d" % fake]))
            g = results(d, name)
            seen = wait_for(lambda: want_line in d.err(), 3)
            check("sigsrc: a forged sender (rt_sigqueueinfo, si_code SI_QUEUE, si_pid %s) is ignored" % ("0" if not fake else "= init's"),
                  g.get("forge:1:15:%d" % fake) == "ok" and seen and d.p.poll() is None, (g, d.err()[-600:]))
    r = d.ctl("start " + config(d.dir, "s2", ["sleep"]))
    check("sigsrc: ctl still works afterwards", r == (0, "done", "-") and started(d, "s2"), r)
    check("sigsrc: locks of a uid-0 proc %s 'signals: can signal init and other uid-0 procs' (ABI %d)" % ("have" if abi < 6 else "lack", abi),
          ("signals: can signal init and other uid-0 procs" in d.fact("s", "locks")) == (abi < 6), d.fact("s", "locks"))
    check("sigsrc: init's locks have no signals line", "signals:" not in d.fact("main", "locks"), d.fact("main", "locks"))
    if d.status().get("subuid", "none") != "none":
        d.ctl("start " + config(d.dir, "u1", ["sleep"], uid=1))
        check("sigsrc: a subuid proc's locks have no signals line", started(d, "u1") and "signals:" not in d.fact("u1", "locks"),
              d.fact("u1", "locks"))
    d.ask("sig:1:15")   # init 送；daemon 收尾時 init 可能來不及寫答案，不看答案
    try:
        rc = d.p.wait(10)
    except subprocess.TimeoutExpired:
        rc = None
    check("sigsrc: init sends SIGTERM to the daemon -> it stops, exit 0", rc == 0 and "exiting (got SIGTERM" in d.err(), (rc, d.err()[-400:]))
    check("sigsrc: ... that one was not ignored (only the three from s are)", d.err().count("ignored SIGTERM") == (3 if abi < 6 else 0),
          d.err()[-600:])

    d = Daemon("sigsrc-out")
    init_up(d)
    check("sigsrc: SIGTERM from outside (through the launcher) -> exit 0, nothing ignored", d.stop() == 0 and "ignored" not in d.err(),
          d.err()[-300:])
    d = Daemon("sigsrc-out2")
    init_up(d)
    os.kill(d.pid, signal.SIGHUP)
    try:
        rc = d.p.wait(10)
    except subprocess.TimeoutExpired:
        rc = None
    check("sigsrc: SIGHUP sent from outside straight to the daemon's PID -> exit 0", rc == 0 and "exiting (got SIGHUP" in d.err(),
          (rc, d.err()[-300:]))


# ---------------------------------------------------------------- ipath（普通 proc 經 init 的 /proc/<PID>/root 進不去 daemon 的目錄）

def t_ipath():
    for variant, extra, label in (("", None, "init without Landlock"),
                                  ("-landlock", {"locks": {"landlock": True}}, "init with locks.landlock true")):
        d = Daemon("ipath" + variant, None, init_extra=extra)
        if not check("ipath: (%s) daemon up" % label, d.pid and started(d, "main"), d.err()):
            continue
        if int(d.status().get("landlock_abi", "0")) < 1:
            check("ipath: (skip) this Linux has no Landlock", True)
            d.stop()
            continue
        i = ns_pid(d, "main")
        victim = config(d.dir, "victim", ["sleep"])
        reads = ["/proc/%d/root/aos/status" % i, "/proc/%d/cwd/aos/status" % i, "/proc/%d/root/aos/procs" % i,
                 "/proc/%d/root" % i, "/proc/%d/cwd" % i]
        writes = ["put:/proc/%d/root/aos/ctl=start %s" % (i, victim), "put:/proc/%d/cwd/aos/ctl=start %s" % (i, victim)]
        d.ctl("start " + config(d.dir, "q", ["probe", "/out", "q"] + reads + writes))
        results(d, "q")
        got = {}   # 寫的那幾個的路徑裡有空白，照整個前綴找
        for line in read(os.path.join(d.dir, "q.txt")).splitlines():
            for p in reads + writes:
                if line.startswith(p + " "):
                    got[p] = line[len(p) + 1:]
        check("ipath: (%s) the probe is uid 0 like init" % label, d.fact("q", "uid").startswith("ns: 0\n"), d.fact("q", "uid"))
        names = ["root/aos/status", "cwd/aos/status", "root/aos/procs", "root", "cwd"]
        for p, n in zip(reads, names):
            check("ipath: (%s) uid-0 proc reading /proc/<init>/%s: %s" % (label, n, got.get(p)), got.get(p, "").startswith("err"), got)
        for p, n in zip(writes, ["root/aos/ctl", "cwd/aos/ctl"]):
            check("ipath: (%s) uid-0 proc writing /proc/<init>/%s: %s" % (label, n, got.get(p)), got.get(p, "").startswith("err"), got)
        check("ipath: (%s) ... nothing was started through it" % label, not os.path.lexists(d.root + "/procs/victim") and
              "victim" not in d.status().get("aos_ctl_cmd", ""), d.status().get("aos_ctl_cmd"))
        d.stop()


# ---------------------------------------------------------------- stuck（bind 來源卡住時 daemon 不跟著卡）

def stuck_fuse(dd):
    """起 toys.py stuckfuse（在外面跑的故意不回答的 FUSE）；回 (Popen, 掛載點, 狀態夾, 說明)。Popen 是 None 就是起不來。"""
    mnt, st = os.path.join(dd, "mnt"), os.path.join(dd, "st")
    os.makedirs(mnt, exist_ok=True)
    os.makedirs(st, exist_ok=True)
    if not shutil.which("fusermount3") or not os.path.exists("/dev/fuse"):
        return None, mnt, st, "no fusermount3 or /dev/fuse"
    p = subprocess.Popen([sys.executable, os.path.join(TOYS, "toys.py"), "stuckfuse", mnt, st], stdout=subprocess.DEVNULL,
                         stderr=open(os.path.join(dd, "fuse.err"), "w"))
    wait_for(lambda: os.path.exists(st + "/ready") or os.path.exists(st + "/failed") or p.poll() is not None, 5)
    if not os.path.exists(st + "/ready"):
        p.kill()
        p.wait(5)
        return None, mnt, st, read(os.path.join(dd, "fuse.err"))[-300:]
    return p, mnt, st, ""


def stuck_pids(st):
    return sorted(int(n[6:]) for n in os.listdir(st) if n.startswith("stuck-"))


def proc_state(pid):
    try:
        return re.search(r"State:\s+(\S)", read("/proc/%d/status" % pid)).group(1)
    except OSError:
        return None


def t_stuck():
    dd = os.path.join(TMP, "stuck-fuse")
    fp, mnt, st, why = stuck_fuse(dd)
    if not fp:
        check("stuck: (skip) could not make a FUSE that hangs: %s" % why, True)
        return
    try:
        d = Daemon("stuck")   # FUSE 先掛好再起 daemon：daemon 握的「原本那一層」是起動那一刻的
        if not check("stuck: daemon up", d.pid and started(d, "main"), d.err()):
            return
        cg = d.status().get("cgroup", "off")
        cg_on = not cg.startswith("off")
        t0 = time.monotonic()
        r = d.ctl("start " + config(d.dir, "sb", ["sleep"], ns=base_ns(d.dir) + [bind(mnt + "/stuck", "/x")]), wait=30)
        el = time.monotonic() - t0
        check("stuck: start whose bind source hangs: write error EIO after the 10 s timeout (%.1f s), Timeout building the ns" % el,
              r[0] == errno.EIO and r[1] == "failed" and (r[2] or "").startswith("Timeout building the ns") and 9.5 <= el < 13, (r, el))
        sp = stuck_pids(st)
        check("stuck: ... the FUSE got the lookup and does not answer it", len(sp) == 1, sp)
        check("stuck: ... the child is still stuck in the kernel after SIGKILL (state D), not reaped",
              sp and proc_state(sp[0]) == "D", sp and proc_state(sp[0]))
        t0 = time.monotonic()
        s = d.status()
        r = d.ctl("start " + config(d.dir, "ok1", ["sleep"]))
        check("stuck: the daemon is not stuck: status reads, another start is done at once (%.2f s)" % (time.monotonic() - t0),
              s.get("pid_ns") == "1" and r == (0, "done", "-") and started(d, "ok1") and time.monotonic() - t0 < 3, r)
        check("stuck: the failed one is not on the table", not os.path.lexists(d.root + "/procs/sb"))
        check("stuck: the daemon says it did not wait for it", "did not exit 0.5 s after SIGKILL" in d.err(), d.err()[-500:])
        if cg_on:
            check("stuck: ... it was stuck before joining its cgroup, so the cgroup folder is removed at once",
                  not [n for n in os.listdir(cg) if n.startswith("p-sb-")] and "cgroup p-sb-" not in d.err(), d.err()[-400:])
        # 卡在 exec（程式在不回答的 FUSE 上）：已經進了自己的 cgroup，夾刪不掉，記下來之後再刪
        t0 = time.monotonic()
        r = d.ctl("start " + config(d.dir, "sx", [], ns=base_ns(d.dir) + [bind(mnt, "/fz")], argv=["/fz/stuck-exec"]), wait=30)
        el = time.monotonic() - t0
        check("stuck: start whose program is on the hanging FUSE: EIO after the 10 s exec timeout (%.1f s), Timeout exec" % el,
              r[0] == errno.EIO and r[1] == "failed" and (r[2] or "").startswith("Timeout exec") and 9.5 <= el < 13, (r, el))
        sp = stuck_pids(st)
        check("stuck: ... that child is stuck in the kernel too (state D)", len(sp) == 2 and all(proc_state(p) == "D" for p in sp),
              [(p, proc_state(p)) for p in sp])
        left = []
        if cg_on:
            left = [n for n in os.listdir(cg) if n.startswith("p-sx-")]
            check("stuck: ... its cgroup folder could not be removed yet and is kept for later", len(left) == 1 and
                  "cgroup %s not removed yet" % (left or ["?"])[0] in d.err(), (left, d.err()[-400:]))
        t0 = time.monotonic()
        r = d.ctl("mount ok1 %s/stuck-mount /y" % mnt, wait=30)
        el = time.monotonic() - t0
        check("stuck: ctl mount from the hanging FUSE: write error EIO after 10 s (%.1f s), MountFailed Timeout" % el,
              r[0] == errno.EIO and r[1] == "failed" and (r[2] or "").startswith("MountFailed Timeout mount took more than 10 s") and
              9.5 <= el < 13, (r, el))
        sp = stuck_pids(st)
        check("stuck: ... its helper is stuck too (state D)", len(sp) == 3 and all(proc_state(p) == "D" for p in sp),
              [(p, proc_state(p)) for p in sp])
        r = d.ctl("kill ok1 TERM")
        check("stuck: ... and ctl still works", r == (0, "done", "-"), r)
        fp.kill()   # FUSE 的 fd 關了：核心中止連線，卡住的請求回錯，兩隻帶著 SIGKILL 走掉
        fp.wait(5)
        check("stuck: once the FUSE goes away the stuck ones exit and the main loop reaps them (no zombies)",
              wait_for(lambda: all(not os.path.exists("/proc/%d" % p) for p in sp), 5), [(p, proc_state(p)) for p in sp])
        if cg_on:
            check("stuck: ... and the kept cgroup folder is removed then",
                  wait_for(lambda: not any(os.path.exists(os.path.join(cg, n)) for n in left), 5) and "removed cgroup p-sx-" in d.err(),
                  d.err()[-400:])
        check("stuck: the daemon still stops with SIGTERM (exit 0)", d.stop() == 0)
    finally:
        if fp.poll() is None:
            fp.kill()
            fp.wait(5)
        subprocess.run(["fusermount3", "-u", "-z", mnt], stderr=subprocess.DEVNULL)


# ---------------------------------------------------------------- nsby（ns.json 每筆的 by、at）

def t_nsby():
    d = Daemon("nsby")
    if not check("nsby: daemon up", d.pid and started(d, "main"), d.err()):
        return
    d.ctl("start " + config(d.dir, "w", ["sleep"]))
    started(d, "w")
    js = json.loads(d.fact("w", "ns.json"))
    check("nsby: every entry has by and at", all("by" in j and "at" in j for j in js), js)
    check("nsby: at is a UTC time (YYYY-MM-DDTHH:MM:SS.mmmZ)", all(ISO.match(j.get("at", "")) for j in js), [j.get("at") for j in js])
    check("nsby: rows from the config are by start, forced-in submounts by locked",
          all(j.get("by") == ("locked" if j.get("locked") else "start") for j in js), js)
    if any(j.get("locked") for j in js):
        check("nsby: (WSL) the locked rows under /usr are by locked", all(j["by"] == "locked" for j in js if j.get("locked")))
    cg_on = not d.status().get("cgroup", "off").startswith("off")
    nj = json.loads(d.fact("main", "ns.json"))
    want = {"/aos": "daemon", "/cgroup": "daemon"} if cg_on else {"/aos": "daemon"}
    check("nsby: init's /aos%s rows are by daemon" % (" and /cgroup" if cg_on else ""),
          {j["dst"]: j["by"] for j in nj if j["type"] in ("aos", "cgroup")} == want, nj)
    check("nsby: init's other rows are by start or locked", all(j["by"] in ("start", "locked") for j in nj if j["type"] not in ("aos", "cgroup")))
    time.sleep(0.05)
    src = os.path.join(d.dir, "live")
    os.makedirs(src, exist_ok=True)
    r = d.ctl("mount w %s /live" % src)
    js2 = json.loads(d.fact("w", "ns.json"))
    live = [j for j in js2 if j["dst"] == "/live"]
    check("nsby: a ctl mount is by mount with its own at", r == (0, "done", "-") and len(live) == 1 and live[0]["by"] == "mount" and
          ISO.match(live[0]["at"]) and live[0]["at"] != js[0]["at"], (r, live, js[0]))
    check("nsby: the start rows keep their by and at after the remeasure", [j for j in js2 if j["dst"] != "/live"] == js)
    check("nsby: the text ns has no by/at", all(len(l.split()) in (4, 5) for l in d.fact("w", "ns").splitlines()) and
          " start" not in d.fact("w", "ns") and " mount" not in d.fact("w", "ns"), d.fact("w", "ns"))
    d.stop()


# ---------------------------------------------------------------- overlay（ns 的 overlay，唯讀）

def t_overlay():
    d = Daemon("overlay")
    if not check("overlay: daemon up", d.pid and started(d, "main"), d.err()):
        return
    top, bot = os.path.join(d.dir, "top"), os.path.join(d.dir, "bot")
    for p, files in ((top, {"common": "TOP", "t": "t"}), (bot, {"common": "BOT", "b": "b"})):
        os.makedirs(p, exist_ok=True)
        for n, v in files.items():
            with open(os.path.join(p, n), "w") as f:
                f.write(v)
    ov = {"type": "overlay", "lower": [top, bot], "dst": "/ov"}
    r = d.ctl("start " + config(d.dir, "ov", ["probe", "/out", "ov", "/ov", "/ov/common", "/ov/t", "/ov/b"], ns=base_ns(d.dir) + [ov]))
    check("overlay: start with an overlay entry -> done", r == (0, "done", "-"), r)
    got = results(d, "ov")
    check("overlay: both layers show in one folder, the first lower on top",
          got == {"/ov": "ok b common t", "/ov/common": "ok TOP", "/ov/t": "ok t", "/ov/b": "ok b"}, got)
    d.ctl("start " + config(d.dir, "ovw", ["write", "/out", "ovw", "/ov/x", "/ov/common"], ns=base_ns(d.dir) + [ov]))
    got = results(d, "ovw")
    check("overlay: it is read-only (new file and existing file: EROFS)", got == {"/ov/x": "err EROFS", "/ov/common": "err EROFS"}, got)
    table = [l.split() for l in d.fact("ov", "ns").splitlines()]
    check("overlay: ns line 'overlay <top>:<bot> /ov ro'", ["overlay", top + ":" + bot, "/ov", "ro"] in table, table)
    row = [j for j in json.loads(d.fact("ov", "ns.json")) if j["dst"] == "/ov"]
    check("overlay: ns.json row has type overlay, lower as an array, rw false, by start",
          len(row) == 1 and row[0]["type"] == "overlay" and row[0]["lower"] == [top, bot] and row[0]["rw"] is False and
          row[0]["by"] == "start" and "src" not in row[0], row)
    check("overlay: ns_check ok", d.fact("ov", "ns_check") == "ok\n", d.fact("ov", "ns_check"))
    mi = [l.split() for l in read("/proc/%d/mountinfo" % d.hostpid("ov")).splitlines()]
    m = [l for l in mi if l[4] == "/ov"]
    check("overlay: mountinfo: /ov is an overlay, ro", m and m[0][m[0].index("-") + 1] == "overlay" and m[0][5].startswith("ro"), m)
    cases = [("one lower", {"type": "overlay", "lower": [top], "dst": "/z"}, "at least 2"),
             ("lower not an array", {"type": "overlay", "lower": top, "dst": "/z"}, "at least 2"),
             ("relative lower", {"type": "overlay", "lower": [top, "rel/x"], "dst": "/z"}, "absolute"),
             ("missing lower", {"type": "overlay", "dst": "/z"}, "lower"),
             ("rw on overlay", {"type": "overlay", "lower": [top, bot], "dst": "/z", "rw": True}, "unknown key"),
             ("src on overlay", {"type": "overlay", "lower": [top, bot], "dst": "/z", "src": top}, "unknown key")]
    for k, (what, e, word) in enumerate(cases):
        r = d.ctl("start " + config(d.dir, "ob%d" % k, ["sleep"], ns=base_ns(d.dir) + [e]))
        check("overlay: %s -> EIO, ConfigBad" % what, r[0] == errno.EIO and "ConfigBad" in (r[2] or "") and word in (r[2] or ""), r)
    r = d.ctl("start " + config(d.dir, "onx", ["sleep"], ns=base_ns(d.dir) + [{"type": "overlay", "lower": [top, "/nonexistent/x"], "dst": "/z"}]))
    check("overlay: a lower that does not exist -> EIO, StartFailed (overlay)", r[0] == errno.EIO and
          (r[2] or "").startswith("StartFailed") and "overlay" in (r[2] or ""), r)
    d.stop()


# ---------------------------------------------------------------- merge（合併目錄 B：留空 tmpfs，跑的時候一個一個檔掛進去）

def t_merge():
    dd = os.path.join(TMP, "merge")
    d = Daemon("merge", None, init_extra={"ns": base_ns(dd) + [ent("tmpfs", "/merged")]})
    if not check("merge: daemon up (init has an empty tmpfs at /merged)", d.pid and started(d, "main"), d.err()):
        return
    check("merge: /merged starts empty", d.ask("/merged") == "ok", d.ask("/merged"))
    files = {}
    for sub, name, val in (("one", "tool-a", "A"), ("two", "tool-b", "B")):
        os.makedirs(os.path.join(dd, sub), exist_ok=True)
        files[name] = os.path.join(dd, sub, name)
        with open(files[name], "w") as f:
            f.write(val)
    rs = [d.ctl("mount main %s /merged/%s" % (files[n], n)) for n in ("tool-a", "tool-b")]
    check("merge: ctl mount of two single files from two host folders -> done", rs == [(0, "done", "-")] * 2, rs)
    check("merge: init sees both in one folder", d.ask("/merged") == "ok tool-a tool-b", d.ask("/merged"))
    check("merge: ... with their contents", d.ask("/merged/tool-a") == "ok A" and d.ask("/merged/tool-b") == "ok B")
    table = [l.split() for l in d.fact("main", "ns").splitlines()]
    check("merge: ns has one bind line per file", all(["bind", files[n], "/merged/" + n, "ro"] in table for n in files), table)
    nj = [j for j in json.loads(d.fact("main", "ns.json")) if j["dst"].startswith("/merged/")]
    check("merge: ns.json rows are by mount", len(nj) == 2 and all(j["by"] == "mount" for j in nj), nj)
    check("merge: ns_check ok", d.fact("main", "ns_check") == "ok\n", d.fact("main", "ns_check"))
    r = d.ctl("umount main /merged/tool-a")
    check("merge: umount one -> done; measured: an empty mount-point file stays (%s)" % d.ask("/merged/tool-a"),
          r == (0, "done", "-") and d.ask("/merged/tool-a") == "ok" and d.ask("/merged/tool-b") == "ok B", r)
    d.stop()


# ---------------------------------------------------------------- rinit（ctl 的 restart-init，使用者 11-26 定）

def t_rinit():
    dd = os.path.join(TMP, "rinit")
    xdir = os.path.join(dd, "x")
    os.makedirs(xdir, exist_ok=True)
    d = Daemon("rinit", None, "--restart-limit", "1", "--on-restart-limit", "stay", init_extra={"ns": base_ns(dd) + [bind(xdir, "/x")]})
    if not check("rinit: daemon up (--restart-limit 1 --on-restart-limit stay)", d.pid and init_up(d), d.err()):
        return

    r = d.ctl("restart-init")
    check("rinit: init alive -> write error EINVAL, rejected InitAlive", r[0] == errno.EINVAL and r[1] == "rejected" and
          (r[2] or "").startswith("InitAlive"), r)
    r = d.ctl("restart-init now")
    check("rinit: an argument -> EINVAL ArgumentsBad", r[0] == errno.EINVAL and (r[2] or "").startswith("ArgumentsBad"), r)
    hp = d.hostpid("main")
    d.ctl("kill main KILL")
    wait_for(lambda: d.status().get("init_restarts") == "1" and started(d, "main", 0.05) and d.hostpid("main") != hp, 5)
    hp = d.hostpid("main")
    d.ctl("kill main KILL")
    gone_ = wait_for(lambda: d.status().get("init_state", "").startswith("gone"), 5)
    check("rinit: two deaths -> init gone (restart limit, stay)", gone_ and d.status().get("init_restarts") == "1", d.status())
    r = d.ctl("restart-init")
    s = d.status()
    check("rinit: restart-init while init is gone -> done; init alive again, restart counts back to 0",
          r == (0, "done", "-") and s.get("init_state") == "alive" and s.get("init_restarts") == "0" and
          s.get("init_deaths_in_window") == "0" and d.fact("main", "state") == "alive\n" and d.hostpid("main") != hp, (r, s))
    kt = wait_for(lambda: read(os.path.join(d.dir, "init-%d.txt" % ns_pid(d, "main"))), 5) or ""   # init 記的是它自己看到的 PID
    check("rinit: it is a real init: AOS_DAEMON=/aos, reads /aos/status; /aos in its ns", kt.startswith("ok pid_ns: 1") and
          "\nroot /aos\n" in kt and ["aos", "-", "/aos", "rw"] in [l.split() for l in d.fact("main", "ns").splitlines()], kt)
    check("rinit: stderr says restart-init", "restart-init: starting init main" in d.err(), d.err()[-300:])
    hp = d.hostpid("main")
    d.ctl("kill main KILL")
    check("rinit: the restart window was reset: the next death is restarted again (init_restarts 1)",
          wait_for(lambda: d.status().get("init_restarts") == "1" and started(d, "main", 0.05) and d.hostpid("main") != hp, 5), d.status())
    hp = d.hostpid("main")
    d.ctl("kill main KILL")
    wait_for(lambda: d.status().get("init_state", "").startswith("gone"), 5)
    r1 = d.ctl("forget main")
    r2 = d.ctl("restart-init")
    check("rinit: after forget of the gone init, restart-init starts it", r1 == (0, "done", "-") and r2 == (0, "done", "-") and
          started(d, "main") and d.status().get("init_state") == "alive", (r1, r2))
    # 起不來：init 天空的 bind 來源不見了
    for _ in range(2):
        hp = d.hostpid("main")
        d.ctl("kill main KILL")
        wait_for(lambda: d.status().get("init_state", "").startswith("gone") or
                 (started(d, "main", 0.05) and d.hostpid("main") != hp), 5)
    os.rmdir(xdir)
    r = d.ctl("restart-init")
    s = d.status()
    check("rinit: init that cannot start -> write error EIO, failed; init_state gone (restart-init failed …); daemon stays",
          r[0] == errno.EIO and r[1] == "failed" and "bind source" in (r[2] or "") and
          s.get("init_state", "").startswith("gone (restart-init failed") and d.p.poll() is None, (r, s.get("init_state")))
    os.makedirs(xdir)
    r = d.ctl("restart-init")
    check("rinit: fixed, restart-init again -> done", r == (0, "done", "-") and started(d, "main"), r)
    # 表上同名的是一般 proc
    for _ in range(2):
        hp = d.hostpid("main")
        d.ctl("kill main KILL")
        wait_for(lambda: d.status().get("init_state", "").startswith("gone") or
                 (started(d, "main", 0.05) and d.hostpid("main") != hp), 5)
    d.ctl("forget main")
    other = os.path.join(d.dir, "other")
    os.makedirs(other, exist_ok=True)
    d.ctl("start " + config(other, "main", ["sleep"], ns=base_ns(d.dir)))
    r = d.ctl("restart-init")
    check("rinit: a proc named main that is not init is on the table -> EINVAL ProcExists",
          r[0] == errno.EINVAL and (r[2] or "").startswith("ProcExists"), r)
    d.stop()
    dj = write_json(os.path.join(TMP, "rinit-noinit", "daemon.json"), {})
    d = Daemon("rinit-noinit", args=[dj])
    r = d.ctl("restart-init")
    check("rinit: no init in the daemon config -> EINVAL NoInit", r[0] == errno.EINVAL and (r[2] or "").startswith("NoInit"), r)
    d.stop()


# ---------------------------------------------------------------- iface（介面宣告 __meta/__interfaces，使用者 11-26 定）

def t_iface():
    d = Daemon("iface")
    if not check("iface: daemon up", d.pid and init_up(d), d.err()):
        return
    base = d.root + "/__meta/__interfaces/aos"
    check("iface: __meta/__interfaces/aos holds ctl/ and jsonpath", sorted(os.listdir(base)) == ["ctl", "jsonpath"], os.listdir(base))
    check("iface: aos/ctl is a folder with kind, path, commands", os.path.isdir(base + "/ctl") and
          sorted(os.listdir(base + "/ctl")) == ["commands", "kind", "path"])
    check("iface: aos/ctl/kind is file", read(base + "/ctl/kind") == "file\n", read(base + "/ctl/kind"))
    check("iface: aos/ctl/path is ctl, and that is the ctl next to __meta", read(base + "/ctl/path") == "ctl\n" and
          os.path.exists(os.path.join(d.root, read(base + "/ctl/path").strip())))
    cmds = read(base + "/ctl/commands").split()
    check("iface: aos/ctl/commands lists the commands, restart-init included",
          cmds == ["start", "kill", "mount", "umount", "forget", "restart-init"], cmds)
    res = [d.ctl(c) for c in cmds]
    check("iface: ... and ctl knows every one of them (no CommandUnknown)",
          all(r[0] == errno.EINVAL and not (r[2] or "").startswith("CommandUnknown") for r in res), res)
    r = d.ctl("frobnicate")
    check("iface: ... while a word not listed is CommandUnknown", (r[2] or "").startswith("CommandUnknown"), r)
    check("iface: aos/jsonpath is an empty file", os.path.isfile(base + "/jsonpath") and read(base + "/jsonpath") == "")
    modes = {p: os.stat(p).st_mode & 0o777 for p in (d.root + "/__meta", base, base + "/ctl", base + "/ctl/kind", base + "/jsonpath")}
    check("iface: read-only (folders 0555, files 0444)", list(modes.values()) == [0o555, 0o555, 0o555, 0o444, 0o444], modes)
    errs = []
    for f in (lambda: os.close(os.open(base + "/ctl/kind", os.O_WRONLY)), lambda: os.mkdir(base + "/x"),
              lambda: os.close(os.open(base + "/new", os.O_WRONLY | os.O_CREAT)), lambda: os.unlink(base + "/jsonpath")):
        try:
            f()
            errs.append("ok")
        except OSError as e:
            errs.append(errno.errorcode.get(e.errno, str(e.errno)))
    check("iface: writing, making, removing under __meta all fail (%s)" % " ".join(errs), "ok" not in errs, errs)
    d.ctl("start " + config(d.dir, "w", ["sleep"]))
    started(d, "w")
    for n in ("main", "w"):
        p = "%s/procs/%s/__meta/__interfaces/aos" % (d.root, n)
        check("iface: procs/%s/ declares aos/proc (an empty file)" % n, os.listdir(p) == ["proc"] and read(p + "/proc") == "",
              os.listdir(p))
    check("iface: init reads /aos/__meta/__interfaces/aos/ctl/kind", d.ask("/aos/__meta/__interfaces/aos/ctl/kind") == "ok file|")
    check("iface: init reads .../ctl/path and .../ctl/commands", d.ask("/aos/__meta/__interfaces/aos/ctl/path") == "ok ctl|" and
          d.ask("/aos/__meta/__interfaces/aos/ctl/commands") == "ok start kill mount umount forget restart-init|")
    check("iface: init reads .../aos/jsonpath and procs/w/__meta/__interfaces/aos/proc",
          d.ask("/aos/__meta/__interfaces/aos/jsonpath") == "ok" and d.ask("/aos/procs/w/__meta/__interfaces/aos/proc") == "ok")
    a = d.ask("put:/aos/__meta/__interfaces/aos/ctl/kind=socket")
    check("iface: init cannot change the declaration (%s)" % a, (a or "").startswith("err") and read(base + "/ctl/kind") == "file\n", a)
    d.stop()


# ---------------------------------------------------------------- leftovers

def t_leftovers():
    for p, pid in STARTED:
        if p.poll() is None:
            p.kill()
            p.wait(5)
    time.sleep(0.2)
    left = []
    binreal = os.path.realpath(BIN)
    mine = set(our_bin_pids())   # 天空裡跑的那份（疊 daemon）exe 是天空裡的路徑，比 dev＋inode
    for d in os.listdir("/proc"):
        if d.isdigit():
            try:
                args = read("/proc/%s/cmdline" % d).split("\0")
            except OSError:
                continue
            try:
                exe = os.readlink("/proc/%s/exe" % d)
            except OSError:
                exe = ""
            # proto8 的 daemon 也叫 aos-daemon：只比 /proc/<pid>/exe 是不是我們這份 build/bin/aos-daemon（或 cmdline 的 argv[0]），不比名字
            # 起動那一層（argv[0]）、天空裡的 toys.py（argv[1]）
            if exe == binreal or args[0] == BIN or args[1:2] == ["/toys/toys.py"] or int(d) in mine:
                left.append((d, " ".join(args)))
    check("leftovers: no processes", not left, left)
    units = units_left()
    check("leftovers: no systemd units", units == "", units)
    cgs = []
    ours = {n[:-len(".scope")] for n in our_scope_names()}
    for root, dirs, _ in os.walk("/sys/fs/cgroup/user.slice"):
        cgs += [os.path.join(root, x) for x in dirs if x[:-len(".scope")] in ours and x.endswith(".scope")]
    check("leftovers: no cgroups", not cgs, cgs)
    mi = [l for l in read("/proc/self/mountinfo").splitlines() if "aosdaemon" in l or TMP in l]
    check("leftovers: no mounts", not mi, mi)


GROUPS = {"basic": t_basic, "procs": t_procs, "ns": t_ns, "nsconf": t_nsconf, "landlock": t_landlock, "cgroup": t_cgroup,
          "mount": t_mount, "modes": t_modes, "restart": t_restart, "teardown": t_teardown, "access": t_access,
          "dirs": t_dirs, "stdio": t_stdio, "dconf": t_dconf, "grace": t_grace, "pdeath": t_pdeath, "forgetk": t_forgetk,
          "rename": t_rename, "noinit": t_noinit, "rlstay": t_rlstay, "dpath": t_dpath, "ilandlock": t_ilandlock,
          "exitcode": t_exitcode, "net": t_net, "seccomp": t_seccomp, "nest": t_nest, "cgpath": t_cgpath,
          "sigsrc": t_sigsrc, "ipath": t_ipath, "stuck": t_stuck, "nsby": t_nsby, "overlay": t_overlay, "merge": t_merge,
          "rinit": t_rinit, "iface": t_iface}


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
