"""daemon.py: the sky-1125 toy daemon: PID 1 of its own PID namespace and the only program here that touches Linux power; it starts procs in skies built from sky configs, keeps each proc's want-table, holds the kernel board (provides and depends), changes a running sky on an explicit command, and freezes procs through cgroups."""
import argparse, json, os, posixpath, re, select, signal, socket, stat, sys, time, traceback

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sky  # noqa: E402
from sky import Refused  # noqa: E402

STUB = '''#!/usr/bin/python3 -I
# exec stub put here by the sky daemon: running {path} hands the call to kernel {kernel} through {sock}
import json, os, socket, sys
c = socket.socket(socket.AF_UNIX)
try:
    c.connect({sock!r})
except OSError as e:
    sys.exit(f"{path}: kernel {kernel} is not answering: {{e.strerror}}")
socket.send_fds(c, [json.dumps({{"argv": sys.argv, "cwd": os.getcwd()}}).encode()], [0, 1, 2])
reply = c.makefile("rb").readline()
sys.exit(int(reply) if reply.strip() else 1)
'''


def find_cycle(graph, start):
    """A dependency path from start back to start, or None."""
    stack, seen = [(start, [start])], set()
    while stack:
        node, path = stack.pop()
        for d in graph.get(node, []):
            if d == start:
                return path + [d]
            if d not in seen:
                seen.add(d)
                stack.append((d, path + [d]))
    return None


def read_all(fd, timeout=10):
    """Everything the child writes before it closes the pipe (an exec closes it); '' means it went fine."""
    data, end = b"", time.monotonic() + timeout
    try:
        while True:
            left = end - time.monotonic()
            if left <= 0 or not select.select([fd], [], [], left)[0]:
                return (data + b" (timed out waiting for the child)").decode(errors="replace")
            chunk = os.read(fd, 4096)
            if not chunk:
                return data.decode(errors="replace")
            data += chunk
    finally:
        os.close(fd)


class Daemon:
    def __init__(self, tmp, toys, cgroup_unit):
        self.tmp, self.toys, self.run = tmp, toys, tmp + "/run"
        self.sock = tmp + "/daemon.sock"
        self.cgroup_unit = cgroup_unit
        self.procs = {}   # name -> record (pid, starter, rows = the want-table, uid, net, state, ...)
        self.board = {}   # kernel name -> {"provides": [...], "depends": [...]}
        self.options = {"no_cycles": False}
        self.cg = None

    def log(self, **kv):
        print(json.dumps(kv), flush=True)

    def setup(self):
        # Everything the daemon makes lives on a tmpfs inside its own mount namespace: it is gone when we are.
        os.makedirs(self.run, exist_ok=True)
        sky.mount("tmpfs", self.run, "tmpfs", sky.MS_NOSUID | sky.MS_NODEV, "mode=0755")
        for d in ("procs", "names", "roots", "shared"):
            os.mkdir(f"{self.run}/{d}")
        os.chmod(f"{self.run}/shared", 0o1777)
        # Procs run as the same uid as us; without this they could read /proc/1/root, which is the real system.
        sky.set_dumpable(False)
        cg = open("/proc/self/cgroup").read().strip().split("::", 1)[-1]
        if self.cgroup_unit and cg.endswith("/" + self.cgroup_unit) and os.access(f"/sys/fs/cgroup{cg}/cgroup.procs", os.W_OK):
            self.cg = "/sys/fs/cgroup" + cg  # only ever a cgroup that systemd delegated to this very run

    def names(self, self_dir=None):
        n = {"TOYS": self.toys, "RUN": self.run, "TMP": self.tmp, "DAEMON": self.sock}
        if self_dir:
            n["SELF"] = self_dir
        return n

    def proc(self, name):
        if name not in self.procs:
            raise Refused(f"no proc named {name}")
        return self.procs[name]

    def proc_of(self, pid):
        """Which of my procs a pid belongs to: the proc itself or one of its descendants."""
        by_pid = {p["pid"]: n for n, p in self.procs.items() if p["state"] == "running"}
        for _ in range(64):
            if pid in by_pid:
                return by_pid[pid]
            if pid <= 1:
                return None
            try:
                with open(f"/proc/{pid}/status") as f:
                    pid = int(next(l for l in f if l.startswith("PPid:")).split()[1])
            except (OSError, StopIteration):
                return None
        return None

    def may_change(self, p, caller):
        if caller and caller != p["starter"]:
            raise Refused(f"only the user or {p['name']}'s starter ({p['starter']}) may do that")

    # ------------------------------------------------------------ ops (one JSON request per connection)

    def op_ping(self, req, caller):
        return {"ok": True, "pid": os.getpid(), "cgroup": self.cg, "landlock": sky.landlock_abi()}

    def op_spawn(self, req, caller):
        name, argv, lines = req.get("name", ""), req.get("argv"), req.get("sky", [])
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,30}", name):
            raise Refused(f"bad proc name {name!r}")
        if name in self.procs:
            raise Refused(f"{name} already exists")
        if not argv or not all(isinstance(a, str) for a in argv):
            raise Refused("argv must be a non-empty list of strings")
        starter = self.procs[caller] if caller else None
        self_dir = f"{self.run}/procs/{name}"
        rows, cfg = sky.compose(lines, starter, {"self_dir": self_dir, "names": self.names(self_dir), "board": self.board})
        uid, gid = cfg["uid"], cfg["gid"]
        os.makedirs(self_dir, 0o700, exist_ok=True)
        os.chown(self_dir, uid, gid)
        for r in rows:  # names given to a kernel: a stub program in an overlay layer of their own
            if r["kind"] == "kexec":
                at, base = posixpath.split(r["path"])
                layer = f"{self.run}/names/{name}{at}"
                os.makedirs(layer, exist_ok=True)
                with open(f"{layer}/{base}", "w") as f:
                    f.write(STUB.format(path=r["path"], kernel=r["kernel"], sock=r["sock"]))
                os.chmod(f"{layer}/{base}", 0o755)
                r["layer"] = layer
        root = f"{self.run}/roots/{name}"
        os.makedirs(root, exist_ok=True)
        join_net = f"/proc/{starter['pid']}/ns/net" if cfg["net"] == "join" else None
        cg = f"{self.cg}/sky-{name}" if self.cg else None
        if cg:
            os.mkdir(cg)
        has_self = any(r["path"] == "/self" for r in rows)
        env = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "HOME": "/self" if has_self else "/", "SKY_NAME": name}
        logfd = os.open(f"{self.tmp}/logs/{name}.log", os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        nullfd = os.open("/dev/null", os.O_RDONLY)
        rd, wr = os.pipe()
        sys.stdout.flush()
        sys.stderr.flush()
        pid = os.fork()
        if pid == 0:
            try:
                os.close(rd)
                os.dup2(nullfd, 0)
                os.dup2(logfd, 1)
                os.dup2(logfd, 2)
                if cg:
                    with open(f"{cg}/cgroup.procs", "w") as f:
                        f.write("0")
                sky.build(rows, root, cfg["net"], join_net)
                sky.enter(argv, env, uid, gid, cfg["lock"], "/self" if has_self else "/")
            except BaseException as e:
                try:
                    os.write(wr, f"{type(e).__name__}: {e}".encode())
                    traceback.print_exc()
                finally:
                    os._exit(127)
        os.close(wr)
        os.close(logfd)
        os.close(nullfd)
        err = read_all(rd)
        if err:
            os.waitpid(pid, 0)
            if cg:
                os.rmdir(cg)
            raise Refused(f"building the sky failed: {err}")
        self.procs[name] = {"name": name, "pid": pid, "starter": caller or "user", "rows": rows, "uid": uid, "gid": gid,
                            "net": cfg["net"], "lock": cfg["lock"], "state": "running", "exit": None, "cg": cg}
        self.log(event="spawned", name=name, pid=pid, starter=caller or "user", rows=len(rows), net=cfg["net"], uid=uid, lock=cfg["lock"])
        return {"ok": True, "pid": pid}

    def op_ns(self, req, caller):
        p = self.proc(req.get("name"))
        return {"ok": True, "rows": p["rows"], "settings": {k: p[k] for k in ("starter", "uid", "gid", "net", "lock", "state")}}

    def op_status(self, req, caller):
        procs = {n: {k: p[k] for k in ("pid", "starter", "state", "exit", "uid", "gid", "net", "cg")} for n, p in self.procs.items()}
        return {"ok": True, "procs": procs, "board": self.board, "options": self.options, "cgroup": self.cg}

    def op_whois(self, req, caller):
        return {"ok": True, "name": self.proc_of(int(req["pid"]))}

    def op_register(self, req, caller):
        """A proc offers names (provide); it says which kernels it uses (depends). The proc is the kernel's name."""
        if caller is None:
            raise Refused("only a proc can be a kernel")
        me = self.procs[caller]
        provides = []
        for p in req.get("provides", []):
            if p.get("kind") not in ("exec", "socket"):
                raise Refused("kind must be exec or socket")
            have, rel = sky.resolve_in(me["rows"], p["sock"], caller)
            try:
                fd = sky.open_beneath(have["base"], rel)
            except OSError as e:
                raise Refused(f"{p['sock']}: {e.strerror}")
            try:
                if not stat.S_ISSOCK(os.fstat(fd).st_mode):
                    raise Refused(f"{p['sock']} is not a socket")
            finally:
                os.close(fd)
            provides.append({"path": sky.norm(p["path"]), "kind": p["kind"], "base": have["base"], "rel": rel})
        if not provides:
            raise Refused("a kernel must provide something")
        depends = [str(d) for d in req.get("depends", [])]
        if self.options["no_cycles"]:
            graph = {k: v["depends"] for k, v in self.board.items()}
            graph[caller] = depends
            cycle = find_cycle(graph, caller)
            if cycle:
                raise Refused("dependency cycle " + " -> ".join(cycle) + " (option no_cycles is on)")
        self.board[caller] = {"provides": provides, "depends": depends}
        used = sorted({r["kernel"] for r in me["rows"] if r.get("kernel")})
        return {"ok": True, "undeclared": [k for k in used if k not in depends]}

    def op_deps(self, req, caller):
        """Every kernel a kernel needs, directly or not; a cycle and unregistered ones are named, nothing is refused."""
        graph = {k: v["depends"] for k, v in self.board.items()}
        chain, missing, cycle = [], [], None

        def walk(k, path):
            nonlocal cycle
            if k in path:
                cycle = cycle or path[path.index(k):] + [k]
                return
            if k in chain:
                return
            chain.append(k)
            if k not in graph:
                missing.append(k)
                return
            for d in graph[k]:
                walk(d, path + [k])

        walk(req["kernel"], [])
        return {"ok": True, "kernel": req["kernel"], "chain": chain, "cycle": cycle, "missing": missing}

    def op_set(self, req, caller):
        if caller:
            raise Refused("only the user can change daemon options")
        for k, v in req.get("options", {}).items():
            if k not in self.options:
                raise Refused(f"unknown option {k}")
            self.options[k] = bool(v)
        return {"ok": True, "options": self.options}

    def op_mount(self, req, caller):
        """An explicit change to a running sky: `bind [-w] SRC DST`, SRC as the requester sees it."""
        p = self.proc(req.get("name"))
        if p["state"] != "running":
            raise Refused(f"{p['name']} is not running")
        self.may_change(p, caller)
        words = req.get("line", "").split()
        mode = "ro"
        if words[1:2] == ["-w"]:
            mode, words = "rw", words[:1] + words[2:]
        if words[:1] != ["bind"] or len(words) != 3:
            raise Refused("a live change is `bind [-w] SRC DST`")
        dst = sky.norm(words[2])
        if caller is None:
            base, rel = sky.norm(sky.expand(words[1], self.names())), ""
            if not os.path.lexists(base):
                raise Refused(f"{base} does not exist")
        else:
            have, rel = sky.resolve_in(self.procs[caller]["rows"], words[1], caller)
            if mode == "rw" and have["mode"] != "rw":
                raise Refused(f"{words[1]} is read-only in {caller}'s sky")
            base = have["base"]
        if any(r["path"] == dst for r in p["rows"]):
            raise Refused(f"{dst} is already in {p['name']}'s sky")
        rd, wr = os.pipe()
        sys.stdout.flush()
        sys.stderr.flush()
        pid = os.fork()
        if pid == 0:
            try:
                os.close(rd)
                sky.live_bind(p["pid"], base, rel, dst, mode == "ro")
            except BaseException as e:
                os.write(wr, f"{type(e).__name__}: {e}".encode())
            os._exit(0)
        os.close(wr)
        err = read_all(rd)
        os.waitpid(pid, 0)
        if err:
            raise Refused(f"live mount failed: {err}")
        row = {"path": dst, "kind": "bind", "base": base, "rel": rel, "mode": mode, "by": f"live:{caller or 'user'}"}
        p["rows"].append(row)
        self.log(event="live-mount", name=p["name"], path=dst, src=sky.src_of(row), by=caller or "user")
        return {"ok": True, "row": row}

    def op_freeze(self, req, caller, value=1):
        """The rough tool that works on any program: cgroup v2 freeze (and thaw)."""
        p = self.proc(req.get("name"))
        self.may_change(p, caller)
        if not p["cg"]:
            raise Refused("no cgroup: the daemon was not started inside a delegated cgroup")
        with open(f"{p['cg']}/cgroup.freeze", "w") as f:
            f.write(str(value))
        end, frozen = time.monotonic() + 2, None
        while time.monotonic() < end:
            with open(f"{p['cg']}/cgroup.events") as f:
                frozen = dict(l.split() for l in f).get("frozen")
            if frozen == str(value):
                break
            time.sleep(0.02)
        return {"ok": True, "frozen": frozen}

    def op_thaw(self, req, caller):
        return self.op_freeze(req, caller, 0)

    def op_stop(self, req, caller):
        p = self.proc(req.get("name"))
        self.may_change(p, caller)
        if p["state"] == "running":
            os.kill(p["pid"], signal.SIGTERM)
        return {"ok": True}

    # ------------------------------------------------------------ the loop

    def answer(self, conn):
        req, caller = {}, None
        try:
            conn.settimeout(5)
            pid, _, _ = sky.peer(conn)
            caller = None if pid == 0 else self.proc_of(pid)  # pid 0: the peer is outside our PID namespace = the user
            if pid != 0 and caller is None:
                raise Refused(f"pid {pid} is not one of my procs")
            req = json.loads(conn.makefile("rb").readline() or b"{}")
            fn = getattr(self, "op_" + str(req.get("op")), None)
            if fn is None:
                raise Refused(f"unknown op {req.get('op')!r}")
            resp = fn(req, caller)
        except Refused as e:
            resp = {"ok": False, "error": str(e)}
        except Exception as e:  # a toy: report, keep serving
            traceback.print_exc()
            resp = {"ok": False, "error": f"{type(e).__name__}: {e}"}
        if req.get("op") not in ("status", "ping", "whois", "ns"):
            self.log(event="op", op=req.get("op"), caller=caller or "user", ok=resp.get("ok"), error=resp.get("error"))
        try:
            conn.sendall(json.dumps(resp).encode() + b"\n")
        except OSError:
            pass

    def reap(self):
        while True:
            try:
                pid, status = os.waitpid(-1, os.WNOHANG)
            except ChildProcessError:
                return
            if pid == 0:
                return
            for n, p in self.procs.items():
                if p["pid"] == pid and p["state"] == "running":
                    p["state"], p["exit"] = "exited", os.waitstatus_to_exitcode(status)
                    left = self.board.pop(n, None) is not None
                    if p["cg"]:
                        try:
                            os.rmdir(p["cg"])
                        except OSError:
                            pass
                    self.log(event="exited", name=n, pid=pid, exit=p["exit"], left_board=left)

    def serve(self):
        lst = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        lst.bind(self.sock)
        os.chmod(self.sock, 0o600)
        lst.listen(32)
        rfd, wfd = os.pipe()
        os.set_blocking(wfd, False)
        signal.set_wakeup_fd(wfd)
        signal.signal(signal.SIGCHLD, lambda *_: None)
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))  # PID 1 ignores signals it has no handler for
        self.log(event="up", pid=os.getpid(), run=self.run, cgroup=self.cg)
        while True:
            ready = select.select([lst, rfd], [], [], 1.0)[0]
            if rfd in ready:
                os.read(rfd, 4096)
            self.reap()
            if lst in ready:
                conn, _ = lst.accept()
                with conn:
                    self.answer(conn)


def main():
    ap = argparse.ArgumentParser(description="sky-1125 toy daemon (start it as PID 1 of a new PID namespace)")
    ap.add_argument("--tmp", required=True, help="scratch dir of this run (daemon.sock, logs/, run/)")
    ap.add_argument("--toys", required=True, help="the experiment folder (bound into skies as $TOYS)")
    ap.add_argument("--cgroup-unit", help="systemd scope this run was delegated (cgroup tools are off without it)")
    a = ap.parse_args()
    if os.getpid() != 1:
        sys.exit("daemon.py: must be PID 1 of its own PID namespace (start it under unshare --pid --fork)")
    d = Daemon(a.tmp, a.toys, a.cgroup_unit)
    d.setup()
    d.serve()


if __name__ == "__main__":
    main()
