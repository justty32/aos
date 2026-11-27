"""Dynamic paths vs static ones: open/stat through a Python FUSE server (cache 0 and 1 s) and rofiles-fuse (C) against a plain file and a bind, a unix-socket ask-and-answer, and what a reader goes through when the FUSE service is stuck."""

import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time

from common import HERE, MNT_DETACH, MS_BIND, PY, Lat, collect, inner_emit, make_private, mount, umount


def _dirs(work):
    s = os.path.join(work, "fz")
    for d in ("back", "py0", "py1", "ro", "rot0", "bind", "hang"):
        os.makedirs(os.path.join(s, d), exist_ok=True)
    with open(os.path.join(s, "back", "f"), "w") as f:
        f.write("hello\n")
    return s


def fuse(work, quick):
    s = _dirs(work)
    lat = Lat(work)
    r = subprocess.run(["unshare", "-Urm", PY, "-B", os.path.join(HERE, "bench.py"), "_in", "fuse",
                        json.dumps({"s": s, "lat": lat.bin, "reps": 2000 if quick else 5000})],
                       capture_output=True, text=True, timeout=300)
    recs = collect(r.stdout)
    return recs or [{"bench": "fuse", "error": r.stderr.strip()[-300:]}]


def _start_py(s, d, ttl, hang=None):
    p = subprocess.Popen([PY, "-B", os.path.join(HERE, "pyfuse.py"), os.path.join(s, d), str(ttl),
                          os.path.join(s, "back", "f")] + ([hang] if hang else []),
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    line = p.stdout.readline()
    if not line.startswith("READY"):
        p.kill()
        p.wait()
        raise RuntimeError("pyfuse did not start: " + p.stderr.read()[-200:])
    return p


def _rss_kb(pid):
    try:
        with open("/proc/%d/status" % pid) as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1])
    except OSError:
        return None


def fuse_inner(a):
    s, lat = a["s"], Lat.__new__(Lat)
    lat.bin, lat.timer = a["lat"], "c" if a["lat"] else "python"
    make_private()
    mount(os.path.join(s, "back"), os.path.join(s, "bind"), None, MS_BIND)
    procs = [_start_py(s, "py0", 0), _start_py(s, "py1", 1)]
    paths = [("plain", s + "/back/f"), ("bind", s + "/bind/f"), ("pyfuse-cache0", s + "/py0/f"),
             ("pyfuse-cache1s", s + "/py1/f")]
    ro = shutil.which("rofiles-fuse")
    if ro:
        r1 = subprocess.run([ro, s + "/back", s + "/ro"], capture_output=True, text=True)
        r2_ = subprocess.run([ro, s + "/back", s + "/rot0", "-o", "attr_timeout=0,entry_timeout=0,negative_timeout=0"],
                             capture_output=True, text=True)
        if r1.returncode == 0:
            paths.append(("rofiles-fuse(C)", s + "/ro/f"))
        if r2_.returncode == 0:
            paths.append(("rofiles-fuse(C)-cache0", s + "/rot0/f"))
    o = lat.run("open", a["reps"], *[p for _, p in paths])
    st = lat.run("stat", a["reps"], *[p for _, p in paths])
    for (name, _), x, y in zip(paths, o, st):
        inner_emit({"bench": "fuse", "case": name, "timer": lat.timer, "open_median_us": x["median_us"],
                    "open_p99_us": x["p99_us"], "opens_per_s": round(1e6 / x["median_us"]) if x["median_us"] else None,
                    "stat_median_us": y["median_us"], "fail": x["fail"]})
    with open(s + "/back/f", "w") as f:
        f.write("changed\n")
    inner_emit({"bench": "fuse", "case": "content-change-seen",
                "pyfuse": open(s + "/py0/f").read().strip(), "bind": open(s + "/bind/f").read().strip(),
                "pyfuse_server_rss_MB": round((_rss_kb(procs[0].pid) or 0) / 1024, 1)})
    mine = os.readlink("/proc/self/ns/mnt")
    ro_pids = []  # rofiles-fuse daemonizes: find its PIDs in our own mount namespace (nobody else's)
    for x in os.listdir("/proc"):
        if x.isdigit():
            try:
                if open("/proc/%s/comm" % x).read().strip() == "rofiles-fuse" and \
                        os.readlink("/proc/%s/ns/mnt" % x) == mine:
                    ro_pids.append(int(x))
            except OSError:
                pass
    for d in ("py0", "py1", "ro", "rot0"):
        try:
            umount(os.path.join(s, d), MNT_DETACH)
        except OSError:
            pass
    end = time.monotonic() + 3
    while time.monotonic() < end and any(os.path.exists("/proc/%d" % x) for x in ro_pids):
        time.sleep(0.05)
    for x in ro_pids:
        try:
            os.kill(x, signal.SIGKILL)
        except OSError:
            pass
    for p in procs:
        try:
            p.wait(3)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait()


# ------------------------------------------------------------------ a stuck FUSE service

def fusehang(work, quick):
    s = _dirs(work)
    r = subprocess.run(["unshare", "-Urm", PY, "-B", os.path.join(HERE, "bench.py"), "_in", "fusehang",
                        json.dumps({"s": s})], capture_output=True, text=True, timeout=120)
    return collect(r.stdout) or [{"bench": "fusehang", "error": r.stderr.strip()[-300:]}]


def _state(pid):
    try:
        st = open("/proc/%d/stat" % pid).read().rsplit(")", 1)[-1].split()[0]
        return st + " " + open("/proc/%d/wchan" % pid).read()
    except OSError:
        return "gone"


def fusehang_inner(a):
    """A: the service read the request and never answers; B: the service is stopped before reading it."""
    s = a["s"]
    flag = os.path.join(s, "hangflag")
    make_private()
    for case in ("A-took-request-no-answer", "B-service-stopped"):
        if os.path.exists(flag):
            os.unlink(flag)
        srv = _start_py(s, "hang", 0, flag)
        if case.startswith("A"):
            open(flag, "w").close()
        else:
            os.kill(srv.pid, signal.SIGSTOP)
        cli = subprocess.Popen(["cat", s + "/hang/f"], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        rec = {"bench": "fusehang", "case": case}
        time.sleep(1)
        rec["reader_after_1s"] = _state(cli.pid)
        os.kill(cli.pid, signal.SIGTERM)
        time.sleep(0.5)
        rec["after_SIGTERM"] = _state(cli.pid)
        if cli.poll() is None:
            os.kill(cli.pid, signal.SIGKILL)
            time.sleep(0.5)
        rec["after_SIGKILL"] = _state(cli.pid)
        t = time.perf_counter()
        r = subprocess.run(["timeout", "-s", "KILL", "2", "stat", s + "/hang"], capture_output=True, text=True)
        rec["other_stat_of_mountpoint"] = "rc %d after %.1fs" % (r.returncode, time.perf_counter() - t)
        if case.startswith("B"):
            os.kill(srv.pid, signal.SIGCONT)
            time.sleep(0.3)
        srv.kill()
        srv.wait()
        time.sleep(0.3)
        rec["reader_after_service_killed"] = _state(cli.pid)
        cli.wait(5)
        r = subprocess.run(["cat", s + "/hang/f"], capture_output=True, text=True)
        rec["new_reader_after"] = (r.stderr.strip() or "rc %d" % r.returncode)[-80:]
        try:
            umount(s + "/hang", MNT_DETACH)
        except OSError:
            pass
        inner_emit(rec)


# ------------------------------------------------------------------ unix socket ask and answer

def sock(work, quick):
    """Python on both ends; the service reads a small file on every request (same work as pyfuse cache 0)."""
    s = _dirs(work)
    p = os.path.join(work, "rtt.sock")
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(p)
    srv.listen(1)
    pid = os.fork()
    if pid == 0:
        try:
            c, _ = srv.accept()
            while True:
                d = c.recv(256)
                if not d:
                    break
                with open(os.path.join(s, "back", "f"), "rb") as f:
                    c.sendall(f.read())
        finally:
            os._exit(0)
    srv.close()
    n = 5000 if quick else 20000
    cl = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    cl.connect(p)
    v = []
    for _ in range(n):
        t = time.perf_counter_ns()
        cl.sendall(b"read f\n")
        cl.recv(256)
        v.append(time.perf_counter_ns() - t)
    cl.close()
    os.waitpid(pid, 0)
    os.unlink(p)
    v.sort()
    return [{"bench": "sock", "case": "unix-socket-ask-answer", "n": n, "median_us": round(v[n // 2] / 1000, 2),
             "p90_us": round(v[n * 9 // 10] / 1000, 2), "p99_us": round(v[n * 99 // 100] / 1000, 2)}]


INNER = {"fuse": fuse_inner, "fusehang": fusehang_inner}

if __name__ == "__main__":
    sys.exit("run bench.py, not this file")
