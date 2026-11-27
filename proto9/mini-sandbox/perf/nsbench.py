"""Linux limits that cap how deep kernels can nest: user and PID namespace depth (each level unshare + id maps until refused), the related sysctls, and cgroups nested N deep with cpu/memory/pids limits (fork cost, kernel memory) in a delegated systemd --user scope."""

import ctypes
import errno
import json
import os
import subprocess
import sys
import time

from common import (CLONE_NEWPID, CLONE_NEWUSER, HERE, PY, collect, inner_emit, libc, per_us, r2)


def _read(p):
    try:
        with open(p) as f:
            return f.read().strip()
    except OSError:
        return None


def userns(work, quick):
    out = []
    for what in ("user", "pid"):
        r = subprocess.run([PY, "-B", os.path.join(HERE, "bench.py"), "_in", "userns", json.dumps({"what": what})],
                           capture_output=True, text=True, timeout=60)
        out += collect(r.stdout) or [{"bench": "userns", "case": what, "error": r.stderr.strip()[-200:]}]
    cg = "/sys/fs/cgroup" + (_read("/proc/self/cgroup") or "0::/").split("::", 1)[1]
    out.append({"bench": "limits", "case": "sysctl",
                "max_user_namespaces": _read("/proc/sys/user/max_user_namespaces"),
                "mount_max": _read("/proc/sys/fs/mount-max"),
                "cgroup_max_depth_here": _read(cg + "/cgroup.max.depth"),
                "cgroup_controllers_here": _read(cg + "/cgroup.controllers"),
                "pid_max": _read("/proc/sys/kernel/pid_max")})
    return out


def userns_inner(a):
    """Runs in a throwaway child: nest until unshare refuses (this process is ruined afterwards)."""
    what = a["what"]
    uid, gid, depth = os.getuid(), os.getgid(), 0
    err = None
    while depth < 300:
        flags = CLONE_NEWUSER | (CLONE_NEWPID if what == "pid" else 0)
        if libc.unshare(flags) != 0:
            e = ctypes.get_errno()
            err = "%s %s" % (errno.errorcode.get(e, e), os.strerror(e))
            break
        with open("/proc/self/setgroups", "w") as f:
            f.write("deny")
        with open("/proc/self/uid_map", "w") as f:
            f.write("0 %d 1" % uid)
        with open("/proc/self/gid_map", "w") as f:
            f.write("0 %d 1" % gid)
        uid = gid = 0
        depth += 1
        if what == "pid":
            pid = os.fork()  # the child is pid 1 of the new pid ns and goes on nesting
            if pid:
                _, st = os.waitpid(pid, 0)
                os._exit(os.waitstatus_to_exitcode(st))
    inner_emit({"bench": "userns", "case": what, "new_levels_made": depth, "refused_with": err,
                "note": "new namespaces made below the one this ran in (from the host: the most kernels can nest)"})


# ------------------------------------------------------------------ cgroups nested N deep

def cgdepth(work, quick):
    ns = [1, 100] if quick else [1, 100, 1000]
    unit = "aos-perf-cg-%d.scope" % os.getpid()
    cmd = ["systemd-run", "--user", "--scope", "--quiet", "--collect", "-p", "Delegate=yes", "--unit", unit,
           PY, "-B", os.path.join(HERE, "bench.py"), "_in", "cgdepth", json.dumps({"ns": ns})]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except OSError as e:
        return [{"bench": "cgdepth", "error": "systemd-run: %s" % e}]
    return collect(r.stdout) or [{"bench": "cgdepth", "error": r.stderr.strip()[-300:] or "rc %d" % r.returncode}]


def _meminfo():
    with open("/proc/meminfo") as f:
        return {l.split(":")[0]: int(l.split()[1]) for l in f}


def _w(p, s):
    with open(p, "w") as f:
        f.write(s)


def cgdepth_inner(a):
    base = "/sys/fs/cgroup" + _read("/proc/self/cgroup").split("::", 1)[1]
    park = base + "/park"
    os.mkdir(park)
    _w(park + "/cgroup.procs", "0")  # base must hold no process to hand controllers down
    want = [c for c in ("cpu", "memory", "pids") if c in (_read(base + "/cgroup.controllers") or "").split()]
    ctl = " ".join("+" + c for c in want)

    def fk():
        p = os.fork()
        if p == 0:
            os._exit(0)
        os.waitpid(p, 0)

    try:
        for n in a["ns"]:
            m0, c0 = _meminfo(), int(_read(base + "/memory.current") or 0)
            d, err, t = base, None, time.perf_counter()
            try:
                for i in range(n):
                    _w(d + "/cgroup.subtree_control", ctl)
                    nd = d + "/k"
                    os.mkdir(nd)
                    d = nd
                    if "memory" in want:
                        _w(d + "/memory.max", str((8 << 30) - i * 4096))
                    if "pids" in want:
                        _w(d + "/pids.max", str(4096 - (i % 4000)))
                    if "cpu" in want:
                        _w(d + "/cpu.max", "%d 100000" % (1600000 - i * 100))
            except OSError as e:
                err = "level %d: %s" % (d.count("/k") + 1, e.strerror)
            tcreate = time.perf_counter() - t
            made = d.count("/k")
            _w(d + "/cgroup.procs", "0")
            m1, c1 = _meminfo(), int(_read(base + "/memory.current") or 0)
            fork_us = per_us(fk, 500)
            t = time.perf_counter()
            buf = bytearray(64 << 20)
            for i in range(0, len(buf), 4096):
                buf[i] = 1
            touch = (time.perf_counter() - t) * 1000
            del buf
            _w(park + "/cgroup.procs", "0")
            t = time.perf_counter()
            while d != base:
                os.rmdir(d)
                d = os.path.dirname(d)
            inner_emit({"bench": "cgdepth", "case": "nested-with-limits", "n": n, "made": made, "error": err,
                        "controllers": ",".join(want), "create_ms_per_level": r2(tcreate / max(made, 1) * 1000, 3),
                        "rmdir_all_ms": r2((time.perf_counter() - t) * 1000), "fork_us": r2(fork_us, 1),
                        "touch64M_ms": r2(touch), "scope_mem_plus_MB": r2((c1 - c0) / 2 ** 20),
                        "host_slab_plus_MB": r2((m1["Slab"] - m0["Slab"]) / 1024, 1),
                        "host_percpu_plus_MB": r2((m1.get("Percpu", 0) - m0.get("Percpu", 0)) / 1024, 1)})
    finally:
        # leave nothing: climb back out of whatever is left, then the scope is collected when we exit
        _w(park + "/cgroup.procs", "0")
        for dp, dns, _ in sorted(os.walk(base), key=lambda x: -x[0].count("/")):
            if dp not in (base, park):
                try:
                    os.rmdir(dp)
                except OSError:
                    pass


INNER = {"userns": userns_inner, "cgdepth": cgdepth_inner}

if __name__ == "__main__":
    sys.exit("run bench.py, not this file")
