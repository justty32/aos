"""run.py: runs the whole sky-1125 toy experiment once (a few seconds) and prints one PASS/FAIL/SKIP line per item; needs Linux user namespaces, newuidmap/newgidmap with a subuid range (item 9), and systemd --user (item 10)."""
import argparse, json, os, random, re, shutil, signal, socket, subprocess, sys, tempfile, time, traceback

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sky    # noqa: E402
import toys   # noqa: E402

PY = ["/usr/bin/python3", "-I", "-B"]
TOY = PY + ["/toys/toys.py"]  # a toy as it is run inside a sky
TOKENS = toys.FIXED["usage"]["input_tokens"] + toys.FIXED["usage"]["output_tokens"]
ZERO = "0000000000000000"


class Fail(Exception):
    pass


def die_with_me():
    """In the child before exec: get SIGKILL if run.py dies, so even a killed run.py leaves no daemon behind."""
    sky.libc.prctl(1, signal.SIGKILL, 0, 0, 0)  # PR_SET_PDEATHSIG


def clean_env():
    return {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "HOME": os.environ.get("HOME", "/")}


def subids(path):
    """(start, count) of the first range this user owns in /etc/subuid or /etc/subgid, or None."""
    me = {os.environ.get("USER", ""), str(os.getuid())}
    try:
        with open(path) as f:
            for line in f:
                name, start, count = line.strip().split(":")
                if name in me:
                    return int(start), int(count)
    except (OSError, ValueError):
        pass
    return None


def nspid(pid):
    try:
        with open(f"/proc/{pid}/status") as f:
            return [int(x) for x in next(l for l in f if l.startswith("NSpid:")).split()[1:]]
    except (OSError, StopIteration):
        return None


def children(pid):
    try:
        with open(f"/proc/{pid}/task/{pid}/children") as f:
            return [int(x) for x in f.read().split()]
    except OSError:
        return []


def wait_for(fn, timeout, what):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            v = fn()
            if v:
                return v
        except (OSError, ValueError, KeyError):
            pass
        time.sleep(0.05)
    raise Fail(f"timed out after {timeout}s waiting for {what}")


def sweep_stale():
    """Remove scratch folders of earlier runs that died before cleaning up (no live process mentions them)."""
    alive = b""
    for d in os.listdir("/proc"):
        if d.isdigit():
            try:
                with open(f"/proc/{d}/cmdline", "rb") as f:
                    alive += f.read() + b"\n"
            except OSError:
                pass
    gone = []
    for name in os.listdir("/tmp"):
        p = "/tmp/" + name
        if (re.fullmatch(r"sky-1125-[a-z0-9_]{8}", name) and os.path.isdir(p) and not os.path.islink(p)
                and os.lstat(p).st_uid == os.getuid() and p.encode() not in alive):
            shutil.rmtree(p, ignore_errors=True)
            gone.append(p)
    return gone


def cfg(*files, extra=()):
    return [x for f in files for x in sky.load_config(os.path.join(HERE, f))] + [["run.py", line] for line in extra]


class Run:
    def __init__(self, verbose, no_systemd=False, no_subuid=False):
        self.verbose, self.no_systemd, self.no_subuid = verbose, no_systemd, no_subuid
        self.tmp = tempfile.mkdtemp(prefix="sky-1125-", dir="/tmp")
        os.mkdir(self.tmp + "/logs")
        os.mkdir(self.tmp + "/live")
        with open(self.tmp + "/live/hello.txt", "w") as f:
            f.write("hello from a live mount\n")
        self.sock = self.tmp + "/daemon.sock"
        self.unit = self.popen = self.upstream = self.daemon_pid = self.cgroup = self.subuid = None
        self.landlock = -1
        self.results = []

    # ------------------------------------------------------------ plumbing

    def call(self, req):
        return sky.call(self.sock, req)

    def spawn(self, name, lines, argv):
        r = self.call({"op": "spawn", "name": name, "sky": lines, "argv": argv})
        if not r.get("ok"):
            raise Fail(f"spawn {name}: {r.get('error')}")
        return r

    def log(self, name):
        try:
            with open(f"{self.tmp}/logs/{name}.log") as f:
                return f.read()
        except OSError:
            return ""

    def events(self, name, event=None):
        out = []
        for line in self.log(name).splitlines():
            if line.startswith("{"):
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                if event is None or e.get("event") == event:
                    out.append(e)
        return out

    def wait_event(self, name, event, timeout=10):
        try:
            return wait_for(lambda: (self.events(name, event) or [None])[0], timeout, f"{name} to say {event}")
        except Fail:
            tail = " | ".join(self.log(name).strip().splitlines()[-3:])
            raise Fail(f"{name} did not say {event} within {timeout}s; log tail: {tail or '(empty)'}") from None

    def status(self):
        return self.call({"op": "status"})

    def inner_to_outer(self):
        """inner PID -> outer PID for every process in the daemon's PID namespace (from NSpid)."""
        mine = os.readlink(f"/proc/{self.daemon_pid}/ns/pid")
        out = {}
        for d in os.listdir("/proc"):
            if d.isdigit():
                try:
                    if os.readlink(f"/proc/{d}/ns/pid") != mine:
                        continue
                except OSError:
                    continue
                ns = nspid(d)
                if ns:
                    out[ns[-1]] = int(d)
        return out

    def outer(self, name):
        return self.inner_to_outer()[self.status()["procs"][name]["pid"]]

    def check_sky(self, name, rows=None):
        """The daemon's want-table for a proc (or the rows given) vs Linux's mountinfo for it, measured from outside."""
        ns = self.call({"op": "ns", "name": name})
        o = self.outer(name)
        with open(f"/proc/{o}/mountinfo") as f:
            mi = f.read()
        problems = sky.compare(ns["rows"] if rows is None else rows, mi, f"/proc/{o}/root", f"/proc/{self.daemon_pid}/root")
        return problems, ns, len(sky.parse_mountinfo(mi))

    def table(self, ns):
        short = {self.tmp + "/run": "$RUN", self.tmp: "$TMP", HERE: "$TOYS"}
        return sky.table_text(ns["rows"], ns["settings"], short)

    # ------------------------------------------------------------ start and stop

    def start(self):
        log = open(self.tmp + "/logs/upstream.log", "w")
        self.upstream = subprocess.Popen(PY + [HERE + "/toys.py", "upstream", self.tmp + "/upstream.port"], stdout=log,
                                         stderr=subprocess.STDOUT, env=clean_env(), cwd="/", preexec_fn=die_with_me)
        self.port = int(wait_for(lambda: open(self.tmp + "/upstream.port").read(), 5, "the fake upstream"))
        uid, gid = os.getuid(), os.getgid()
        su, sg = subids("/etc/subuid"), subids("/etc/subgid")
        cmd = ["unshare", "--user"]
        if su and sg and shutil.which("newuidmap") and shutil.which("newgidmap") and not self.no_subuid:
            self.subuid = su
            cmd += [f"--map-users=0:{uid}:1", f"--map-users=1:{su[0]}:{su[1]}",
                    f"--map-groups=0:{gid}:1", f"--map-groups=1:{sg[0]}:{sg[1]}", "--setgroups=allow"]
        else:
            cmd += ["--map-root-user"]
        cmd += ["--mount", "--pid", "--fork", "--kill-child", "--mount-proc", "--propagation=private", "--",
                *PY, HERE + "/daemon.py", "--tmp", self.tmp, "--toys", HERE]
        env = clean_env()
        user_systemd = shutil.which("systemd-run") and subprocess.run(
            ["systemctl", "--user", "is-system-running"], capture_output=True, text=True).stdout.strip() in ("running", "degraded")
        if user_systemd and not self.no_systemd:
            self.unit = f"sky-1125-{os.getpid()}-{random.randrange(1 << 30):x}.scope"
            cmd = ["systemd-run", "--user", "--scope", "-p", "Delegate=yes", "--quiet", "--collect",
                   f"--unit={self.unit}", "--"] + cmd + ["--cgroup-unit", self.unit]
            env.update({k: os.environ[k] for k in ("XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS") if k in os.environ})
        self.popen = subprocess.Popen(cmd, stdout=open(self.tmp + "/logs/daemon.log", "w"), stderr=subprocess.STDOUT, env=env,
                                      cwd="/", preexec_fn=die_with_me)  # unshare --kill-child passes it on to the daemon

        def find_daemon():  # the process that is PID 1 inside, somewhere under what we started
            todo = [self.popen.pid]
            while todo:
                p = todo.pop()
                ns = nspid(p)
                if ns and len(ns) == 2 and ns[1] == 1:
                    return p
                todo += children(p)
            return None
        self.daemon_pid = wait_for(find_daemon, 10, "the daemon process")
        ping = wait_for(lambda: os.path.exists(self.sock) and self.call({"op": "ping"}), 10, "the daemon socket")
        self.cgroup, self.landlock = ping.get("cgroup"), ping.get("landlock", -1)
        print(f"sky-1125 toy experiment (spike). scratch {self.tmp}; daemon pid {self.daemon_pid} outside = 1 inside; "
              f"subuid {'%d+%d' % self.subuid if self.subuid else 'none'}; cgroup {'delegated' if self.cgroup else 'none'}; "
              f"Landlock ABI {self.landlock}")

    def start_kernels_and_leader(self):
        self.spawn("draw-kernel", cfg("kernel.sky"), TOY + ["draw-kernel"])
        self.wait_event("draw-kernel", "registered")
        self.spawn("perm-kernel", cfg("perm.sky"), TOY + ["perm-kernel"])
        self.spawn("llm-proxy", cfg("kernel.sky"), TOY + ["llm-proxy", str(self.port)])
        self.spawn("ring-a", cfg("kernel.sky"), TOY + ["kernel", "ring-b"])
        self.wait_event("ring-a", "registered")
        self.spawn("ring-b", cfg("kernel.sky"), TOY + ["kernel", "ring-a"])
        for k in ("perm-kernel", "llm-proxy", "ring-b"):
            self.wait_event(k, "registered")
        self.call({"op": "set", "options": {"no_cycles": True}})
        self.spawn("ring-c", cfg("kernel.sky"), TOY + ["kernel", "ring-d"])
        self.wait_event("ring-c", "registered")
        self.spawn("ring-d", cfg("kernel.sky"), TOY + ["kernel", "ring-c"])
        self.wait_event("ring-d", "refused")
        self.spawn("leader", cfg("leader.sky"), TOY + ["leader", str(self.port)])
        self.wait_event("leader", "done", 20)
        self.spawn("netless", cfg("kernel.sky", extra=["net none"]), TOY + ["netless"])
        self.wait_event("drawer", "done", 20)
        self.wait_event("netless", "handdown")

    def teardown(self):
        notes = []
        if self.daemon_pid and os.path.exists(f"/proc/{self.daemon_pid}"):
            os.kill(self.daemon_pid, signal.SIGKILL)
        for p in (self.popen, self.upstream):
            if p:
                if p is self.upstream:
                    p.terminate()
                try:
                    p.wait(5)
                except subprocess.TimeoutExpired:
                    p.kill()
                    p.wait()
        if self.unit and subprocess.run(["systemctl", "--user", "is-active", self.unit], capture_output=True, text=True).stdout.strip() == "active":
            subprocess.run(["systemctl", "--user", "stop", self.unit], capture_output=True)
            notes.append(f"had to stop {self.unit}")
        left = []
        for d in os.listdir("/proc"):
            if d.isdigit() and int(d) != os.getpid():
                try:
                    with open(f"/proc/{d}/cmdline", "rb") as f:
                        if self.tmp.encode() in f.read():
                            left.append(int(d))
                except OSError:
                    pass
        for pid in left:  # only ours: their command line names this run's scratch folder
            os.kill(pid, signal.SIGKILL)
        if left:
            notes.append(f"killed leftover processes {left}")
        if self.cgroup:  # systemd removes the scope once it is empty; give it a moment
            try:
                wait_for(lambda: not os.path.isdir(self.cgroup), 3, "the scope's cgroup to go")
            except Fail:
                pass
        if self.cgroup and os.path.isdir(self.cgroup):
            for d in os.listdir(self.cgroup):
                if d.startswith("sky-") and os.path.isdir(f"{self.cgroup}/{d}"):
                    try:
                        os.rmdir(f"{self.cgroup}/{d}")
                    except OSError:
                        pass
            notes.append(f"cgroup {self.cgroup} was still there")
        with open("/proc/self/mountinfo") as f:
            if self.tmp in f.read():
                notes.append("a mount under the scratch folder is visible outside")
        shutil.rmtree(self.tmp, ignore_errors=True)
        if os.path.exists(self.tmp):
            notes.append(f"could not remove {self.tmp}")
        print("cleanup: " + ("; ".join(notes) if notes else f"nothing left (no processes, mounts or cgroups); {self.tmp} removed"))
        return not notes

    # ------------------------------------------------------------ the items

    def item1(self):
        problems, ns, n = self.check_sky("leader")
        others = {k: self.check_sky(k)[0] for k in ("draw-kernel", "perm-kernel", "llm-proxy", "ring-a")}
        bad = {k: v for k, v in others.items() if v}
        if problems or bad:
            raise Fail(f"want-table vs mountinfo: leader {problems}; others {bad}")
        # the comparison has to be able to fail: a table missing /tmp, and one that says /etc comes from /usr
        missing = self.check_sky("leader", [r for r in ns["rows"] if r["path"] != "/tmp"])[0]
        wrong = self.check_sky("leader", [dict(r, base="/usr") if r["path"] == "/etc" else r for r in ns["rows"]])[0]
        if not missing or not wrong:
            raise Fail(f"the comparison did not notice a wrong table: {missing} {wrong}")
        mounts = sum(1 for r in ns["rows"] if r["kind"] != "symlink")
        return (f"leader.sky (via base.sky) became a {len(ns['rows'])}-row table in the daemon ({mounts} mounts + symlinks); "
                f"leader's /proc/PID/mountinfo has exactly those {n} mounts, same sources (dev+inode) and ro/rw; "
                f"4 kernel skies match too; a wrong table is caught", self.table(ns).splitlines()
                + [f"negative control: {missing[0]} / {wrong[0]}"])

    def item2(self):
        host_has = os.path.lexists("/usr/bin/draw")
        ev = self.wait_event("drawer", "draw")
        drew = self.events("draw-kernel", "drew")
        leader_has = os.path.lexists(f"/proc/{self.outer('leader')}/root/usr/bin/draw")
        problems, ns, _ = self.check_sky("drawer")
        last = ev["out"].strip().splitlines()[-1] if ev["out"].strip() else ""
        mine = [e for e in drew if e["caller"] == "drawer" and e["rc"] == 0]
        if host_has or leader_has or ev["rc"] != 0 or "for drawer" not in last or not mine or problems:
            raise Fail(f"host_has={host_has} leader_has={leader_has} rc={ev['rc']} out={last!r} err={ev['err']!r} drew={drew} table={problems}")
        rows = [l for l in self.table(ns).splitlines() if "kernel " in l]
        return (f"drawer ran `draw turtle` (exit 0) and draw-kernel wrote into drawer's own stdout: \"{last}\"; "
                f"no /usr/bin/draw outside or in leader's sky", ev["out"].rstrip("\n").splitlines()[:-1] + rows)

    def item3(self):
        hd = {e["case"]: e for e in self.events("leader", "handdown") + self.events("netless", "handdown")}
        want = {"not-in-sky": "not in leader's sky", "rw-upgrade": "read-only", "symlink-escape": "symlink",
                "other-uid": "identity", "unlock": "unlocked", "net-widen": "host network"}
        wrong = [c for c, frag in want.items() if c not in hd or hd[c]["ok"] or frag not in (hd[c]["error"] or "")]
        listed = "base.sky" in self.log("try-has-it")
        if wrong or not hd.get("has-it", {}).get("ok") or not listed:
            raise Fail(f"cases not refused as expected: {wrong}; has-it={hd.get('has-it')} ran={listed}")
        return (f"{len(want)} hand-downs refused (not in the starter's sky, ro->rw, a symlink out of a bind, another uid, "
                f"unlock, host net from a netless starter); passing on /toys that leader has worked",
                [f"{c}: `{hd[c]['line']}` -> {hd[c]['error']}" for c in want] + [f"has-it: `{hd['has-it']['line']}` -> ok"])

    def item4(self):
        deps = {e["kernel"]: e for e in self.events("leader", "deps")}
        perm, ring = deps.get("perm-kernel", {}), deps.get("ring-a", {})
        used = self.events("perm-kernel", "used-draw")
        b, c, d = (self.events(k, "registered") + self.events(k, "refused") for k in ("ring-b", "ring-c", "ring-d"))
        board = self.status()["board"]
        checks = {
            "perm chain": perm.get("chain") == ["perm-kernel", "draw-kernel"] and perm.get("cycle") is None,
            "perm uses draw": bool(used) and used[0]["rc"] == 0,
            "cycle seen": ring.get("cycle") == ["ring-a", "ring-b", "ring-a"] and ring.get("decision", "").startswith("skip"),
            "ring-b accepted (option off)": bool(b) and b[0]["reply"]["ok"],
            "ring-c accepted": bool(c) and c[0]["reply"]["ok"],
            "ring-d refused (option on)": bool(d) and not d[0]["reply"]["ok"] and "cycle" in d[0]["reply"]["error"] and "ring-d" not in board,
        }
        if not all(checks.values()):
            raise Fail(f"{checks}; perm={perm} ring={ring} ring-d={d}")
        return ("leader asked: perm-kernel -> draw-kernel (and perm-kernel's own sky uses draw); with no_cycles off "
                "ring-a <-> ring-b both registered and leader saw the cycle and skipped it; with no_cycles on ring-d was refused",
                [f"deps {k}: chain {v['chain']} cycle {v['cycle']} -> {v['decision']}" for k, v in deps.items()]
                + [f"ring-d: {d[0]['reply']['error']}",
                   f"perm-kernel registered depends [draw-kernel]; kernels its sky uses but it did not declare: "
                   f"{self.events('perm-kernel', 'registered')[0]['reply']['undeclared']}"])

    def item5(self):
        net = self.wait_event("drawer", "net")
        total = self.wait_event("drawer", "llm-total")["tokens"]
        with open(f"/proc/{self.daemon_pid}/root{self.tmp}/run/procs/llm-proxy/state.json") as f:
            state = json.load(f)
        ups = self.events("upstream", "request")
        want = 3 * TOKENS
        ok = (net["ifaces"] == ["lo"] and net["direct_to_upstream"] != "OK" and net["outside"] not in ("OK", "not tried")
              and total == want and state["calls"] == 3 and state["input_tokens"] + state["output_tokens"] == want
              and state["by_caller"].get("drawer") == {"calls": 3, "tokens": want}
              and len(ups) == 3 and all(u["peer"] == "127.0.0.1" for u in ups))
        if not ok:
            raise Fail(f"net={net} drawer_total={total} proxy={state} upstream={ups}")
        return (f"drawer's net namespace has only lo; straight to the upstream: {net['direct_to_upstream']}, to 192.0.2.1: "
                f"{net['outside']}; 3 calls via /srv/llm: proxy counted {state['input_tokens']}+{state['output_tokens']}="
                f"{want} tokens for drawer (by peer pid -> name), same as drawer saw; upstream got 3 requests, all from the proxy",
                [f"proxy state.json: {json.dumps(state)}"])

    def item6(self):
        self.spawn("watcher", cfg("base.sky"), TOY + ["watcher"])
        self.wait_event("watcher", "watching")
        before = len(self.call({"op": "ns", "name": "watcher"})["rows"])
        r = self.call({"op": "mount", "name": "watcher", "line": "bind $TMP/live /srv/new"})
        if not r.get("ok"):
            raise Fail(f"live mount refused: {r.get('error')}")
        seen = self.wait_event("watcher", "seen", 5)
        problems, ns, _ = self.check_sky("watcher")
        row = [x for x in ns["rows"] if x["path"] == "/srv/new"]
        if seen["text"] != "hello from a live mount" or not row or len(ns["rows"]) != before + 1 or problems:
            raise Fail(f"seen={seen} row={row} rows {before}->{len(ns['rows'])} table={problems}")
        return ("daemon got `bind $TMP/live /srv/new` for running watcher; watcher saw hello.txt appear, the table grew "
                "by that one row (by live:user) and still matches mountinfo", [l for l in self.table(ns).splitlines() if "/srv/new" in l])

    def item7(self):
        sib = self.status()["procs"]["watcher"]["pid"]
        abstract = f"sky-1125-test-{os.getpid()}"   # stands for a host abstract socket (X11, D-Bus, ...)
        lst = socket.socket(socket.AF_UNIX)
        lst.bind("\0" + abstract)
        lst.listen(8)
        try:
            self.spawn("lock-on", cfg("base.sky"), TOY + ["locktest", "locked", str(sib), abstract])
            self.spawn("lock-off", cfg("base.sky", extra=["lock off"]), TOY + ["locktest", "unlocked", str(sib), abstract])
            self.spawn("lock-half", cfg("base.sky", extra=["lock nolandlock"]), TOY + ["locktest", "locked", str(sib), abstract])
            on, off = self.wait_event("lock-on", "locktest"), self.wait_event("lock-off", "locktest")
            half = self.wait_event("lock-half", "locktest")
        finally:
            lst.close()
        c, scoped = on["caps"], self.landlock >= 6
        locked = {
            "caps all 0, NoNewPrivs 1, securebits noroot+locked": all(c[k] == ZERO for k in ("CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb"))
                and c["NoNewPrivs"] == "1" and on["securebits"] & 0x3 == 0x3,
            "umount(2)/mount(2) EPERM": on["umount_syscall"] == "EPERM" and on["mount_syscall"] == "EPERM",
            "umount/mount commands fail": on["umount_cmd"]["rc"] != 0 and on["mount_cmd"]["rc"] != 0,
            "own user namespace does not unlock": "umount EINVAL" in on["own_userns"],
            "cannot read /proc/1/root, a sibling's root or environ": on["daemon_root"] == "EACCES" and on["sibling_root"] == "EACCES"
                and on["sibling_environ"] == "EACCES",
            "cannot signal a sibling": on["signal_sibling"] == "EPERM" or not scoped,
            "cannot reach a host abstract socket": on["abstract_socket"] == "EPERM" or not scoped,
        }
        control = {
            "unlocked: umount /toys works": off["umount_cmd"]["rc"] == 0,
            "unlocked: /proc/1/root shows the real system": not str(off["daemon_root"]).startswith("E"),
            "unlocked: reaches the host abstract socket": off["abstract_socket"] == "OK",
            "caps-only: umount(2) EPERM": off["caps_after_drop"]["CapEff"] == ZERO and off["umount_syscall_after_drop"] == "EPERM",
            "caps-only: after execve umount works again": off["umount_cmd_after_drop"]["rc"] == 0,
        }
        hc = half["caps"]
        control.update({  # locked the same way but without the Landlock domain: caps are gone, yet the siblings are open
            "no Landlock: caps 0, umount EPERM": hc["CapEff"] == ZERO and half["umount_syscall"] == "EPERM",
            "no Landlock: /proc/1/root EACCES (daemon not dumpable)": half["daemon_root"] == "EACCES",
            "no Landlock: sibling's root and environ readable": half["sibling_root"] == "OK" and half["sibling_environ"] == "OK",
            "no Landlock: can signal the sibling": half["signal_sibling"] == "OK",
            "no Landlock: reaches the host abstract socket": half["abstract_socket"] == "OK",
        })
        if not all(locked.values()) or not all(control.values()):
            raise Fail(f"locked {locked} {on}; controls {control} {off} {half}")
        return ("locked proc (uid 0 inside): umount/mount fail as syscalls and as commands, its own user namespace "
                "gets EINVAL (sky mounts are locked), /proc/1/root and a sibling's root and environ EACCES"
                + (", signals and a host abstract socket EPERM" if scoped else f" (Landlock ABI {self.landlock}: signals and abstract sockets not scoped)")
                + "; controls: unlocked it unmounts /toys and sees the real / via /proc/1/root; caps dropped alone come back "
                "with the next execve; locked without Landlock it can still read a sibling's root and environ, signal it, and reach the abstract socket",
                [f"locked: umount said {on['umount_cmd']['said']!r}; securebits {on['securebits']:#x}; own userns: {on['own_userns']}",
                 f"unlocked: /proc/1/root lists {off['daemon_root']!r}; abstract socket {off['abstract_socket']}; "
                 f"caps-only: umount(2) {off['umount_syscall_after_drop']}, then exec umount rc {off['umount_cmd_after_drop']['rc']}"])

    def item8(self):
        i2o = self.inner_to_outer()
        procs = {p["pid"]: n for n, p in self.status()["procs"].items() if p["state"] == "running"}
        procs[1] = "daemon"
        seen = sorted((inner, outer, procs.get(inner, "-")) for inner, outer in i2o.items())
        os.kill(self.daemon_pid, signal.SIGKILL)
        t0 = time.monotonic()
        wait_for(lambda: not any(os.path.exists(f"/proc/{o}") for _, o, _ in seen), 5, "every process in the PID namespace to go")
        dt = time.monotonic() - t0
        self.popen.wait(5)
        gone_cg = True
        if self.cgroup:
            try:
                wait_for(lambda: not os.path.exists(self.cgroup), 5, "the scope's cgroup to go")
            except Fail:
                gone_cg = False
        if len(seen) < 8 or not gone_cg:
            raise Fail(f"seen={seen} cgroup_gone={gone_cg}")
        dk = next(s for s in seen if s[2] == "draw-kernel")
        return (f"daemon (pid {self.daemon_pid} outside, 1 inside) got SIGKILL from outside; all {len(seen)} processes of its "
                f"PID namespace were gone after {dt:.2f}s" + (", its cgroup scope too" if self.cgroup else "")
                + f" (e.g. draw-kernel: {dk[1]} outside, {dk[0]} inside)",
                ["NSpid (outside inside name): " + ", ".join(f"{o} {i} {n}" for i, o, n in seen)])

    def item9(self):
        if not self.subuid:
            return None, "skipped: no subuid range or newuidmap here (or --no-subuid)", []
        shared = ["bind -w $RUN/shared /shared"]
        self.spawn("alice", cfg("base.sky", extra=shared + ["uid 1001 1001"]), TOY + ["idtest", "alice"])
        a = self.wait_event("alice", "alice")
        self.spawn("bob", cfg("base.sky", extra=shared + ["uid 1002 1002"]), TOY + ["idtest", "bob"])
        b = self.wait_event("bob", "bob")
        st = os.stat(f"/proc/{self.daemon_pid}/root{self.tmp}/run/shared/alice.txt")
        outside = self.subuid[0] + 1000
        uid_of = lambda n: open(f"/proc/{self.outer(n)}/status").read().split("Uid:")[1].split()[0]
        if not (a["uid"] == 1001 and b["uid"] == 1002 and a["read_own"] == "alice's secret" and b["file_uid"] == 1001
                and b["read"] == "EACCES" and b["write"] == "EACCES" and st.st_uid == outside):
            raise Fail(f"alice={a} bob={b} outside_uid={st.st_uid} (want {outside})")
        return (f"alice (uid 1001 inside, {uid_of('alice')} outside) and bob (1002, {uid_of('bob')}) share /shared; bob gets "
                f"EACCES reading and writing alice's 0600 file; on disk it belongs to uid {st.st_uid}; no root used", [])

    def item10(self):
        if not self.cgroup:
            return None, "skipped: the daemon has no delegated cgroup (no systemd --user here, or --no-systemd)", []
        self.spawn("ticker", cfg("base.sky"), TOY + ["ticker"])
        ticks = lambda: self.log("ticker").count("tick ")
        wait_for(lambda: ticks() >= 5, 5, "ticker to tick")
        fr = self.call({"op": "freeze", "name": "ticker"})
        time.sleep(0.1)
        n1 = ticks()
        time.sleep(0.6)
        n2 = ticks()
        th = self.call({"op": "thaw", "name": "ticker"})
        time.sleep(0.6)
        n3 = ticks()
        if not (fr.get("frozen") == "1" and n2 == n1 and th.get("frozen") == "0" and n3 - n2 >= 5):
            raise Fail(f"freeze={fr} thaw={th} ticks {n1}->{n2} frozen, {n2}->{n3} thawed")
        return (f"ticker (prints a counter, offers no interface) frozen via its cgroup: 0 ticks in 0.6s "
                f"(cgroup.events frozen 1); thawed: {n3 - n2} ticks in 0.6s", [f"cgroup: {self.cgroup}/sky-ticker"])

    ITEMS = [(1, "sky config", "item1"), (2, "name given to a kernel", "item2"), (3, "only hand down what you have", "item3"),
             (4, "dependency chain", "item4"), (5, "llm proxy as the only way out", "item5"), (6, "change while running", "item6"),
             (7, "sky locked", "item7"), (9, "subuid identities (extra)", "item9"), (10, "cgroup freeze (extra)", "item10"),
             (8, "PID namespace", "item8")]

    def item(self, n, title, fn, ready):
        try:
            if not ready:
                raise Fail("setup did not finish (see above)")
            got = getattr(self, fn)()  # (message, details) = PASS; (None, message, details) = SKIP
            status, msg, details = ("PASS", *got) if len(got) == 2 else ("SKIP", *got[1:])
        except Fail as e:
            status, msg, details = "FAIL", str(e), []
        except Exception as e:
            status, msg, details = "FAIL", f"{type(e).__name__}: {e}", traceback.format_exc().splitlines()[-4:]
        self.results.append((n, status))
        print(f"{status}  {n:>2}  {title}: {msg}")
        for d in details if (self.verbose or n in (1, 2, 3, 4)) else details[:2]:
            print(f"          {d}")
        sys.stdout.flush()


def main():
    ap = argparse.ArgumentParser(description="Run the sky-1125 toy experiment and print PASS/FAIL per item.")
    ap.add_argument("-v", "--verbose", action="store_true", help="print every detail line")
    ap.add_argument("--pause", action="store_true", help="before item 8 kills the daemon, wait for Enter (poke around)")
    ap.add_argument("--no-systemd", action="store_true", help="do not use systemd-run (item 10 is skipped)")
    ap.add_argument("--no-subuid", action="store_true", help="map only your own uid (item 9 is skipped)")
    a = ap.parse_args()
    stale = sweep_stale()
    if stale:
        print("removed scratch folders left by earlier runs that were killed: " + " ".join(stale))
    run = Run(a.verbose, a.no_systemd, a.no_subuid)
    ok_clean = False
    try:
        ready = True
        try:
            run.start()
            run.start_kernels_and_leader()
        except Exception as e:
            ready = False
            print(f"FAIL  setup: {type(e).__name__}: {e}")
        for n, title, fn in Run.ITEMS:
            if n == 8 and a.pause and ready:
                input(f"paused; daemon socket {run.sock}; e.g. python3 {HERE}/sky.py ns {run.sock} drawer ; Enter to go on ")
            run.item(n, title, fn, ready)
    finally:
        ok_clean = run.teardown()
    counts = {s: sum(1 for _, x in run.results if x == s) for s in ("PASS", "FAIL", "SKIP")}
    print(f"SUMMARY: {counts['PASS']} PASS, {counts['FAIL']} FAIL, {counts['SKIP']} SKIP" + ("" if ok_clean else "; cleanup had to fix things"))
    sys.exit(0 if counts["FAIL"] == 0 and ok_clean else 1)


if __name__ == "__main__":
    main()
