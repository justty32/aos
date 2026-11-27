#!/usr/bin/env python3
# run.py：channels-1127 一鍵跑——編 probe、照七種設定（預設、net host、seccomp off、subuid、三種 ABI 3 模擬）各起一次 aos-daemon（兄弟 A、B、沒有 /proc 的 C，外面一隻對照的 hold），收結果印成表，最後比對有沒有留下東西。
# 用法：python3 run.py [-v] [--json OUT.json] [--tmp DIR] [--only VARIANT ...]
import argparse, json, os, re, select, shutil, signal, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
P9 = os.path.normpath(os.path.join(HERE, "..", ".."))
BIN = os.path.join(P9, "cpp", "aos-daemon", "build", "bin", "aos-daemon")
KEY_BASE = 0x43481100

# variant -> (extra config for A, B, C; per-proc uid or None; use the fake-ABI shim)
VARIANTS = [
    ("default", {}, None, False),
    ("net_host", {"net": "host"}, None, False),
    ("seccomp_off", {"locks": {"seccomp": "off"}}, None, False),
    ("subuid", {}, {"A": 1, "B": 2, "C": 3}, False),
    ("abi3_sim", {}, None, True),
    ("abi3_net_host", {"net": "host"}, None, True),
    ("abi3_subuid", {}, {"A": 1, "B": 2, "C": 3}, True),
]


def log(*a):
    print(*a, flush=True)


def read(p):
    with open(p) as f:
        return f.read()


def wait_for(cond, timeout=10.0, step=0.05):
    end = time.monotonic() + timeout
    while True:
        try:
            v = cond()
        except OSError:
            v = None
        if v or time.monotonic() > end:
            return v
        time.sleep(step)


def kv_file(p):
    out = {}
    for line in read(p).splitlines():
        k, _, v = line.partition(" ")
        out[k] = v
    return out


def jsonl(p):
    out = {}
    if os.path.exists(p):
        for line in read(p).splitlines():
            if line.strip():
                r = json.loads(line)
                out[r["id"]] = r
    return out


# ---------------------------------------------------------------- what is left over (before/after)

def our_ipc_keys():
    keys = set()
    out = subprocess.run(["ipcs"], capture_output=True, text=True).stdout
    for line in out.splitlines():
        m = re.match(r"(0x[0-9a-f]+)\s", line)
        if m:
            keys.add(line.split()[0] + " " + line.split()[1])
    return keys


def snapshot(tmproot, probe_id):
    """probe_id: (st_dev, st_ino) of the probe binary (it is deleted before the second snapshot)."""
    snap = {}
    binst = os.stat(BIN)
    procs = []
    for d in os.listdir("/proc"):
        if not d.isdigit():
            continue
        try:
            st = os.stat("/proc/%s/exe" % d)
        except OSError:
            continue
        if (st.st_dev, st.st_ino) in ((binst.st_dev, binst.st_ino), probe_id):
            procs.append(d)
    snap["processes (exe is our aos-daemon or probe)"] = set(procs)
    snap["mounts"] = {l for l in read("/proc/self/mountinfo").splitlines() if tmproot in l or "aosdaemon" in l}
    units = subprocess.run(["systemctl", "--user", "list-units", "aos-daemon-*", "--all", "--no-legend", "--plain"],
                           capture_output=True, text=True).stdout
    snap["systemd --user aos-daemon-* units"] = {l.split()[0] for l in units.splitlines() if l.strip()}
    cgs = set()
    for root, dirs, _ in os.walk("/sys/fs/cgroup/user.slice"):
        cgs |= {os.path.join(root, x) for x in dirs if x.startswith("aos-daemon-")}
    snap["cgroup dirs aos-daemon-*"] = cgs
    snap["/tmp entries"] = set(os.listdir("/tmp"))
    snap["tmp root entries"] = set(os.listdir(tmproot))
    snap["SysV IPC (ipcs key id)"] = our_ipc_keys()
    snap["/dev/mqueue"] = set(os.listdir("/dev/mqueue")) if os.path.isdir("/dev/mqueue") else set()
    snap["/dev/shm channels1127-*"] = {x for x in os.listdir("/dev/shm") if x.startswith("channels1127")}
    return snap


def clear_own_leftovers():
    """前一次被打斷留下的、用我們的 key／名字建的東西（只動自己的）。"""
    for kind, flag in (("-m", "-M"), ("-q", "-Q"), ("-s", "-S")):
        for i in range(1, 4):
            r = subprocess.run(["ipcrm", flag, hex(KEY_BASE + i)], capture_output=True, text=True)
            if r.returncode == 0:
                log("NOTE removed a leftover SysV object key %s" % hex(KEY_BASE + i))
    for tag in ("out", "B", "A"):
        for p in ("/dev/mqueue/channels1127-" + tag, "/dev/shm/channels1127-" + tag):
            if os.path.exists(p):
                os.unlink(p)
                log("NOTE removed leftover " + p)


# ---------------------------------------------------------------- one daemon run

class Run:
    def __init__(self, work, probe, shim, name, extra, uids, use_shim, verbose):
        self.work, self.probe, self.shim, self.name = work, probe, shim, name
        self.extra, self.uids, self.use_shim, self.v = extra, uids, use_shim, verbose
        self.procs = []   # Popen we started (outside): killed by pid at the end if still there
        self.res = {"variant": name}

    def out_dir(self, who):
        d = os.path.join(self.work, "out-" + who)
        os.makedirs(d, exist_ok=True)
        os.chmod(d, 0o777)   # subuid procs write here too
        return d

    def ns(self, who, with_proc=True):
        ns = [{"type": "bind", "src": "/usr", "dst": "/usr"}, {"type": "bind", "src": "/etc", "dst": "/etc"},
              {"type": "symlink", "target": "usr/bin", "dst": "/bin"}, {"type": "symlink", "target": "usr/lib", "dst": "/lib"},
              {"type": "symlink", "target": "usr/lib64", "dst": "/lib64"}, {"type": "dev", "dst": "/dev"}]
        if with_proc:
            ns.append({"type": "proc", "dst": "/proc"})
        ns += [{"type": "tmpfs", "dst": "/tmp"}, {"type": "bind", "src": os.path.dirname(self.probe), "dst": "/w"},
               {"type": "bind", "src": self.out_dir(who), "dst": "/out", "rw": True}]
        return ns

    def proc_config(self, who, argv, with_proc=True):
        c = {"name": who, "argv": argv, "ns": self.ns(who, with_proc)}
        c.update(json.loads(json.dumps(self.extra)))
        if self.uids and who in self.uids:
            c["uid"] = self.uids[who]
        p = os.path.join(self.work, who + ".json")
        with open(p, "w") as f:
            json.dump(c, f)
        return p

    def ctl(self, line):
        try:
            fd = os.open(self.root + "/ctl", os.O_WRONLY)
            try:
                os.write(fd, (line + "\n").encode())
            finally:
                os.close(fd)
            return None
        except OSError as e:
            st = read(self.root + "/status")
            m = re.search(r"aos_ctl_error: (.*)", st)
            return "%s %s" % (e.strerror, m.group(1) if m else "")

    def fact(self, who, f):
        return read("%s/procs/%s/%s" % (self.root, who, f))

    def ns_pid(self, who):
        return int(re.search(r"ns: (\d+)", self.fact(who, "pid")).group(1))

    def run(self):
        w = self.work
        os.makedirs(os.path.join(w, "outside"))
        # 1. the outside control process
        oinfo = os.path.join(w, "outside", "out.info")
        hold = subprocess.Popen([self.probe, "hold", "out", oinfo], stdin=subprocess.DEVNULL)
        self.procs.append(hold)
        if not wait_for(lambda: os.path.exists(oinfo)):
            raise RuntimeError("outside holder did not write its info")
        out = kv_file(oinfo)
        self.res["outside_hold"] = out
        # 2. the daemon (init: a sleeper with the default settings)
        init = {"name": "init", "argv": ["/w/probe", "sleep"], "ns": self.ns("init")}
        dj = os.path.join(w, "daemon.json")
        with open(dj, "w") as f:
            json.dump({"init": init}, f)
        env = dict(os.environ)
        if self.use_shim:
            env["LD_PRELOAD"] = self.shim
        self.err_path = os.path.join(w, "daemon.err")
        self.d = subprocess.Popen([BIN, dj], stdout=subprocess.PIPE, stderr=open(self.err_path, "w"), stdin=subprocess.DEVNULL,
                                  env=env, cwd="/")
        self.procs.append(self.d)
        line = self._line(10)
        m = re.fullmatch(r"export AOS_DAEMON=/proc/(\d+)/cwd", line or "")
        if not m:
            raise RuntimeError("daemon did not start: %r\n%s" % (line, read(self.err_path)))
        self.root = "/proc/%s/cwd" % m.group(1)
        if not wait_for(lambda: self.fact("init", "state") == "alive\n"):
            raise RuntimeError("init not alive\n" + read(self.err_path))
        st = read(self.root + "/status")
        self.res["landlock_abi"] = re.search(r"landlock_abi: (.*)", st).group(1)
        # 3. sibling B holds its things
        err = self.ctl("start " + self.proc_config("B", ["/w/probe", "hold", "B", "/out/B.info"]))
        if err:
            raise RuntimeError("start B: " + err)
        binfo = os.path.join(self.out_dir("B"), "B.info")
        if not wait_for(lambda: os.path.exists(binfo)):
            raise RuntimeError("B did not write its info")
        b = kv_file(binfo)
        self.res["B_hold"] = b
        self.res["locks_B"] = self.fact("B", "locks")
        inp = {"b_pid": self.ns_pid("B"), "init_pid": self.ns_pid("init"), "out_host_pid": hold.pid,
               "b_marker_addr": b["marker_addr"], "b_tcp": b["tcp_port"], "out_tcp": out["tcp_port"],
               "out_hostname": out["hostname"], "out_session_keyring": out["session_keyring"],
               "out_user_keyring": out["user_keyring"], "b_session_keyring": b["session_keyring"],
               "b_user_keyring": b["user_keyring"]}
        # 4. A (with /proc) and C (without /proc) probe, one after the other
        for who, with_proc in (("A", True), ("C", False)):
            with open(os.path.join(self.out_dir(who), "in.txt"), "w") as f:
                f.write("".join("%s %s\n" % kv for kv in inp.items()))
            err = self.ctl("start " + self.proc_config(who, ["/w/probe", "probe", "/out/in.txt", "/out/result.jsonl"], with_proc))
            if err:
                raise RuntimeError("start %s: %s" % (who, err))
            self.res["locks_" + who] = self.fact(who, "locks")
            if not wait_for(lambda: self.fact(who, "state") == "dead\n", 60):
                raise RuntimeError(who + " did not finish in 60 s")
            self.res["exit_" + who] = self.fact(who, "exit").strip()
            self.res[who] = jsonl(os.path.join(self.out_dir(who), "result.jsonl"))
        # 5. the outside looks for what B made
        fout = os.path.join(w, "outside", "find.jsonl")
        subprocess.run([self.probe, "find", "B", b["tcp_port"], fout], check=True, timeout=30)
        self.res["find"] = jsonl(fout)
        # 6. stop B (it removes its SysV objects), the daemon, the outside holder
        self.ctl("kill B TERM")
        if not wait_for(lambda: self.fact("B", "state") == "dead\n"):
            log("NOTE %s: B did not stop on TERM" % self.name)

    def _line(self, wait):
        end = time.monotonic() + wait
        buf = b""
        fd = self.d.stdout.fileno()
        while time.monotonic() < end and b"\n" not in buf:
            r, _, _ = select.select([fd], [], [], 0.05)
            if r:
                c = os.read(fd, 4096)
                if not c:
                    break
                buf += c
        return buf.decode().split("\n")[0] if b"\n" in buf else None

    def stop(self):
        for p in reversed(self.procs):
            if p.poll() is None:
                p.send_signal(signal.SIGTERM)
                try:
                    p.wait(10)
                except subprocess.TimeoutExpired:
                    p.kill()
                    p.wait(5)


# ---------------------------------------------------------------- table

def cell(r):
    if r is None:
        return "-"
    return "open" if r["ok"] else (r["err"] or "closed")


def main():
    ap = argparse.ArgumentParser(description="Probe which non-file channels a proc under proto9 aos-daemon still has.")
    ap.add_argument("-v", action="store_true", help="print every detail")
    ap.add_argument("--json", help="write all results here")
    ap.add_argument("--tmp", default=tempfile.gettempdir(), help="where to make the work folder (default: the temp dir)")
    ap.add_argument("--only", nargs="*", help="run only these variants")
    a = ap.parse_args()
    if not os.access(BIN, os.X_OK):
        log("building aos-daemon")
        subprocess.run(["make", "-C", os.path.dirname(os.path.dirname(os.path.dirname(BIN)))], check=True)
    os.makedirs(a.tmp, exist_ok=True)
    top = tempfile.mkdtemp(prefix="channels-1127-", dir=a.tmp)
    bdir = os.path.join(top, "b")
    os.makedirs(bdir)
    os.chmod(top, 0o755)
    probe, shim = os.path.join(bdir, "probe"), os.path.join(bdir, "fakeabi.so")
    subprocess.run(["gcc", "-O1", "-Wall", "-o", probe, os.path.join(HERE, "probe.c")], check=True)
    subprocess.run(["gcc", "-shared", "-fPIC", "-O1", "-Wall", "-o", shim, os.path.join(HERE, "fakeabi.c"), "-ldl"], check=True)
    clear_own_leftovers()
    pst = os.stat(probe)
    probe_id = (pst.st_dev, pst.st_ino)
    before = snapshot(a.tmp, probe_id)
    results, failed = [], []
    for name, extra, uids, use_shim in VARIANTS:
        if a.only and name not in a.only:
            continue
        work = os.path.join(top, name)
        os.makedirs(work)
        os.chmod(work, 0o755)
        r = Run(work, probe, shim, name, extra, uids, use_shim, a.v)
        try:
            r.run()
        except Exception as e:   # keep going with the other variants; this one is reported
            failed.append(name)
            log("FAIL %s: %s" % (name, e))
        finally:
            r.stop()
        results.append(r.res)
        log("ran %s (landlock_abi %s, A %s, C %s)" % (name, r.res.get("landlock_abi"), r.res.get("exit_A"), r.res.get("exit_C")))
    time.sleep(0.3)
    shutil.rmtree(top, ignore_errors=True)
    after = snapshot(a.tmp, probe_id)

    names = [r["variant"] for r in results]
    ids = []
    for r in results:
        for k in list(r.get("A", {})) + ["C:" + x for x in r.get("C", {})] + list(r.get("find", {})):
            if k not in ids:
                ids.append(k)

    def get(r, k):
        if k.startswith("C:"):
            return r.get("C", {}).get(k[2:])
        return r.get("A", {}).get(k) or r.get("find", {}).get(k)

    w = max(len(k) for k in ids) if ids else 10
    log("")
    log("%-*s  %s" % (w, "check", "  ".join("%-12s" % n for n in names)))
    for k in ids:
        log("%-*s  %s" % (w, k, "  ".join("%-12s" % cell(get(r, k)) for r in results)))
        if a.v:
            for r in results:
                g = get(r, k)
                if g and g["detail"]:
                    log("    %-12s %s" % (r["variant"], g["detail"]))
    if a.v:
        for r in results:
            log("locks of A in %s:\n%s" % (r["variant"], r.get("locks_A", "")))
    left = []
    for k in before:
        new = after[k] - before[k]
        if k == "/tmp entries" or k == "tmp root entries":
            new = {x for x in new if "channels-1127" in x or "aosd" in x or "aos-daemon" in x}
        if new:
            left.append("%s: %s" % (k, sorted(new)))
    log("")
    log("cleanup: " + ("ok (nothing new: processes, mounts, units, cgroups, /tmp, SysV IPC, mqueue, /dev/shm)" if not left
                       else "LEFT OVER " + "; ".join(left)))
    if a.json:
        with open(a.json, "w") as f:
            json.dump(results, f, indent=1)
    log("SUMMARY %d variants run, %d failed%s" % (len(results), len(failed), (": " + " ".join(failed)) if failed else ""))
    return 1 if failed or left else 0


if __name__ == "__main__":
    sys.exit(main())
