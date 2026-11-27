"""Shared by the mini kernels that nest (cg, mask, uid, net as a wrapper): the KERNEL [options] -- NEXT... shape, the environment folder each layer reads from the outer one ($AOS_ENV) and hands a copy of to the inner one, user namespaces that keep the subordinate ids, and the cgroup layout (a layer's own cgroup holds no process)."""

import ctypes
import json
import os
import pwd
import shutil
import sys

INIT_CGROUP_NS = "cgroup:[4026531835]"   # the init namespaces have fixed inode numbers
DECL = os.path.join(".aos", "interfaces", "aos")
CONTROLLERS = ("cpu", "memory", "pids")
MS_RDONLY, MS_NOSUID, MS_NODEV, MS_NOEXEC, MS_REMOUNT, MS_BIND, MS_REC = 1, 2, 4, 8, 32, 4096, 16384
MS_NOATIME, MS_NODIRATIME, MS_RELATIME = 1024, 2048, 1 << 21
O_PATH = getattr(os, "O_PATH", 0o10000000)


def fail(prog, code, msg, exit_code=1):
    sys.stdout.flush()
    print("%s: error: %s %s" % (prog, code, msg), file=sys.stderr, flush=True)
    sys.exit(exit_code)


def warn(prog, msg):
    print("%s: warning: %s" % (prog, msg), file=sys.stderr, flush=True)


def parse(prog, argv, flags=("--stage2",)):
    """KERNEL [--name N] [--json CFG] [--stage2] -- NEXT... -> (opts, cfg dict, next argv)."""
    if "--" not in argv:
        fail(prog, "ArgumentsBad", "want: %s [--name N] [--json CFG] -- NEXT..." % prog, 2)
    i = argv.index("--")
    own, nxt = argv[:i], argv[i + 1:]
    if not nxt:
        fail(prog, "ArgumentsBad", "nothing to run after --", 2)
    opts, cfg, k = {"name": prog}, {}, 0
    while k < len(own):
        a = own[k]
        if a in flags:
            opts[a.lstrip("-")] = True
            k += 1
        elif a in ("--name", "--json") and k + 1 < len(own):
            if a == "--name":
                opts["name"] = own[k + 1]
            else:
                try:
                    cfg = json.loads(own[k + 1])
                except ValueError as e:
                    fail(prog, "ConfigBad", "--json: %s" % e, 2)
                if not isinstance(cfg, dict):
                    fail(prog, "ConfigBad", "--json: want an object", 2)
            k += 2
        else:
            fail(prog, "ArgumentsBad", "unknown option %r" % a, 2)
    return opts, cfg, nxt


def py(path):
    """How a kernel starts a program of this folder (or the next stage of itself)."""
    return [sys.executable, "-I", path]


# ------------------------------------------------------------ user namespaces

def in_init_userns():
    with open("/proc/self/uid_map") as f:
        return f.read().split() == ["0", "0", "4294967295"]


def subid_range(path, uid=None):
    uid = os.getuid() if uid is None else uid
    try:
        user = pwd.getpwuid(uid).pw_name
    except KeyError:
        user = None
    try:
        with open(path) as f:
            for line in f:
                p = line.strip().split(":")
                if len(p) == 3 and p[0] in (user, str(uid)):
                    return int(p[1]), int(p[2])
    except OSError:
        pass
    return None


def userns_args():
    """util-linux unshare options for a new user namespace one level down. Outside any sandbox: 0 -> you and
    1..N -> your subordinate ids (newuidmap, no root); inside one, as its root: every id we have, unchanged
    (so a uid kernel further in can still switch); as a plain uid N: only N, kept as N, caps kept for the setup."""
    if in_init_userns():
        su, sg = subid_range("/etc/subuid"), subid_range("/etc/subgid")
        if su and sg and shutil.which("newuidmap"):
            n = min(su[1], sg[1])
            return ["--user", "--map-user=0", "--map-users=1:%d:%d" % (su[0], n),
                    "--map-group=0", "--map-groups=1:%d:%d" % (sg[0], n)]
        return ["--user", "--map-root-user"]
    if os.geteuid() == 0:
        return ["--user", "--map-users=all", "--map-groups=all"]
    return ["--user", "--map-current-user", "--keep-caps"]


# ------------------------------------------------------------ the environment folder ($AOS_ENV)

def env_outer():
    d = os.environ.get("AOS_ENV")
    return d if d and os.path.isdir(d) else None


def decl_read(envdir, kind, key, default=None):
    """One declared value of the outer environment (None when that kind is not declared)."""
    if not envdir:
        return default
    try:
        with open(os.path.join(envdir, DECL, kind, key)) as f:
            return f.read().strip()
    except OSError:
        return default


def host_file(name):
    """What mini.py --kernels wrote about the machine at the root of the chain (.aos/host_uid, .aos/host_subuid)."""
    env = env_outer()
    try:
        with open(os.path.join(env, ".aos", name)) as f:
            return f.read().strip()
    except (OSError, TypeError):
        return ""


def host_subuid():
    """(start, count) of your subordinate ids outside, or None."""
    v = host_file("host_subuid").split()
    return (int(v[0]), int(v[1])) if len(v) == 2 else None


def declared(envdir, kind):
    return bool(envdir) and os.path.isdir(os.path.join(envdir, DECL, kind))


def _write(path, text):
    os.makedirs(os.path.dirname(path), mode=0o755, exist_ok=True)
    tmp = os.path.join(os.path.dirname(path), "." + os.path.basename(path) + ".tmp")
    with open(tmp, "w") as f:
        f.write(text)
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)


def new_env(kind, name):
    """The folder this layer hands to the inner one: a copy of the outer folder's .aos (so the inner sees everything
    declared further out), plus one line in .aos/kernels. Lives next to the outer one (in the run folder)."""
    outer = env_outer()
    if not outer:
        raise RuntimeError("AOS_ENV is not set (start kernels through mini.py --kernels)")
    run = os.path.dirname(outer)
    with open(os.path.join(outer, ".aos", "kernels")) as f:
        lines = [l for l in f.read().splitlines() if l.strip()]
    d = os.path.join(run, "%d-%s-%d" % (len(lines) + 1, kind, os.getpid()))
    shutil.copytree(os.path.join(outer, ".aos"), os.path.join(d, ".aos"), symlinks=True)
    os.chmod(d, 0o755)
    _write(os.path.join(d, ".aos", "kernels"), "".join(l + "\n" for l in lines + ["%s %s" % (kind, name)]))
    return d


def declare(envdir, kind, files, description=None):
    """Declare (or replace: the inner declaration shadows the outer one) aos/<kind> in envdir."""
    d = os.path.join(envdir, DECL, kind)
    if os.path.isdir(d):
        shutil.rmtree(d)
    os.makedirs(d, mode=0o755)
    for k, v in files.items():
        _write(os.path.join(d, k), (v + "\n") if v else "")
    if description:
        _write(os.path.join(d, "description"), description + "\n")


# ------------------------------------------------------------ mounts and cgroups

_libc = ctypes.CDLL(None, use_errno=True)


def mount(src, target, fstype=None, flags=0, data=None):
    enc = lambda s: s.encode() if isinstance(s, str) else s
    if _libc.mount(enc(src), enc(target), enc(fstype), ctypes.c_ulong(flags), enc(data)) != 0:
        e = ctypes.get_errno()
        raise OSError(e, "mount %s: %s" % (target, os.strerror(e)))


def cg_path():
    with open("/proc/self/cgroup") as f:
        for line in f:
            if line.startswith("0::"):
                return line[3:].strip()
    raise RuntimeError("no cgroup v2 line in /proc/self/cgroup")


def cg_dir():
    """Our cgroup folder: /sys/fs/cgroup shows the root of our cgroup namespace (every layer that makes a cgroup
    namespace mounts a fresh view, see cg_remount)."""
    return os.path.normpath("/sys/fs/cgroup/" + cg_path().lstrip("/"))


def cg_init_ns():
    return os.readlink("/proc/self/ns/cgroup") == INIT_CGROUP_NS


def cg_procs(d):
    with open(os.path.join(d, "cgroup.procs")) as f:
        return [int(x) for x in f.read().split()]


def cg_move(pid, d):
    with open(os.path.join(d, "cgroup.procs"), "w") as f:
        f.write(str(pid))


def cg_enable(d):
    """Hand cpu, memory, pids down to the children of d (d must hold no process)."""
    with open(os.path.join(d, "cgroup.controllers")) as f:
        have = f.read().split()
    want = " ".join("+" + c for c in CONTROLLERS if c in have)
    if want:
        with open(os.path.join(d, "cgroup.subtree_control"), "w") as f:
            f.write(want)


def cg_remount():
    """After unshare -C: make /sys/fs/cgroup show the new namespace root. Mounting cgroup2 straight onto the old
    cgroup2 mount is EBUSY (same superblock), so put a small tmpfs there first, mount cgroup2 on a folder in it,
    and bind that over."""
    t = "/sys/fs/cgroup"
    mount("tmpfs", t, "tmpfs", MS_NOSUID | MS_NODEV | MS_NOEXEC, "size=16k,mode=0755")
    os.mkdir(t + "/.v")
    mount("cgroup2", t + "/.v", "cgroup2", MS_NOSUID | MS_NODEV | MS_NOEXEC)
    mount(t + "/.v", t, None, MS_BIND)


def cg_layout(leaf):
    """We are the only process in the root of a fresh cgroup namespace: move into a child (so the root holds no
    process) and hand the controllers down, so whoever runs inside can make limited cgroups of its own."""
    root = "/sys/fs/cgroup"
    os.makedirs(os.path.join(root, leaf), exist_ok=True)
    cg_move(0, os.path.join(root, leaf))
    cg_enable(root)


def cg_split(prog, pids, kernel_leaf, inner_leaf):
    """For a kernel that keeps running (net): move its own processes into <cgroup>/<kernel_leaf> and make
    <cgroup>/<inner_leaf> for the inner layers, so a cgroup kernel further in finds a cgroup with only itself.
    Returns the inner folder, or None when the cgroup is not ours to change (then nothing is moved)."""
    try:
        d = cg_dir()
        if not os.access(os.path.join(d, "cgroup.procs"), os.W_OK):
            return None
        k, i = os.path.join(d, kernel_leaf), os.path.join(d, inner_leaf)
        os.makedirs(k, exist_ok=True)
        os.makedirs(i, exist_ok=True)
        for p in set(cg_procs(d)) | set(pids):
            try:
                cg_move(p, k)
            except OSError:
                pass
        try:
            cg_enable(d)
        except OSError as e:
            warn(prog, "cgroup %s: could not hand controllers down (%s)" % (d, e.strerror))
        return i
    except (OSError, RuntimeError) as e:
        warn(prog, "cgroup: left as it is (%s)" % e)
        return None
