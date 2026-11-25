"""toys.py: the toy programs of sky-1125: kernels (draw-kernel, perm-kernel, llm-proxy, plain ring kernels), procs (leader, drawer, watcher, locktest, idtest, ticker, netless) and the fake upstream LLM API that runs outside every sky."""
import errno, http.client, http.server, json, os, shutil, socket, socketserver, subprocess, sys, time

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sky  # noqa: E402

DAEMON = "/srv/daemon"          # where kernels and leader find the daemon in their sky
ME = os.environ.get("SKY_NAME", "?")
FIXED = {"id": "msg_fake_1", "type": "message", "role": "assistant", "model": "fake-upstream",
         "content": [{"type": "text", "text": "hello from the fake upstream"}],
         "usage": {"input_tokens": 12, "output_tokens": 30}}
TURTLE = r"""
        _____     ____
       /      \  |  o |
      |        |/ ___\|
      |_________/
      |_|_| |_|_|
"""


def say(**kv):
    """One JSON object per line on stdout (the proc's log): what run.py reads back."""
    print(json.dumps(kv), flush=True)


def daemon(req):
    return sky.call(DAEMON, req)


def whois(pid):
    try:
        return daemon({"op": "whois", "pid": pid}).get("name")
    except OSError:
        return None


def errname(fn):
    """Run fn: 'OK' (or what it returned) if it worked, else the errno name such as 'EPERM'."""
    try:
        r = fn()
        return "OK" if r is None else r
    except OSError as e:
        return errno.errorcode.get(e.errno, str(e.errno))


def forever():
    while True:
        time.sleep(3600)


def listen(path):
    s = socket.socket(socket.AF_UNIX)
    s.bind(path)
    s.listen(16)
    return s


def register(provides, depends=()):
    r = daemon({"op": "register", "provides": provides, "depends": list(depends)})
    say(event="registered" if r.get("ok") else "refused", reply=r)
    return r


# ---------------------------------------------------------------- kernels

def draw_kernel(args):
    """draw-kernel: provides the exec name /usr/bin/draw; answers by writing straight into the caller's stdout."""
    srv = listen("/self/draw.sock")
    register([{"path": "/usr/bin/draw", "kind": "exec", "sock": "/self/draw.sock"}])
    while True:
        conn, _ = srv.accept()
        with conn:
            pid, uid, _ = sky.peer(conn)          # filled in by Linux, the caller cannot fake it
            msg, fds, _, _ = socket.recv_fds(conn, 65536, 3)
            argv = json.loads(msg)["argv"]
            caller = whois(pid)
            os.close(fds[0])
            out, err = os.fdopen(fds[1], "w"), os.fdopen(fds[2], "w")
            if argv[1:2] == ["turtle"]:
                out.write(TURTLE.lstrip("\n"))
                out.write(f"drawn by draw-kernel (pid {os.getpid()}) for {caller} (pid {pid}, uid {uid})\n")
                rc = 0
            else:
                err.write("usage: draw turtle\n")
                rc = 2
            out.close()
            err.close()
            conn.sendall(f"{rc}\n".encode())
            say(event="drew", caller=caller, pid=pid, uid=uid, argv=argv, rc=rc)


def perm_kernel(args):
    """perm-kernel: provides /srv/perm (says allow to everything); depends on draw-kernel, whose draw it uses."""
    r = subprocess.run(["draw", "turtle"], capture_output=True, text=True, timeout=10)
    say(event="used-draw", rc=r.returncode, last=r.stdout.strip().splitlines()[-1:])
    srv = listen("/self/perm.sock")
    register([{"path": "/srv/perm", "kind": "socket", "sock": "/self/perm.sock"}], ["draw-kernel"])
    while True:
        conn, _ = srv.accept()
        with conn:
            conn.sendall(b"allow\n")


def llm_proxy(args):
    """llm-proxy: provides /srv/llm, an HTTP endpoint on a unix socket. It forwards to the upstream and counts the
    tokens itself, per caller, in /self/state.json: measured at the only way out, not claimed by the caller."""
    port = int(args[0])
    state = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "by_caller": {}}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            pid, _, _ = sky.peer(self.connection)
            caller = whois(pid) or f"pid {pid}"
            up = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
            up.request("POST", self.path, body, {"Content-Type": "application/json"})
            resp = up.getresponse()
            data = resp.read()
            usage = json.loads(data).get("usage", {})
            n_in, n_out = int(usage.get("input_tokens", 0)), int(usage.get("output_tokens", 0))
            state["calls"] += 1
            state["input_tokens"] += n_in
            state["output_tokens"] += n_out
            mine = state["by_caller"].setdefault(caller, {"calls": 0, "tokens": 0})
            mine["calls"] += 1
            mine["tokens"] += n_in + n_out
            with open("/self/state.json.tmp", "w") as f:
                json.dump(state, f)
            os.replace("/self/state.json.tmp", "/self/state.json")
            self.send_response(resp.status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            say(event="forwarded", caller=caller, input_tokens=n_in, output_tokens=n_out)

        def log_message(self, *a):
            pass

    srv = socketserver.UnixStreamServer("/self/llm.sock", Handler)
    register([{"path": "/srv/llm", "kind": "socket", "sock": "/self/llm.sock"}])
    srv.serve_forever()


def plain_kernel(args):
    """A toy kernel that only provides /srv/<its own name> and declares the dependencies given as arguments."""
    srv = listen("/self/k.sock")  # noqa: F841 (kept open so the socket stays alive)
    if not register([{"path": f"/srv/{ME}", "kind": "socket", "sock": "/self/k.sock"}], args).get("ok"):
        sys.exit(3)
    forever()


# ---------------------------------------------------------------- procs

def leader(args):
    """leader: asks the daemon about kernels, tries to hand drawer things it does not have (each one refused),
    then starts drawer as drawer.mods says (leader's own sky plus those changes)."""
    port = args[0]
    me = daemon({"op": "ns", "name": ME})
    say(event="my-sky", paths=sorted(r["path"] for r in me["rows"]))
    for k in ("draw-kernel", "llm-proxy", "perm-kernel", "ring-a"):
        d = daemon({"op": "deps", "kernel": k})
        decision = "skip: dependency cycle" if d.get("cycle") else "skip: not registered" if d.get("missing") else "ok"
        say(event="deps", kernel=k, chain=d.get("chain"), cycle=d.get("cycle"), missing=d.get("missing"), decision=decision)
    os.symlink("/home", "/self/escape")  # leader has no /home; seen from the daemon this is the user's real home
    tries = [("not-in-sky", "bind /var /var"), ("rw-upgrade", "bind -w /toys /toys"),
             ("symlink-escape", "bind /self/escape /hostroot"), ("other-uid", "uid 1001"),
             ("unlock", "lock off"), ("has-it", "bind /toys /opt/toys2")]
    for case, line in tries:
        argv = ["/usr/bin/python3", "-I", "-c", "import os; print('listing', sorted(os.listdir('/opt/toys2')))"]
        r = daemon({"op": "spawn", "name": f"try-{case}", "sky": [["leader", line]], "argv": argv})
        say(event="handdown", case=case, line=line, ok=r.get("ok"), error=r.get("error"))
    mods = sky.load_config("/toys/drawer.mods")
    r = daemon({"op": "spawn", "name": "drawer", "sky": mods, "argv": ["/usr/bin/python3", "-I", "-B", "/toys/toys.py", "drawer", port]})
    say(event="started-drawer", ok=r.get("ok"), error=r.get("error"))
    say(event="done")
    forever()


class UnixHTTP(http.client.HTTPConnection):
    def __init__(self, path):
        super().__init__("llm", timeout=10)
        self.unix_path = path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX)
        self.sock.settimeout(10)
        self.sock.connect(self.unix_path)


def drawer(args):
    """drawer: runs `draw turtle` (answered by draw-kernel), checks that it has no network of its own,
    and asks the llm three times through /srv/llm, the only way out."""
    port = int(args[0])
    r = subprocess.run(["draw", "turtle"], capture_output=True, text=True, timeout=10)
    say(event="draw", rc=r.returncode, out=r.stdout, err=r.stderr, path=shutil.which("draw"))
    say(event="sky", daemon_socket=os.path.exists("/srv/daemon"), llm_socket=os.path.exists("/srv/llm"))
    with open("/proc/net/dev") as f:
        ifaces = [l.split(":")[0].strip() for l in f.read().splitlines()[2:]]
    direct = errname(lambda: socket.create_connection(("127.0.0.1", port), timeout=2).close())
    # 192.0.2.1 is a documentation address (RFC 5737); it is only tried when lo is the only interface,
    # so the attempt cannot leave the machine
    outside = errname(lambda: socket.create_connection(("192.0.2.1", 80), timeout=2).close()) if ifaces == ["lo"] else "not tried"
    say(event="net", ifaces=ifaces, direct_to_upstream=direct, outside=outside)
    total = 0
    for i in range(3):
        c = UnixHTTP("/srv/llm")
        req = {"model": "fake", "max_tokens": 16, "messages": [{"role": "user", "content": f"hi {i}"}]}
        c.request("POST", "/v1/messages", json.dumps(req), {"Content-Type": "application/json"})
        usage = json.loads(c.getresponse().read())["usage"]
        c.close()
        total += usage["input_tokens"] + usage["output_tokens"]
        say(event="llm", i=i, usage=usage)
    say(event="llm-total", tokens=total)
    say(event="done")
    forever()


def watcher(args):
    """watcher: does nothing but wait for /srv/new/hello.txt to appear in its sky while it runs."""
    say(event="watching", srv=os.path.exists("/srv"))
    while not os.path.exists("/srv/new/hello.txt"):
        time.sleep(0.05)
    with open("/srv/new/hello.txt") as f:
        say(event="seen", text=f.read().strip())
    forever()


def caps():
    keep = ("Uid", "CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb", "NoNewPrivs")
    with open("/proc/self/status") as f:
        return {k: v.strip() for k, _, v in (l.partition(":") for l in f) if k in keep}


def run_rc(argv):
    r = subprocess.run(argv, capture_output=True, text=True)
    return {"rc": r.returncode, "said": (r.stderr or r.stdout).strip()[:100]}


def in_child(fn):
    """errname(fn) in a forked child, so this process stays as it is."""
    rd, wr = os.pipe()
    pid = os.fork()
    if pid == 0:
        os.close(rd)
        os.write(wr, str(errname(fn)).encode())
        os._exit(0)
    os.close(wr)
    out = os.read(rd, 300).decode()
    os.close(rd)
    os.waitpid(pid, 0)
    return out


def own_namespace_umount():
    os.unshare(os.CLONE_NEWUSER | os.CLONE_NEWNS)  # a user namespace of its own: full caps again, in there
    return ("unshare OK, then umount " + errname(lambda: sky.umount2("/usr"))
            + ", mount a tmpfs on /tmp " + errname(lambda: sky.mount("none", "/tmp", "tmpfs")))


def connect_abstract(name):
    s = socket.socket(socket.AF_UNIX)
    try:
        s.connect("\0" + name)
    finally:
        s.close()


def securebits():
    return sky.libc.prctl(27, 0, 0, 0, 0)  # PR_GET_SECUREBITS


def locktest(args):
    """locktest: tries to undo its own sky (unmount, mount, a namespace of its own) and to look into the daemon's
    and a sibling's sky. 'locked' must fail at all of it; 'unlocked' is the control, plus the caps-only pitfall
    (run.py also starts one 'locked' with `lock nolandlock`, to show what the Landlock domain adds)."""
    mode, sibling, abstract = args[0], int(args[1]), args[2]
    res = {"caps": caps(), "securebits": securebits(),
           "abstract_socket": errname(lambda: connect_abstract(abstract))}  # e.g. an X11 or D-Bus socket of the host
    if mode == "locked":
        res["umount_syscall"] = errname(lambda: sky.umount2("/usr"))
        res["mount_syscall"] = errname(lambda: sky.mount("none", "/tmp", "tmpfs"))
        res["umount_cmd"] = run_rc(["umount", "/toys"])
        res["mount_cmd"] = run_rc(["mount", "-t", "tmpfs", "none", "/tmp"])
        res["own_userns"] = in_child(own_namespace_umount)
        res["daemon_root"] = errname(lambda: (os.listdir("/proc/1/root"), None)[1])
        res["sibling_root"] = errname(lambda: (os.listdir(f"/proc/{sibling}/root"), None)[1])
        res["sibling_environ"] = errname(lambda: (open(f"/proc/{sibling}/environ").read(), None)[1])  # API keys live here
        res["signal_sibling"] = errname(lambda: os.kill(sibling, 0))
    else:
        res["umount_cmd"] = run_rc(["umount", "/toys"])
        res["daemon_root"] = errname(lambda: " ".join(sorted(os.listdir("/proc/1/root"))[:5]))
        sky.drop_caps()                                   # caps to zero, nothing else
        res["caps_after_drop"] = caps()
        res["umount_syscall_after_drop"] = errname(lambda: sky.umount2("/tmp"))
        res["umount_cmd_after_drop"] = run_rc(["umount", "/tmp"])   # an execve: uid 0 gets every cap back
    say(event="locktest", mode=mode, **res)
    forever()


def idtest(args):
    """idtest: alice keeps a private file in /shared; bob (another uid, same /shared) tries to read and write it."""
    p = "/shared/alice.txt"
    if args[0] == "alice":
        fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.write(fd, b"alice's secret\n")
        os.close(fd)
        with open(p) as f:
            say(event="alice", uid=os.getuid(), gid=os.getgid(), read_own=f.read().strip())
    else:
        while not os.path.exists(p):
            time.sleep(0.05)
        st = os.stat(p)
        say(event="bob", uid=os.getuid(), gid=os.getgid(), file_uid=st.st_uid, file_mode=oct(st.st_mode & 0o777),
            read=errname(lambda: (open(p).read(), None)[1]), write=errname(lambda: (open(p, "a").close(), None)[1]))
    forever()


def ticker(args):
    """ticker: a plain program with no interface at all; it only prints a counter."""
    i = 0
    while True:
        print(f"tick {i}", flush=True)
        i += 1
        time.sleep(0.05)


def netless(args):
    """netless: a proc with no network of its own that tries to give its child the host network."""
    r = daemon({"op": "spawn", "name": "try-net-host", "sky": [["netless", "net host"]], "argv": ["true"]})
    say(event="handdown", case="net-widen", line="net host", ok=r.get("ok"), error=r.get("error"))
    forever()


# ---------------------------------------------------------------- outside every sky

def upstream(args):
    """The fake upstream LLM API, on 127.0.0.1 only: every POST gets the same JSON with a usage block."""
    port_file = args[0]

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            data = json.dumps(FIXED).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            say(event="request", peer=self.client_address[0], path=self.path)

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    with open(port_file + ".tmp", "w") as f:
        f.write(str(srv.server_address[1]))
    os.replace(port_file + ".tmp", port_file)
    srv.serve_forever()


COMMANDS = {"draw-kernel": draw_kernel, "perm-kernel": perm_kernel, "llm-proxy": llm_proxy, "kernel": plain_kernel,
            "leader": leader, "drawer": drawer, "watcher": watcher, "locktest": locktest, "idtest": idtest,
            "ticker": ticker, "netless": netless, "upstream": upstream}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        sys.exit("usage: toys.py " + "|".join(COMMANDS) + " [args]")
    COMMANDS[sys.argv[1]](sys.argv[2:])
