"""Innermost step of a mini --kernels chain (self-contained: mini.py runs it as python3 -I -c SOURCE, so it works even after a uid kernel took away your home): a clear UsernsFull if no user namespace is left for it, the declarations locked read-only if no kernel did it yet, the agent's own user, mount, pid and cgroup namespaces, an empty network unless an outer layer declared aos/net ($AOS_ENV, or / when it is not set), a clean environment, then the agent."""

import ctypes
import json
import os
import pwd
import re
import shutil
import subprocess
import sys

PROG = "mini-leaf"
NET_DECL = os.path.join(".aos", "interfaces", "aos", "net")


def fail(code, msg, exit_code=125):
    print("%s: error: %s %s" % (PROG, code, msg), file=sys.stderr, flush=True)
    sys.exit(exit_code)


def own_source():
    try:
        with open(__file__) as f:
            return f.read()
    except NameError:  # run as -c SOURCE: take it back from our own command line
        with open("/proc/self/cmdline", "rb") as f:
            a = f.read().split(b"\0")
        return a[a.index(b"-c") + 1].decode()


def userns_args():
    """Same rule as nest.userns_args (copied: this file must not need anything from your home)."""
    with open("/proc/self/uid_map") as f:
        init = f.read().split() == ["0", "0", "4294967295"]
    if init:
        user = pwd.getpwuid(os.getuid()).pw_name
        ids = []
        for path in ("/etc/subuid", "/etc/subgid"):
            try:
                with open(path) as f:
                    r = [l.strip().split(":") for l in f if l.strip().split(":")[0] in (user, str(os.getuid()))]
                ids.append((int(r[0][1]), int(r[0][2])) if r and len(r[0]) == 3 else None)
            except OSError:
                ids.append(None)
        if all(ids) and shutil.which("newuidmap"):
            n = min(ids[0][1], ids[1][1])
            return ["--user", "--map-user=0", "--map-users=1:%d:%d" % (ids[0][0], n),
                    "--map-group=0", "--map-groups=1:%d:%d" % (ids[1][0], n)]
        return ["--user", "--map-root-user"]
    if os.geteuid() == 0:
        return ["--user", "--map-users=all", "--map-groups=all"]
    return ["--user", "--map-current-user", "--keep-caps"]


_libc = ctypes.CDLL(None, use_errno=True)


def mount(src, target, fstype=None, flags=0, data=None):
    enc = lambda s: s.encode() if isinstance(s, str) else s
    if _libc.mount(enc(src), enc(target), enc(fstype), ctypes.c_ulong(flags), enc(data)) != 0:
        e = ctypes.get_errno()
        raise OSError(e, "mount %s: %s" % (target, os.strerror(e)))


MS_RDONLY, MS_REMOUNT, MS_BIND, MS_REC = 1, 32, 4096, 16384
ST_FLAGS = ((1, 1), (2, 2), (4, 4), (8, 8), (1024, 1024), (2048, 2048), (4096, 1 << 21))  # statvfs -> MS_*


def lock_env(envdir):
    """Same as nest.lock_env (copied): in our own mount namespace, every layer folder of the run folder read-only
    and the run folder a mount point, so the agent (one user namespace further in) cannot change or remove them."""
    run = os.path.dirname(os.path.abspath(envdir))
    try:
        with open("/proc/self/mountinfo") as f:
            mps = {re.sub(r"\\([0-7]{3})", lambda m: chr(int(m.group(1), 8)), l.split()[4]) for l in f}
        if run not in mps:
            mount(run, run, None, MS_BIND | MS_REC)
        for n in sorted(os.listdir(run)):
            p = os.path.join(run, n)
            if os.path.isdir(p) and not os.path.islink(p) and p not in mps:
                mount(p, p, None, MS_BIND | MS_REC)
                fl = os.statvfs(p).f_flag
                mount(None, p, None, MS_BIND | MS_REMOUNT | MS_RDONLY | sum(m for st, m in ST_FLAGS if fl & st))
    except OSError as e:
        fail("LockFailed", "%s: %s" % (run, e))


def userns_room(want):
    """Same as nest.userns_room (copied): how many more user namespaces fit below us, up to want."""
    r, w = os.pipe()
    pid = os.fork()
    if pid == 0:
        os.close(r)
        n = 0
        try:
            uid, gid = os.geteuid(), os.getegid()
            while n < want:
                if _libc.unshare(0x10000000) != 0:
                    if ctypes.get_errno() not in (28, 87):
                        n = want
                    break
                n += 1
                for f, t in (("setgroups", "deny"), ("uid_map", "0 %d 1" % uid), ("gid_map", "0 %d 1" % gid)):
                    with open("/proc/self/" + f, "w") as fh:
                        fh.write(t)
                uid = gid = 0
        except OSError:
            n = want
        os.write(w, str(n).encode())
        os._exit(0)
    os.close(w)
    got = os.read(r, 64)
    os.close(r)
    os.waitpid(pid, 0)
    try:
        return int(got)
    except ValueError:
        return want


def need_userns(want):
    have = userns_room(want)
    if have < want:
        fail("UsernsFull", "the agent's own namespaces need %d more nested user namespace(s), only %d left here: Linux "
             "allows 33 nested from the machine and the layers outside used the rest (this is not a full disk); use "
             "fewer kernels (mini.py --explain shows how many each one takes)" % (want, have), 1)


def cg_dir():
    with open("/proc/self/cgroup") as f:
        path = next(l[3:].strip() for l in f if l.startswith("0::"))
    return os.path.normpath("/sys/fs/cgroup/" + path.lstrip("/"))


def cg_write(d, name, text):
    with open(os.path.join(d, name), "w") as f:
        f.write(text)


def cg_enable(d):
    with open(os.path.join(d, "cgroup.controllers")) as f:
        have = f.read().split()
    want = " ".join("+" + c for c in ("cpu", "memory", "pids") if c in have)
    if want:
        cg_write(d, "cgroup.subtree_control", want)


def stage1(env_json, argv, locked=False):
    """Outside the agent's namespaces. If nobody locked the declarations yet (no kernels: mini's 0-root), first one
    more user and mount namespace of our own to lock them in. If we are alone in our cgroup, park ourselves (unshare
    waits here) in <cg>/wait and leave <cg>/sb empty for the agent, so its cgroup root holds no process."""
    envdir = os.environ.get("AOS_ENV", "") or ("/" if os.path.isdir("/.aos") else "")
    if envdir and envdir != "/" and not locked and os.access(envdir, os.W_OK):
        need_userns(2)
        line = ["unshare"] + userns_args() + ["--mount", "--", sys.executable, "-I", "-c", own_source(), "stage0",
                                              "--env-json", env_json, "--"] + argv
        os.execvp(line[0], line)
    if not locked:
        need_userns(1)
    has_net = bool(envdir) and os.path.isdir(os.path.join(envdir, NET_DECL))
    sb = None
    try:
        d = cg_dir()
        me = os.getpid()
        with open(os.path.join(d, "cgroup.procs")) as f:
            procs = [int(x) for x in f.read().split()]
        if procs == [me] and os.access(os.path.join(d, "cgroup.procs"), os.W_OK):
            for leaf in ("wait", "sb"):
                os.makedirs(os.path.join(d, leaf), exist_ok=True)
            cg_write(os.path.join(d, "wait"), "cgroup.procs", "0")
            cg_enable(d)
            sb = os.path.join(d, "sb")
    except (OSError, StopIteration):
        sb = None
    line = ["unshare"] + userns_args() + ["--mount", "--pid", "--fork", "--kill-child", "--mount-proc"]
    if not has_net:
        line.append("--net")
    line += [sys.executable, "-I", "-c", own_source(), "stage2", "--env-json", env_json]
    line += (["--sb", sb] if sb else []) + (["--lo"] if not has_net else []) + ["--"] + argv
    os.execvp(line[0], line)


def stage2(env_json, sb, lo, argv):
    """pid 1 of the agent's namespaces."""
    if lo:
        subprocess.run(["ip", "link", "set", "lo", "up"], stderr=subprocess.DEVNULL,
                       env={"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"})
    if sb:
        try:
            cg_write(sb, "cgroup.procs", "0")
        except OSError:
            sb = None
    try:
        os.unshare(os.CLONE_NEWCGROUP)  # the agent sees its cgroup as / and cannot raise any limit or move out
    except OSError as e:
        fail("CgroupFailed", "unshare cgroup: %s" % e.strerror)
    try:  # a fresh /sys/fs/cgroup view (see nest.cg_remount), then agent/ under an empty root
        t = "/sys/fs/cgroup"
        mount("tmpfs", t, "tmpfs", 2 | 4 | 8, "size=16k,mode=0755")
        os.mkdir(t + "/.v")
        mount("cgroup2", t + "/.v", "cgroup2", 2 | 4 | 8)
        mount(t + "/.v", t, None, 4096)
        if sb:
            os.makedirs(t + "/agent", exist_ok=True)
            cg_write(t + "/agent", "cgroup.procs", "0")
            cg_enable(t)
    except OSError:
        pass  # e.g. as uid N the cgroup files are not ours: the agent still has its own cgroup namespace
    env = json.loads(env_json)
    if os.environ.get("AOS_ENV"):
        env["AOS_ENV"] = os.environ["AOS_ENV"]
    try:
        if os.geteuid() != 0:  # uid N kept its capabilities for the setup above: drop them for good
            sp = shutil.which("setpriv") or "/usr/bin/setpriv"
            os.execve(sp, [sp, "--inh-caps=-all", "--ambient-caps=-all", "--bounding-set=-all", "--no-new-privs",
                           "--"] + argv, env)
        os.execvpe(argv[0], argv, env)
    except OSError as e:
        fail("ExecFailed", "%s: %s" % (argv[0], e.strerror), 127)


def main(args):
    if not args or args[0] not in ("stage0", "stage1", "stage2") or "--" not in args:
        fail("ArgumentsBad", "want: stage0|stage1|stage2 --env-json J [--sb DIR] [--lo] -- ARGV...", 2)
    i = args.index("--")
    own, argv = args[1:i], args[i + 1:]
    if not argv:
        fail("ArgumentsBad", "nothing to run", 2)
    o, k = {}, 0
    while k < len(own):
        if own[k] in ("--env-json", "--sb"):
            o[own[k]] = own[k + 1]
            k += 2
        elif own[k] == "--lo":
            o["--lo"] = True
            k += 1
        else:
            fail("ArgumentsBad", "unknown option %r" % own[k], 2)
    if args[0] == "stage0":  # in the extra namespace stage1 asked for
        lock_env(os.environ["AOS_ENV"])
        return stage1(o.get("--env-json", "{}"), argv, locked=True)
    if args[0] == "stage1":
        return stage1(o.get("--env-json", "{}"), argv)
    stage2(o.get("--env-json", "{}"), o.get("--sb"), o.get("--lo"), argv)


main(sys.argv[1:])
