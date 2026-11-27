#!/usr/bin/env python3
"""What accept.py and stack_test.py run inside a mini sandbox instead of pi: one subcommand per check (check = several at once), one json line out (standard library only, so it also runs as python3 -I -c SOURCE where your home is closed)."""

import glob
import json
import os
import socket
import subprocess
import sys
import time


def out(**kw):
    print(json.dumps(kw), flush=True)


def err(e):
    return "%s: %s" % (type(e).__name__, getattr(e, "strerror", None) or e)


def cpu(secs):
    t0, c0 = time.monotonic(), time.process_time()
    while time.monotonic() - t0 < float(secs):
        pass
    wall, used = time.monotonic() - t0, time.process_time() - c0
    out(wall=round(wall, 2), cpu=round(used, 2), ratio=round(used / wall, 3))


def mem(mb):
    chunks = []
    for i in range(int(mb)):
        chunks.append(bytearray(1024 * 1024))
        if i % 20 == 0:
            print("allocated %d MB" % i, file=sys.stderr, flush=True)
    out(allocated_mb=int(mb))


def pids(n):
    kids, error = [], None
    for _ in range(int(n)):
        try:
            pid = os.fork()
        except OSError as e:
            error = err(e)
            break
        if pid == 0:
            time.sleep(30)
            os._exit(0)
        kids.append(pid)
    for k in kids:
        os.kill(k, 9)
        os.waitpid(k, 0)
    out(forked=len(kids), error=error)


def cgroup(unit):
    """Try to raise our own memory.max and to move out of our cgroup (both must fail with -C)."""
    own = open("/proc/self/cgroup").read().strip()
    found = glob.glob("/sys/fs/cgroup/user.slice/user-*.slice/user@*.service/*/" + unit)
    r = {"self_cgroup": own, "scope_dir": found[0] if found else None}
    if not found:
        return out(**r)
    d = found[0]
    try:
        with open(os.path.join(d, "memory.max"), "w") as f:
            f.write("999M")
        r["raise_mem"] = "ok: " + open(os.path.join(d, "memory.max")).read().strip()
    except OSError as e:
        r["raise_mem"] = err(e)
    esc = os.path.join(os.path.dirname(d), unit.replace(".scope", "-escape"))
    try:
        os.mkdir(esc)
        try:
            with open(os.path.join(esc, "cgroup.procs"), "w") as f:
                f.write("0")
            r["move_out"] = "ok: now " + open("/proc/self/cgroup").read().strip()
        except OSError as e:
            r["move_out"] = err(e)
    except OSError as e:
        r["move_out"] = "mkdir " + err(e)
    finally:
        try:
            os.rmdir(esc)
        except OSError:
            pass
    out(**r)


def procs(host_pid):
    ps = sorted(int(p) for p in os.listdir("/proc") if p.isdigit())
    out(count=len(ps), pids=ps[:20], sees_host_pid=os.path.exists("/proc/%s" % host_pid))


def tcp(host, port, timeout=3):
    t0 = time.monotonic()
    try:
        s = socket.create_connection((host, int(port)), timeout=float(timeout))
        s.close()
        out(connect="ok", seconds=round(time.monotonic() - t0, 2))
    except OSError as e:
        out(connect=err(e), seconds=round(time.monotonic() - t0, 2))


def http_get(host, port, n, max_time):
    """GET /bytes/N from accept's test server; count bytes until the end or max_time."""
    t0 = time.monotonic()
    got, error = 0, None
    try:
        s = socket.create_connection((host, int(port)), timeout=5)
        s.settimeout(float(max_time))
        s.sendall(("GET /bytes/%s HTTP/1.0\r\nHost: x\r\n\r\n" % n).encode())
        head = b""
        while b"\r\n\r\n" not in head:
            c = s.recv(65536)
            if not c:
                break
            head += c
        got = len(head.split(b"\r\n\r\n", 1)[1]) if b"\r\n\r\n" in head else 0
        deadline = t0 + float(max_time)
        while time.monotonic() < deadline:
            s.settimeout(max(0.05, deadline - time.monotonic()))
            c = s.recv(1 << 20)
            if not c:
                break
            got += len(c)
        else:
            error = "max_time"
        s.close()
    except OSError as e:
        error = err(e)
    sec = time.monotonic() - t0
    out(bytes=got, seconds=round(sec, 2), rate=round(got / sec) if sec else 0, error=error)


def http_put(host, port, n, max_time):
    """POST N bytes to /upload; the server answers how many it read."""
    t0 = time.monotonic()
    sent, error, answer = 0, None, None
    try:
        s = socket.create_connection((host, int(port)), timeout=5)
        s.settimeout(float(max_time))
        s.sendall(("POST /upload HTTP/1.0\r\nHost: x\r\nContent-Length: %s\r\n\r\n" % n).encode())
        block = b"u" * 65536
        while sent < int(n):
            k = min(len(block), int(n) - sent)
            s.sendall(block[:k])
            sent += k
        resp = b""
        while True:
            c = s.recv(4096)
            if not c:
                break
            resp += c
        answer = resp.decode(errors="replace").split("\r\n\r\n", 1)[-1].strip()
        s.close()
    except OSError as e:
        error = err(e)
    sec = time.monotonic() - t0
    out(bytes=sent, seconds=round(sec, 2), rate=round(sent / sec) if sec else 0, server=answer, error=error)


def curl(url, max_time=5):
    r = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", str(max_time), url],
                       capture_output=True, text=True)
    out(code=r.stdout.strip(), rc=r.returncode)


def run(*argv):
    r = subprocess.run(list(argv), capture_output=True, text=True)
    out(rc=r.returncode, out=(r.stdout + r.stderr).strip()[-300:])


def ns():
    r = {}
    for n in ("user", "net", "ipc", "pid", "mnt", "cgroup"):
        r[n] = os.readlink("/proc/self/ns/" + n)
    r["ifaces"] = sorted(n for _, n in socket.if_nameindex())  # netlink: this netns (/sys/class/net is the host's)
    out(**r)


def leaks(unit, outfile):
    """What is left open on purpose (info): ~/.ssh, /run/user/UID, and systemd --user starting a process for us."""
    out(**leaks_dict(unit, outfile))


def leaks_dict(unit, outfile):
    r = {}
    home = os.environ.get("HOME", "/")
    try:
        names = os.listdir(os.path.join(home, ".ssh"))
        r["ssh_dir"] = "listed %d entries" % len(names)
        key = next((n for n in names if n.startswith("id_") and not n.endswith(".pub")), None)
        if key:
            with open(os.path.join(home, ".ssh", key), "rb") as f:
                r["ssh_key"] = "read %d bytes of %s" % (len(f.read(64)), key)
    except OSError as e:
        r["ssh_dir"] = err(e)
    rd = "/run/user/%d" % os.getuid() if os.getuid() else os.environ.get("XDG_RUNTIME_DIR", "")
    try:
        r["run_user"] = "%s: %d entries, systemd/private %s" % (rd, len(os.listdir(rd)), "exists" if os.path.exists(
            os.path.join(rd, "systemd", "private")) else "missing")
    except OSError as e:
        r["run_user"] = err(e)
    r["ipc"] = os.readlink("/proc/self/ns/ipc")
    r["net"] = os.readlink("/proc/self/ns/net")
    script = "{ readlink /proc/self/ns/net; cat /proc/self/cgroup; } > %s; sleep 60" % outfile
    p = subprocess.run(["systemd-run", "--user", "--quiet", "--collect", "--unit", unit, "sh", "-c", script],
                       capture_output=True, text=True)
    r["systemd_run"] = "rc %d %s" % (p.returncode, (p.stdout + p.stderr).strip()[-200:])
    if p.returncode != 0:  # the same request straight over the session bus (what systemd-run sends)
        p = subprocess.run(["busctl", "--user", "call", "--", "org.freedesktop.systemd1", "/org/freedesktop/systemd1",
                            "org.freedesktop.systemd1.Manager", "StartTransientUnit", "ssa(sv)a(sa(sv))", unit, "fail",
                            "2", "ExecStart", "a(sasb)", "1", "/bin/sh", "3", "/bin/sh", "-c", script, "false",
                            "CollectMode", "s", "inactive-or-failed", "0"], capture_output=True, text=True)
        r["busctl"] = "rc %d %s" % (p.returncode, (p.stdout + p.stderr).strip()[-200:])
    return r


def ctl(sock, pid):
    """Ask the net kernel for another veth from inside (must be refused)."""
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(5)
        s.connect(sock)
        s.sendall((json.dumps({"op": "attach", "pid": int(pid)}) + "\n").encode())
        out(answer=json.loads(s.makefile().readline()))
    except (OSError, ValueError) as e:
        out(answer=err(e))


def read(path):
    try:
        with open(path, "rb") as f:
            out(read="ok %d bytes" % len(f.read()))
    except OSError as e:
        out(read=err(e))


def check(spec):
    """Several checks in one sandbox (stack_test.py); spec is a json object, each key optional:
    secret PATH, cpu SECONDS, pids N, mem MB, tcp [[HOST, PORT], ...], get [HOST, PORT, BYTES, MAX_TIME],
    escape [UNIT, OUTFILE], umount PATH."""
    s = json.loads(spec)
    r = {"uid": os.getuid(), "cgroup": open("/proc/self/cgroup").read().strip(),
         "ifaces": sorted(n for _, n in socket.if_nameindex())}
    if "secret" in s:
        try:
            with open(s["secret"]) as f:
                r["secret"] = "read %d bytes" % len(f.read())
        except OSError as e:
            r["secret"] = err(e)
    if "cpu" in s:
        t0, c0 = time.monotonic(), time.process_time()
        while time.monotonic() - t0 < float(s["cpu"]):
            pass
        r["cpu_ratio"] = round((time.process_time() - c0) / (time.monotonic() - t0), 3)
    if "pids" in s:
        kids, error = [], None
        for _ in range(int(s["pids"])):
            try:
                pid = os.fork()
            except OSError as e:
                error = err(e)
                break
            if pid == 0:
                time.sleep(30)
                os._exit(0)
            kids.append(pid)
        for k in kids:
            os.kill(k, 9)
            os.waitpid(k, 0)
        r["forked"], r["fork_error"] = len(kids), error
    if "mem" in s:
        rd, wr = os.pipe()
        pid = os.fork()
        if pid == 0:
            os.close(rd)
            chunks = []
            for i in range(1, int(s["mem"]) + 1):
                chunks.append(bytearray(1024 * 1024))
                if i % 10 == 0:
                    os.write(wr, b"%d\n" % i)
            os._exit(0)
        os.close(wr)
        got = b""
        while True:
            c = os.read(rd, 4096)
            if not c:
                break
            got += c
        _, st = os.waitpid(pid, 0)
        r["mem_reached_mb"] = int(got.split()[-1]) if got.split() else 0
        r["mem_end"] = "killed by signal %d" % os.WTERMSIG(st) if os.WIFSIGNALED(st) else "exit %d" % os.WEXITSTATUS(st)
    for host, port in s.get("tcp", []):
        t0 = time.monotonic()
        try:
            socket.create_connection((host, int(port)), timeout=3).close()
            r["tcp %s:%s" % (host, port)] = "ok"
        except OSError as e:
            r["tcp %s:%s" % (host, port)] = "%s (%.1fs)" % (err(e), time.monotonic() - t0)
    if "get" in s:
        host, port, n, mt = s["get"]
        t0 = time.monotonic()
        got, error = 0, None
        try:
            c = socket.create_connection((host, int(port)), timeout=5)
            c.sendall(("GET /bytes/%d HTTP/1.0\r\nHost: x\r\n\r\n" % int(n)).encode())
            deadline = t0 + float(mt)
            head = b""
            while time.monotonic() < deadline:
                c.settimeout(max(0.05, deadline - time.monotonic()))
                d = c.recv(1 << 20)
                if not d:
                    break
                if b"\r\n\r\n" not in head:
                    head += d
                    if b"\r\n\r\n" in head:
                        got = len(head.split(b"\r\n\r\n", 1)[1])
                    continue
                got += len(d)
            c.close()
        except OSError as e:
            error = err(e)
        r["get_bytes"], r["get_error"] = got, error
    if "escape" in s:
        r.update(("escape_" + k, v) for k, v in leaks_dict(*s["escape"]).items()
                 if k in ("systemd_run", "busctl", "run_user", "net"))
    if "umount" in s:
        import ctypes
        libc = ctypes.CDLL(None, use_errno=True)
        rc = libc.umount2(s["umount"].encode(), 2)  # MNT_DETACH
        r["umount"] = "ok" if rc == 0 else os.strerror(ctypes.get_errno())
    out(**r)


CMDS = {"cpu": cpu, "mem": mem, "pids": pids, "cgroup": cgroup, "procs": procs, "tcp": tcp, "get": http_get,
        "put": http_put, "curl": curl, "run": run, "ns": ns, "leaks": leaks, "ctl": ctl, "read": read,
        "check": check}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in CMDS:
        print("probe: error: ArgumentsBad want one of %s" % ", ".join(CMDS), file=sys.stderr)
        sys.exit(2)
    CMDS[sys.argv[1]](*sys.argv[2:])
