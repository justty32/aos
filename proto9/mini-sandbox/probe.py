#!/usr/bin/env python3
"""What accept.py, stack_test.py, llm_test.py and bundle_test.py run inside a mini sandbox instead of pi: one subcommand per check (check = several at once), one json line out (standard library only, so it also runs as python3 -I -c SOURCE where your home is closed)."""

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
    escape [UNIT, OUTFILE], umount PATH, llm {posts, model, bad_model, state} (see llm_check), lock {status_wait,
    model} (see lock_check)."""
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
    if "llm" in s:
        r.update(llm_check(s["llm"]))
    if "lock" in s:
        r.update(lock_check(s["lock"]))
    if "umount" in s:
        import ctypes
        libc = ctypes.CDLL(None, use_errno=True)
        rc = libc.umount2(s["umount"].encode(), 2)  # MNT_DETACH
        r["umount"] = "ok" if rc == 0 else os.strerror(ctypes.get_errno())
    out(**r)


# ---------------------------------------------------------------- can the agent undo the read-only lock?

AT_FDCWD, AT_EMPTY_PATH, AT_RECURSIVE = -100, 0x1000, 0x8000
OPEN_TREE_CLONE, MOVE_MOUNT_F_EMPTY_PATH, MOUNT_ATTR_RDONLY = 1, 4, 1
SYS_OPEN_TREE, SYS_MOVE_MOUNT, SYS_MOUNT_SETATTR = 428, 429, 442  # x86_64
MS_RDONLY, MS_REMOUNT, MS_BIND, MS_REC = 1, 32, 4096, 16384


def _libc():
    import ctypes
    return ctypes, ctypes.CDLL(None, use_errno=True)


def _rc(rc):
    ctypes, _ = _libc()
    return "ok" if rc >= 0 else os.strerror(ctypes.get_errno())


def _try(fn):
    try:
        fn()
        return "ok"
    except OSError as e:
        return e.strerror or str(e)


def _mount(src, target, fstype, flags):
    ctypes, libc = _libc()
    enc = lambda x: x.encode() if isinstance(x, str) else x
    return _rc(libc.mount(enc(src), enc(target), enc(fstype), ctypes.c_ulong(flags), None))


def _setattr_rw(fd, path, flags):
    """mount_setattr(2): clear MOUNT_ATTR_RDONLY (the new mount API's way to make a mount writable)."""
    ctypes, libc = _libc()
    attr = (ctypes.c_uint64 * 4)(0, MOUNT_ATTR_RDONLY, 0, 0)
    return _rc(libc.syscall(SYS_MOUNT_SETATTR, ctypes.c_int(fd), path.encode(), ctypes.c_uint(flags), attr,
                            ctypes.c_size_t(32)))


def lock_attacks(env, cells, scratch):
    """Everything the agent (root in its own user and mount namespace) might try to write the declarations."""
    ctypes, libc = _libc()
    r = {}
    kernels = os.path.join(env, ".aos", "kernels")
    run = os.path.dirname(env)
    first = os.path.join(cells[0], "name") if cells else kernels
    r["append_kernels"] = _try(lambda: open(kernels, "a").write("pwned x\n"))
    r["write_cell"] = _try(lambda: open(first, "a").write("pwned\n"))
    r["new_file"] = _try(lambda: open(os.path.join(env, ".aos", "pwned"), "w").write("x"))
    r["remove_file"] = _try(lambda: os.unlink(first))
    st = [open(os.path.join(c, "status")).read().strip() for c in cells]
    st = [x for x in st if x]
    if st:
        r["write_status"] = _try(lambda: open(st[0], "a").write("state: pwned\n"))
    for name, src in (("rename_env", env), ("rename_run", run)):
        r[name] = _try(lambda: os.rename(src, src + ".x"))
        if r[name] == "ok":
            os.rename(src + ".x", src)
    r["umount"] = _rc(libc.umount2(env.encode(), 2))  # MNT_DETACH
    r["remount_rw"] = _mount(None, env, None, MS_REMOUNT | MS_BIND)
    r["remount_rw_then_write"] = _try(lambda: open(kernels, "a").write("pwned remount\n"))
    r["mount_setattr_rw"] = _setattr_rw(AT_FDCWD, env, 0)
    fd = libc.syscall(SYS_OPEN_TREE, ctypes.c_int(AT_FDCWD), env.encode(), ctypes.c_uint(OPEN_TREE_CLONE |
                                                                                         AT_RECURSIVE))
    r["open_tree_clone"] = _rc(fd)
    if fd >= 0:
        r["clone_setattr_rw"] = _setattr_rw(fd, "", AT_EMPTY_PATH)
        os.makedirs(scratch + "/clone", exist_ok=True)
        r["clone_move_mount"] = _rc(libc.syscall(SYS_MOVE_MOUNT, ctypes.c_int(fd), b"", ctypes.c_int(AT_FDCWD),
                                                 (scratch + "/clone").encode(), ctypes.c_uint(MOVE_MOUNT_F_EMPTY_PATH)))
        if r["clone_move_mount"] == "ok":
            r["clone_write"] = _try(lambda: open(scratch + "/clone/.aos/kernels", "a").write("pwned clone\n"))
            libc.umount2((scratch + "/clone").encode(), 2)
        os.close(fd)
    for name, src in (("bind_run_plain", run), ("bind_tmp_plain", os.path.dirname(run))):
        t = os.path.join(scratch, name)
        os.makedirs(t, exist_ok=True)
        r[name] = _mount(src, t, None, MS_BIND)  # without MS_REC: would show what the locked mounts cover
        if r[name] == "ok":
            under = os.path.join(t, os.path.relpath(kernels, src))
            r[name + "_write"] = _try(lambda: open(under, "a").write("pwned bind\n"))
            libc.umount2(t.encode(), 2)
    return r


def lock_check(spec):
    """The declarations ($AOS_ENV, or /) are locked read-only: try to write, remove, rename, unmount, remount them,
    once as the agent and once more from a user and mount namespace of its own (like unshare -Urm), then see that
    nothing changed; and that the live status files still move (kept up to date from outside). escape_unit: last,
    ask systemd --user over D-Bus for a process outside the sandbox that appends to .aos/kernels."""
    import tempfile
    env = os.environ.get("AOS_ENV") or "/"
    decl = os.path.join(env, ".aos", "interfaces", "aos")
    cells = [os.path.join(decl, k) for k in sorted(os.listdir(decl))] if os.path.isdir(decl) else []
    cells = [c for c in cells if os.path.isdir(c)]
    snap = lambda: {p: open(p).read() for p in [os.path.join(env, ".aos", "kernels")] +
                    [os.path.join(c, f) for c in cells for f in sorted(os.listdir(c)) if os.path.isfile(os.path.join(c, f))]}
    before = snap()
    r = {"lock_cells": {os.path.basename(c): {f: open(os.path.join(c, f)).read().strip() for f in
                                              ("name", "layer", "status", "from") if os.path.exists(os.path.join(c, f))}
                        for c in cells},
         "lock_kernels": open(os.path.join(env, ".aos", "kernels")).read().splitlines()}
    scratch = tempfile.mkdtemp(prefix="aos-probe-")
    try:
        r["lock_agent"] = lock_attacks(env, cells, scratch)
        rd, wr = os.pipe()
        pid = os.fork()
        if pid == 0:  # one user + mount namespace further in, root there (unshare -Urm)
            os.close(rd)
            try:
                uid, gid = os.getuid(), os.getgid()
                os.unshare(os.CLONE_NEWUSER | os.CLONE_NEWNS)
                open("/proc/self/setgroups", "w").write("deny")
                open("/proc/self/uid_map", "w").write("0 %d 1" % uid)
                open("/proc/self/gid_map", "w").write("0 %d 1" % gid)
                n = lock_attacks(env, cells, scratch)
                n["cover_with_tmpfs"] = _mount("tmpfs", env, "tmpfs", 0)  # only its own view changes
                if n["cover_with_tmpfs"] == "ok":
                    n["cover_then_write"] = _try(lambda: open(os.path.join(env, "own"), "w").write("x"))
            except OSError as e:
                n = {"unshare": err(e)}
            os.write(wr, json.dumps(n).encode())
            os._exit(0)
        os.close(wr)
        got = b""
        while True:
            c = os.read(rd, 65536)
            if not c:
                break
            got += c
        os.waitpid(pid, 0)
        r["lock_nested"] = json.loads(got or b"{}")
    finally:
        for d in sorted((os.path.join(dp, x) for dp, ds, _ in os.walk(scratch) for x in ds), reverse=True):
            _, libc = _libc()
            libc.umount2(d.encode(), 2)
        subprocess.run(["rm", "-rf", scratch], stderr=subprocess.DEVNULL)
    after = snap()
    r["lock_unchanged"] = before == after
    if before != after:
        r["lock_changed"] = sorted(p for p in set(before) | set(after) if before.get(p) != after.get(p))
    live = {}
    for c in cells:
        sp = open(os.path.join(c, "status")).read().strip()
        if not sp:
            continue
        h1 = open(sp).read().splitlines()
        if os.path.basename(c) == "llm":
            llm_post(open(os.path.join(c, "path")).read().strip(), spec.get("model", "fake-model"))
        time.sleep(float(spec.get("status_wait", 0)))
        h2 = open(sp).read().splitlines()
        live[os.path.basename(c)] = {"before": h1[:3], "after": h2[:3], "moved": h1 != h2}
    r["lock_live"] = live
    if spec.get("escape_unit"):  # out through systemd --user (open when /run/user is not covered), write from there
        k = os.path.join(env, ".aos", "kernels")
        script = "echo 'pwned from outside' >> %s" % k
        p = subprocess.run(["busctl", "--user", "call", "--", "org.freedesktop.systemd1", "/org/freedesktop/systemd1",
                            "org.freedesktop.systemd1.Manager", "StartTransientUnit", "ssa(sv)a(sa(sv))",
                            spec["escape_unit"], "fail", "2", "ExecStart", "a(sasb)", "1", "/bin/sh", "3", "/bin/sh",
                            "-c", script, "false", "CollectMode", "s", "inactive-or-failed", "0"],
                           capture_output=True, text=True)
        time.sleep(1.5)
        r["lock_escape"] = {"busctl": "rc %d %s" % (p.returncode, (p.stdout + p.stderr).strip()[-120:]),
                            "kernels_now": open(k).read().splitlines()[-1:]}
    return r


def llm_post(sock, model, timeout=20):
    """One chat request over a unix socket (HTTP/1.1); returns the status code or an error."""
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": "hi"}]}).encode()
    try:
        c = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        c.settimeout(timeout)
        c.connect(sock)
        c.sendall(b"POST /v1/chat/completions HTTP/1.1\r\nHost: llm\r\nContent-Type: application/json\r\n"
                  b"Connection: close\r\nContent-Length: %d\r\n\r\n" % len(body) + body)
        head = c.recv(64)
        c.close()
        return int(head.split()[1]) if head.startswith(b"HTTP/") else "no answer"
    except (OSError, ValueError, IndexError) as e:
        return err(e)


def llm_check(spec):
    """What the agent sees of an llm kernel: its aos/llm declaration (found through $AOS_ENV), N requests over the
    declared socket, other llm sockets it can find on the disk, and the kernel's state folder."""
    r = {}
    decl = os.path.join(os.environ.get("AOS_ENV") or "/", ".aos", "interfaces", "aos", "llm")
    try:
        sock = open(os.path.join(decl, "path")).read().strip()
        r["llm_network"] = open(os.path.join(decl, "network")).read().split(":")[0]
    except OSError as e:
        r["llm_decl"] = err(e)
        return r
    r["llm_codes"] = [llm_post(sock, spec.get("model", "fake-model")) for _ in range(int(spec.get("posts", 1)))]
    if spec.get("bad_model"):
        r["llm_bad_model"] = llm_post(sock, spec["bad_model"])
    r["llm_other_socks"] = {p: llm_post(p, spec.get("model", "fake-model"), 5)
                            for p in sorted(glob.glob("/tmp/aos-mini-*/*-llm-*/sock")) if p != sock}
    if spec.get("state"):
        st = spec["state"]
        try:
            r["llm_state_list"] = sorted(os.listdir(st))
        except OSError as e:
            r["llm_state_list"] = err(e)
        try:
            with open(os.path.join(st, "budget.json"), "w") as f:
                f.write('{"used": 0, "limit": 1000}\n')
            r["llm_state_write"] = "wrote budget.json"
        except OSError as e:
            r["llm_state_write"] = err(e)
    return r


CMDS = {"cpu": cpu, "mem": mem, "pids": pids, "cgroup": cgroup, "procs": procs, "tcp": tcp, "get": http_get,
        "put": http_put, "curl": curl, "run": run, "ns": ns, "leaks": leaks, "ctl": ctl, "read": read,
        "check": check}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in CMDS:
        print("probe: error: ArgumentsBad want one of %s" % ", ".join(CMDS), file=sys.stderr)
        sys.exit(2)
    CMDS[sys.argv[1]](*sys.argv[2:])
