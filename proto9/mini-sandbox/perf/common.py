"""Shared helpers for perf/: host facts, one-JSON-line records, timing loops, mount(2) through ctypes, and the small C timer lat.c (built on the fly, Python fallback when there is no C compiler)."""

import ctypes
import json
import os
import platform
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
PY = sys.executable or "/usr/bin/python3"

# ------------------------------------------------------------------ host facts and records

_HOST = None


def _git(*args):
    try:
        return subprocess.run(["git", "-C", REPO] + list(args), capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def host():
    """Machine, Linux version and commit, put into every record (no host name, no user name)."""
    global _HOST
    if _HOST is None:
        cpu = ""
        try:
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if line.startswith("model name"):
                        cpu = line.split(":", 1)[1].strip()
                        break
        except OSError:
            pass
        osname = ""
        try:
            with open("/etc/os-release") as f:
                for line in f:
                    if line.startswith("PRETTY_NAME="):
                        osname = line.split("=", 1)[1].strip().strip('"')
        except OSError:
            pass
        rel = os.uname().release
        commit = _git("rev-parse", "--short=9", "HEAD").strip() or "unknown"
        if _git("status", "--porcelain", "--untracked-files=no").strip():
            commit += "+dirty"
        _HOST = {"cpu": cpu, "cpus": os.cpu_count(), "kernel": rel, "os": osname,
                 "wsl": "microsoft" in rel.lower(), "commit": commit, "python": platform.python_version()}
    return _HOST


def loadavg():
    try:
        with open("/proc/loadavg") as f:
            return float(f.read().split()[0])
    except OSError:
        return None


def stamp(rec):
    """Add time, load and host to a record."""
    out = {"time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "load1": loadavg()}
    out.update(rec)
    out["host"] = host()
    return out


def inner_emit(rec):
    """Inside a namespace or a child: print a bare record line; the parent stamps and keeps it."""
    print("REC " + json.dumps(rec), flush=True)


def collect(stdout):
    """The REC lines a child printed."""
    out = []
    for line in stdout.splitlines():
        if line.startswith("REC "):
            try:
                out.append(json.loads(line[4:]))
            except ValueError:
                pass
    return out


# ------------------------------------------------------------------ timing

def per_us(fn, n):
    """Mean microseconds of fn() over n calls."""
    t = time.perf_counter()
    for _ in range(n):
        fn()
    return (time.perf_counter() - t) / n * 1e6


def best_ms(cmd, reps=3, **kw):
    """Best of reps wall milliseconds of a command; returns (ms, last CompletedProcess)."""
    best, r = 1e18, None
    for _ in range(reps):
        t = time.perf_counter()
        r = subprocess.run(cmd, capture_output=True, **kw)
        best = min(best, time.perf_counter() - t)
    return round(best * 1000, 3), r


def median(v):
    v = sorted(v)
    return v[len(v) // 2] if v else None


def r2(x, nd=2):
    return None if x is None else round(x, nd)


# ------------------------------------------------------------------ mount(2)

libc = ctypes.CDLL(None, use_errno=True)
MS_RDONLY, MS_NOSUID, MS_NODEV, MS_REMOUNT, MS_BIND, MS_REC, MS_PRIVATE = 1, 2, 4, 32, 4096, 16384, 1 << 18
MNT_DETACH = 2
CLONE_NEWNS, CLONE_NEWUSER, CLONE_NEWPID = 0x20000, 0x10000000, 0x20000000


def _b(s):
    return s.encode() if isinstance(s, str) else s


def mount(src, tgt, fs, flags, data=None):
    if libc.mount(_b(src), _b(tgt), _b(fs), ctypes.c_ulong(flags), _b(data)) != 0:
        e = ctypes.get_errno()
        raise OSError(e, os.strerror(e), tgt)


def umount(tgt, flags=0):
    if libc.umount2(_b(tgt), flags) != 0:
        e = ctypes.get_errno()
        raise OSError(e, os.strerror(e), tgt)


def make_private():
    mount(None, "/", None, MS_REC | MS_PRIVATE)


def mountinfo_lines():
    with open("/proc/self/mountinfo") as f:
        return sum(1 for _ in f)


def fstype(path):
    try:
        return subprocess.run(["findmnt", "-no", "FSTYPE", "-T", path], capture_output=True, text=True,
                              timeout=5).stdout.strip() or None
    except (OSError, subprocess.TimeoutExpired):
        return None


# ------------------------------------------------------------------ the C timer (lat.c) with a Python fallback

class Lat:
    """Latency of stat / open+read+close / stat of a missing name; median, p90, p99 in microseconds."""

    def __init__(self, workdir):
        self.bin = None
        cc = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
        if cc:
            out = os.path.join(workdir, "lat")
            r = subprocess.run([cc, "-O2", "-o", out, os.path.join(HERE, "lat.c")], capture_output=True, text=True)
            if r.returncode == 0:
                self.bin = out
        self.timer = "c" if self.bin else "python"

    def run(self, mode, n, *paths):
        """[{path, median_us, p90_us, p99_us, fail}] per path."""
        if self.bin:
            out = subprocess.run([self.bin, mode, str(n)] + list(paths), capture_output=True, text=True).stdout
            res = []
            for line in out.splitlines():
                f = line.split()
                kv = dict(x.split("=", 1) for x in f[2:] if "=" in x)
                res.append({"path": f[1], "median_us": float(kv["median_us"]), "p90_us": float(kv["p90_us"]),
                            "p99_us": float(kv["p99_us"]), "fail": int(kv["fail"])})
            return res
        return [self._py(mode, n, p) for p in paths]

    def first_open_mean(self, paths):
        """Open+read each path once (cold for whatever cache sits in front of it); mean microseconds."""
        if self.bin:
            r = subprocess.run([self.bin, "list"], input="\n".join(paths) + "\n", capture_output=True, text=True)
            kv = dict(x.split("=", 1) for x in r.stdout.split()[1:] if "=" in x)
            return float(kv.get("mean_us", "nan")), int(kv.get("bad", "0"))
        bad, t = 0, time.perf_counter_ns()
        for p in paths:
            try:
                with open(p, "rb") as f:
                    f.read(256)
            except OSError:
                bad += 1
        return (time.perf_counter_ns() - t) / len(paths) / 1000, bad

    @staticmethod
    def _py(mode, n, p):
        def op():
            if mode in ("stat", "miss"):
                os.stat(p)
            else:
                with open(p, "rb") as f:
                    f.read(256)
        bad, v = 0, []
        for _ in range(50):
            try:
                op()
            except OSError:
                pass
        for _ in range(n):
            t = time.perf_counter_ns()
            try:
                op()
            except OSError:
                bad += 1
            v.append(time.perf_counter_ns() - t)
        v.sort()
        return {"path": p, "median_us": v[n // 2] / 1000, "p90_us": v[n * 9 // 10] / 1000,
                "p99_us": v[n * 99 // 100] / 1000, "fail": bad}
