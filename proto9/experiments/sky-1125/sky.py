"""sky.py: the library of the sky-1125 toy: sky config text, want-tables, building a sky in a forked child (tmpfs root, binds, overlay, pivot_root), the lock, live mounts, and comparing a table with /proc/<PID>/mountinfo."""
import ctypes, errno, fcntl, json, os, posixpath, re, socket, stat, struct, sys

if os.uname().machine != "x86_64":
    sys.exit("sky.py: the syscall numbers below are for x86_64 only")

# ---------------------------------------------------------------- Linux calls Python has no wrapper for

SYS_capset, SYS_pivot_root = 126, 155
SYS_open_tree, SYS_move_mount, SYS_openat2 = 428, 429, 437
SYS_landlock_create_ruleset, SYS_landlock_restrict_self = 444, 446

MS_RDONLY, MS_NOSUID, MS_NODEV, MS_NOEXEC = 1, 2, 4, 8
MS_REMOUNT, MS_NOATIME, MS_NODIRATIME, MS_BIND, MS_REC, MS_PRIVATE = 32, 1024, 2048, 4096, 16384, 1 << 18
MNT_DETACH = 2
AT_FDCWD, AT_EMPTY_PATH = -100, 0x1000
OPEN_TREE_CLONE, MOVE_MOUNT_F_EMPTY_PATH = 1, 4
RESOLVE_NO_MAGICLINKS, RESOLVE_BENEATH = 0x02, 0x08
PR_SET_DUMPABLE = 4

libc = ctypes.CDLL(None, use_errno=True)
libc.syscall.restype = ctypes.c_long
libc.mount.argtypes = (ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_ulong, ctypes.c_char_p)
libc.umount2.argtypes = (ctypes.c_char_p, ctypes.c_int)
libc.prctl.argtypes = (ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong)
L = ctypes.c_long


def _b(s):
    return None if s is None else os.fsencode(s)


def _ok(ret, what):
    if ret < 0:
        err = ctypes.get_errno()
        raise OSError(err, f"{what}: {os.strerror(err)}")
    return ret


def mount(src, dst, fstype=None, flags=0, data=None):
    _ok(libc.mount(_b(src), _b(dst), _b(fstype), flags, _b(data)), f"mount {dst}")


def umount2(path, flags=0):
    _ok(libc.umount2(_b(path), flags), f"umount {path}")


def pivot_root(new, old):
    _ok(libc.syscall(L(SYS_pivot_root), _b(new), _b(old)), "pivot_root")


def open_tree(fd, flags):
    return _ok(libc.syscall(L(SYS_open_tree), L(fd), b"", L(flags | AT_EMPTY_PATH | os.O_CLOEXEC)), "open_tree")


def move_mount(fd, to):
    _ok(libc.syscall(L(SYS_move_mount), L(fd), b"", L(AT_FDCWD), _b(to), L(MOVE_MOUNT_F_EMPTY_PATH)), f"move_mount {to}")


def openat2(dirfd, path, flags, resolve):
    how = struct.pack("QQQ", flags, 0, resolve)
    return _ok(libc.syscall(L(SYS_openat2), L(dirfd), _b(path), how, L(len(how))), f"open {path}")


def set_dumpable(on):
    _ok(libc.prctl(PR_SET_DUMPABLE, 1 if on else 0, 0, 0, 0), "prctl(PR_SET_DUMPABLE)")


def drop_caps():
    """capset(2) everything to zero in this process only: the half-lock that the next execve undoes for uid 0."""
    _ok(libc.syscall(L(SYS_capset), struct.pack("Ii", 0x20080522, 0), bytes(24)), "capset")


def landlock_abi():
    """Landlock ABI version of this kernel (negative: no Landlock)."""
    return libc.syscall(L(SYS_landlock_create_ruleset), None, L(0), L(1))


def landlock_scope():
    """Put the caller in a Landlock domain of its own. Landlock stops a process in a domain from ptrace-reading
    anything outside it (/proc/<PID>/root, cwd, fd); from ABI 6 (Linux 6.12) the domain also scopes signals
    and abstract unix sockets. Before ABI 6 the domain only handles making block devices, which a user
    namespace cannot do anyway, so nothing else changes."""
    if landlock_abi() >= 6:
        attr = struct.pack("QQQ", 0, 0, 0x1 | 0x2)  # handled fs, handled net, scoped = abstract unix | signal
    else:
        attr = struct.pack("Q", 1 << 11)  # LANDLOCK_ACCESS_FS_MAKE_BLOCK
    fd = _ok(libc.syscall(L(SYS_landlock_create_ruleset), attr, L(len(attr)), L(0)), "landlock_create_ruleset")
    _ok(libc.syscall(L(SYS_landlock_restrict_self), L(fd), L(0)), "landlock_restrict_self")
    os.close(fd)


def lo_up():
    """Bring lo up in a fresh network namespace (it starts down)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        ifr = struct.pack("16sH22x", b"lo", 0)
        flags = struct.unpack("16sH22x", fcntl.ioctl(s, 0x8913, ifr))[1]  # SIOCGIFFLAGS
        fcntl.ioctl(s, 0x8914, struct.pack("16sH22x", b"lo", flags | 1))  # SIOCSIFFLAGS, IFF_UP
    finally:
        s.close()


def remount(path, ro, extra=0):
    """Re-mount one mount point read-only (or read-write), keeping the flags Linux will not let us drop."""
    keep = os.statvfs(path).f_flag & (MS_NOSUID | MS_NODEV | MS_NOEXEC | MS_NOATIME | MS_NODIRATIME)
    mount(None, path, None, MS_REMOUNT | MS_BIND | keep | extra | (MS_RDONLY if ro else 0))


def locked_subs(src):
    """Mount points below src that a bind of src has to take along, as paths relative to src (usually none).
    A bind without its submounts is refused (EINVAL) when a submount below is locked, i.e. was made by a more
    privileged namespace (WSL mounts /usr/lib/wsl/* under /usr). Then only a recursive bind works, and it brings
    every submount below src. Probed with open_tree: the same kernel check, nothing gets mounted."""
    try:
        fd = os.open(src, os.O_PATH | os.O_CLOEXEC)
    except OSError:
        return []
    try:
        os.close(open_tree(fd, OPEN_TREE_CLONE))
        return []
    except OSError as e:
        if e.errno != errno.EINVAL:
            return []
    finally:
        os.close(fd)
    top = os.path.realpath(src)
    with open("/proc/self/mountinfo") as f:
        points = [m["mnt"] for m in parse_mountinfo(f.read())]
    return sorted({p[len(top):].lstrip("/") for p in points if p != top and under(p, top)})


def open_beneath(base, rel):
    """O_PATH fd for base/rel where rel may not leave base: no absolute or escaping symlinks, no /proc magic links."""
    fd = os.open(base, os.O_PATH | os.O_CLOEXEC)
    if not rel:
        return fd
    try:
        return openat2(fd, rel, os.O_PATH | os.O_CLOEXEC, RESOLVE_BENEATH | RESOLVE_NO_MAGICLINKS)
    finally:
        os.close(fd)


# ---------------------------------------------------------------- sky config text and want-tables

class Refused(Exception):
    """The daemon will not do it; the message says why."""


def load_config(path):
    """Read a sky config file into [origin, line] pairs; `include FILE` (or Plan 9's `. FILE`) pulls in another."""
    out = []
    with open(path) as f:
        for no, raw in enumerate(f, 1):
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            if line.split()[0] in ("include", "."):
                out += load_config(os.path.join(os.path.dirname(path), line.split()[1]))
            else:
                out.append([f"{os.path.basename(path)}:{no}", line])
    return out


DEV_NODES = ("null", "zero", "full", "random", "urandom")
DEV_LINKS = (("fd", "/proc/self/fd"), ("stdin", "/proc/self/fd/0"), ("stdout", "/proc/self/fd/1"), ("stderr", "/proc/self/fd/2"))
BINDLIKE = ("bind", "ksock", "devnode")


def under(path, top):
    return top == "/" or path == top or path.startswith(top + "/")


def norm(path):
    if not path.startswith("/"):
        raise Refused(f"{path}: paths in a sky are absolute")
    return posixpath.normpath("/" + path.lstrip("/"))


def src_of(row):
    return posixpath.join(row["base"], row["rel"]) if row["rel"] else row["base"]


def put(rows, row):
    """Mount a new row: it hides whatever the table had at that path or below it."""
    rows[:] = [r for r in rows if not under(r["path"], row["path"])] + [row]


def resolve_in(rows, path, who, hops=0):
    """What is `path` in this sky: (row, rest-of-path). Follows the sky's own symlink rows. Only things that come
    from somewhere (a bind, a kernel socket, a device) can be handed on; fresh tmpfs/proc/root cannot."""
    path = norm(path)
    best = max((r for r in rows if under(path, r["path"])), key=lambda r: len(r["path"]), default=None)
    if best is None:
        raise Refused(f"{path} is not in {who}'s sky")
    rest = path[len(best["path"]):].lstrip("/") if best["path"] != "/" else path.lstrip("/")
    kind = best["kind"]
    if kind == "symlink":
        if hops >= 8:
            raise Refused(f"{path}: too many symlinks in {who}'s sky")
        target = best["target"] if best["target"].startswith("/") else posixpath.join(posixpath.dirname(best["path"]), best["target"])
        return resolve_in(rows, posixpath.join(target, rest), who, hops + 1)
    if kind == "kexec":
        raise Refused(f"{path} is kernel {best['kernel']}'s name in {who}'s sky; hand it on with `mount {best['kernel']}`")
    if kind not in BINDLIKE:
        raise Refused(f"{path} is not in {who}'s sky (it falls on {best['path']}, a {kind} made fresh for {who})")
    return best, posixpath.join(best["rel"], rest) if best["rel"] and rest else (best["rel"] or rest)


def expand(word, names):
    def sub(m):
        if m.group(1) not in names:
            raise Refused(f"unknown variable ${m.group(1)}")
        return names[m.group(1)]
    return re.sub(r"\$([A-Z]+)", sub, word)


def compose(lines, starter, ctx):
    """Turn the starter's table plus config lines into the new proc's want-table.
    starter is None for the user outside the daemon (a fresh sky from scratch, host paths as sources);
    otherwise the starter's proc record: the new sky starts as a copy of the starter's and may only narrow.
    ctx: self_dir, names (variables for the user's configs), board (kernel name -> provides/depends).
    Returns (rows, settings); raises Refused."""
    who = starter["name"] if starter else "the user"
    if starter:
        rows = [dict(r, by=f"{starter['name']}:{r['by']}") for r in starter["rows"]]
        for r in rows:
            if r.get("self"):
                r.update(base=ctx["self_dir"], rel="")
        cfg = {"uid": starter["uid"], "gid": starter["gid"], "lock": True,
               "net": "host" if starter["net"] == "host" else "join"}
    else:
        rows, cfg = [], {"uid": 0, "gid": 0, "lock": True, "net": "host"}
    for origin, line in lines:
        words = line.split()
        verb, args = words[0], words[1:]
        try:
            if starter is None:
                args = [expand(a, ctx["names"]) for a in args]
            elif any("$" in a for a in args):
                raise Refused("variables are only for the user's own configs; a proc writes paths in its own sky")
            mode = "ro"
            if args[:1] == ["-w"]:
                mode, args = "rw", args[1:]
            if verb == "tmpfs" and len(args) == 1:
                p = norm(args[0])
                put(rows, {"path": p, "kind": "root" if p == "/" else "tmpfs", "mode": "ro" if p == "/" else "rw", "by": origin})
            elif verb in ("proc", "dev") and len(args) == 1 and starter and not any(
                    r["kind"] == {"proc": "proc", "dev": "devfs"}[verb] for r in starter["rows"]):
                raise Refused(f"{who} has no {verb} of its own to hand on")
            elif verb == "proc" and len(args) == 1:
                put(rows, {"path": norm(args[0]), "kind": "proc", "mode": "rw", "by": origin})
            elif verb == "dev" and len(args) == 1:
                p = norm(args[0])
                put(rows, {"path": p, "kind": "devfs", "mode": "ro", "by": origin})
                for n in DEV_NODES:
                    rows.append({"path": f"{p}/{n}", "kind": "devnode", "base": f"/dev/{n}", "rel": "", "mode": "rw", "by": origin})
                for n, t in DEV_LINKS:
                    rows.append({"path": f"{p}/{n}", "kind": "symlink", "target": t, "mode": "", "by": origin})
            elif verb == "symlink" and len(args) == 2:
                put(rows, {"path": norm(args[1]), "kind": "symlink", "target": args[0], "mode": "", "by": origin})
            elif verb == "bind" and len(args) == 2:
                dst = norm(args[1])
                if starter is None:
                    src = norm(args[0])
                    if src != ctx["self_dir"] and not os.path.lexists(src):  # $SELF is made right after this
                        raise Refused(f"{src} does not exist")
                    row = {"path": dst, "kind": "bind", "base": src, "rel": "", "mode": mode, "by": origin}
                    if src == ctx["self_dir"]:
                        row["self"] = True
                else:
                    have, rel = resolve_in(starter["rows"], args[0], who)
                    if mode == "rw" and have["mode"] != "rw":
                        raise Refused(f"{args[0]} is read-only in {who}'s sky; it cannot hand out write access")
                    try:
                        os.close(open_beneath(have["base"], rel))
                    except OSError as e:
                        raise Refused(f"{args[0]} leaves {have['path']} through a symlink or is missing ({e.strerror})")
                    row = {k: v for k, v in have.items() if k not in ("path", "by", "self")}
                    row.update(path=dst, rel=rel, mode=mode, by=origin)
                    if rel:
                        row["kind"] = "bind" if have["kind"] != "devnode" else "devnode"
                put(rows, row)
            elif verb == "mount" and 1 <= len(args) <= 2:
                k = args[0]
                if k not in ctx["board"]:
                    raise Refused(f"no kernel named {k} on the board")
                prov = ctx["board"][k]["provides"][0]
                dst = norm(args[1]) if len(args) == 2 else prov["path"]
                sock = {"path": f"/srv/{k}", "kind": "ksock", "kernel": k, "base": prov["base"], "rel": prov["rel"], "mode": "rw", "by": origin}
                if prov["kind"] == "exec":
                    if not any(r["path"] == sock["path"] for r in rows):
                        put(rows, sock)
                    put(rows, {"path": dst, "kind": "kexec", "kernel": k, "sock": sock["path"], "mode": "ro", "by": origin})
                else:
                    put(rows, dict(sock, path=dst))
            elif verb == "unmount" and len(args) == 1:
                p = norm(args[0])
                if p == "/" or not any(under(r["path"], p) for r in rows):
                    raise Refused(f"nothing at {p} to unmount")
                rows[:] = [r for r in rows if not under(r["path"], p)]
            elif verb == "net" and args in (["none"], ["host"]):
                if args == ["host"] and cfg["net"] != "host":
                    raise Refused(f"{who} has no host network to hand on")
                cfg["net"] = "own" if args == ["none"] else "host"
            elif verb == "uid" and 1 <= len(args) <= 2:
                uid, gid = int(args[0]), int(args[-1])
                if starter and (uid, gid) != (starter["uid"], starter["gid"]):
                    raise Refused(f"{who} runs as {starter['uid']}:{starter['gid']}; it cannot give out identity {uid}:{gid}")
                cfg["uid"], cfg["gid"] = uid, gid
            elif verb == "lock" and args in (["on"], ["off"], ["nolandlock"]):
                if starter and args != ["on"]:
                    raise Refused("only the user can start an unlocked sky")
                cfg["lock"] = {"on": True, "off": False}.get(args[0], args[0])  # nolandlock: the lock minus Landlock (a control)
            else:
                raise Refused(f"cannot read the line `{line}`")
        except Refused as e:
            raise Refused(f"{origin}: {e}") from None
    if not any(r["path"] == "/" for r in rows):
        raise Refused("the sky has no root (it needs a `tmpfs /` line)")
    for r in rows:  # a bind whose source has locked submounts brings them along; the table says so
        r.pop("subs", None)
        if r["kind"] in ("bind", "devnode"):
            subs = locked_subs(src_of(r))
            if subs:
                r["subs"] = subs
    return rows, cfg


def describe(row):
    k = row["kind"]
    if row.get("subs"):
        return describe({**row, "subs": None}) + f" +{len(row['subs'])} locked submounts"
    return {"root": "tmpfs", "tmpfs": "tmpfs", "devfs": "tmpfs (dev)", "proc": "proc",
            "symlink": f"-> {row.get('target')}", "bind": f"bind {src_of(row) if 'base' in row else ''}",
            "devnode": f"bind {src_of(row) if 'base' in row else ''}",
            "ksock": f"kernel {row.get('kernel')} (socket)", "kexec": f"kernel {row.get('kernel')} (exec)"}[k]


def table_text(rows, settings=None, short=None):
    """The want-table as text, one path per line (like Plan 9's `ns`)."""
    out = []
    if settings:
        out.append("# " + "  ".join(f"{k} {({True: 'on', False: 'off'}.get(v, v) if isinstance(v, bool) else v)}" for k, v in settings.items()))
    for r in sorted(rows, key=lambda r: r["path"]):
        what = describe(r)
        for long, name in (short or {}).items():
            what = what.replace(long, name)
        out.append(f"{r['path']:<20} {what:<44} {r['mode']:<2}  {r['by']}")
    return "\n".join(out)


# ---------------------------------------------------------------- building a sky (runs in a forked child)

def mkpoint(root, path, is_dir, own):
    """Make root+path exist as a mount point without going through a symlink. New directories and files are only
    made on the sky's own fresh tmpfs (st_dev in own), never inside something bound in from outside."""
    cur = root
    parts = [p for p in path.split("/") if p]
    for i, part in enumerate(parts):
        nxt, last = posixpath.join(cur, part), i == len(parts) - 1
        try:
            st = os.lstat(nxt)
        except FileNotFoundError:
            if os.stat(cur).st_dev not in own:
                raise OSError(errno.EPERM, f"cannot make mount point {path}: its parent is bound in from outside")
            if last and not is_dir:
                os.close(os.open(nxt, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC, 0o644))
            else:
                os.mkdir(nxt, 0o755)
            st = os.lstat(nxt)
        if stat.S_ISLNK(st.st_mode):
            raise OSError(errno.ELOOP, f"mount point {path} goes through a symlink")
        cur = nxt
    return cur


def build(rows, root, net, join_net=None):
    """In the forked child: a private mount namespace (and a network namespace if asked), every row mounted under
    root, then pivot_root into it. Afterwards the process sees nothing but its sky."""
    os.unshare(os.CLONE_NEWNS | (os.CLONE_NEWNET if net == "own" else 0))
    if join_net:
        fd = os.open(join_net, os.O_RDONLY | os.O_CLOEXEC)
        os.setns(fd, os.CLONE_NEWNET)
        os.close(fd)
    if net == "own":
        lo_up()
    mount(None, "/", None, MS_REC | MS_PRIVATE)

    def order(r):  # parents first; an overlay for a kernel's exec name goes right after its directory
        at = posixpath.dirname(r["path"]) if r["kind"] == "kexec" else r["path"]
        return (0 if at == "/" else at.count("/"), r["kind"] == "kexec", at)

    own, late_ro, overlays = set(), [], set()
    for r in sorted(rows, key=order):
        k, p = r["kind"], r["path"]
        t = root + (p if p != "/" else "")
        if k == "root":
            mount("tmpfs", root, "tmpfs", MS_NOSUID | MS_NODEV, "mode=0755")
            own.add(os.stat(root).st_dev)
            late_ro.append("/")
        elif k in ("tmpfs", "devfs"):
            mkpoint(root, p, True, own)
            mount("tmpfs", t, "tmpfs", MS_NOSUID | (MS_NODEV if k == "tmpfs" else 0), "mode=1777" if k == "tmpfs" else "mode=0755")
            own.add(os.stat(t).st_dev)
            if r["mode"] == "ro":
                late_ro.append(p)
        elif k == "proc":
            mkpoint(root, p, True, own)
            mount("proc", t, "proc", MS_NOSUID | MS_NODEV | MS_NOEXEC)
        elif k == "symlink":
            parent = mkpoint(root, posixpath.dirname(p), True, own)
            if os.stat(parent).st_dev not in own:
                raise OSError(errno.EPERM, f"symlink {p}: symlinks are only made on the sky's own tmpfs")
            os.symlink(r["target"], t)
        elif k in BINDLIKE:
            fd = open_beneath(r["base"], r["rel"])  # opened again here, so a symlink swapped in since is caught
            try:
                mkpoint(root, p, stat.S_ISDIR(os.fstat(fd).st_mode), own)
                mount(f"/proc/self/fd/{fd}", t, None, MS_BIND | (MS_REC if r.get("subs") else 0))
            finally:
                os.close(fd)
            for at in [t] + [f"{t}/{s}" for s in r.get("subs", [])]:
                remount(at, r["mode"] == "ro", MS_NOSUID | (0 if k == "devnode" else MS_NODEV))
        elif k == "kexec":
            at = posixpath.dirname(p)
            if at not in overlays:
                overlays.add(at)
                lower = mkpoint(root, at, True, own)
                mount("overlay", lower, "overlay", MS_NOSUID | MS_NODEV, f"lowerdir={r['layer']}:{lower}")
                remount(lower, True, MS_NOSUID | MS_NODEV)
    os.mkdir(root + "/.old")
    os.chdir(root)
    pivot_root(".", ".old")
    umount2("/.old", MNT_DETACH)
    os.rmdir("/.old")
    os.chdir("/")
    for p in late_ro:
        remount(p, True)


LOCK = ("--no-new-privs", "--inh-caps=-all", "--ambient-caps=-all", "--bounding-set=-all",
        "--securebits=+noroot,+noroot_locked,+no_setuid_fixup,+no_setuid_fixup_locked,+keep_caps_locked")


def enter(argv, env, uid, gid, lock, cwd):
    """Last step in the child: lock the sky (Landlock domain + setpriv) and exec the proc's program."""
    os.chdir(cwd)
    with open("/proc/self/setgroups") as f:  # "deny" when the user namespace was made without newgidmap
        groups_ok = f.read().strip() == "allow"
    if lock:
        if lock != "nolandlock" and landlock_abi() >= 1:  # without it same-uid procs read each other's /proc/PID/root
            landlock_scope()
        groups = "--clear-groups" if groups_ok else "--keep-groups"
        os.execve("/usr/bin/setpriv", ["setpriv", *LOCK, f"--reuid={uid}", f"--regid={gid}", groups, "--", *argv], env)
    if groups_ok:
        os.setgroups([])
    os.setresgid(gid, gid, gid)
    os.setresuid(uid, uid, uid)
    os.execvpe(argv[0], argv, env)


def live_bind(pid, base, rel, path, ro):
    """In a forked helper of the daemon: graft base/rel into the running sky of `pid` at `path`. A plain
    `nsenter + mount --bind` cannot do it (the source must be in the same mount namespace), so: clone the source
    here with open_tree, enter the sky with setns, attach the clone there with move_mount."""
    src = open_beneath(base, rel)
    tree = open_tree(src, OPEN_TREE_CLONE)
    is_dir = stat.S_ISDIR(os.fstat(src).st_mode)
    fd = os.open(f"/proc/{pid}/ns/mnt", os.O_RDONLY | os.O_CLOEXEC)
    os.setns(fd, os.CLONE_NEWNS)  # now "/" is that proc's sky
    root_ro = bool(os.statvfs("/").f_flag & MS_RDONLY)
    remount("/", False)
    try:
        mkpoint("/", path, is_dir, {os.stat("/").st_dev})
    finally:
        remount("/", root_ro)
    move_mount(tree, path)
    remount(path, ro, MS_NOSUID | MS_NODEV)


# ---------------------------------------------------------------- measuring: want-table vs /proc/<PID>/mountinfo

def parse_mountinfo(text):
    dec = lambda s: re.sub(r"\\([0-7]{3})", lambda m: chr(int(m.group(1), 8)), s)
    out = []
    for line in text.splitlines():
        a, _, b = line.partition(" - ")
        f, g = a.split(), b.split()
        out.append({"root": dec(f[3]), "mnt": dec(f[4]), "opts": f[5], "fstype": g[0], "super": g[2] if len(g) > 2 else ""})
    return out


def compare(rows, mountinfo, sky_root, real_root):
    """Want-table vs what Linux shows for the proc. sky_root is /proc/<PID>/root of the proc, real_root is
    /proc/<daemon PID>/root (where the sources live). Returns problems; empty means they match one to one."""
    problems, expected = [], set()
    mounts = {m["mnt"]: m for m in parse_mountinfo(mountinfo)}
    fstype = {"root": "tmpfs", "tmpfs": "tmpfs", "devfs": "tmpfs", "proc": "proc", "kexec": "overlay"}
    for r in rows:
        k, p = r["kind"], r["path"]
        if k == "symlink":
            try:
                got = os.readlink(sky_root + p)
            except OSError as e:
                got = e.strerror
            if got != r["target"]:
                problems.append(f"{p}: want symlink to {r['target']}, found {got}")
            continue
        at = posixpath.dirname(p) if k == "kexec" else p
        expected.add(at)
        m = mounts.get(at)
        if m is None:
            problems.append(f"{p}: in the table, but nothing is mounted at {at}")
            continue
        if k in fstype and m["fstype"] != fstype[k]:
            problems.append(f"{at}: want {fstype[k]}, mounted {m['fstype']}")
        if r["mode"] and m["opts"].split(",")[0] != r["mode"]:
            problems.append(f"{at}: want {r['mode']}, mounted {m['opts'].split(',')[0]}")
        if k in BINDLIKE:
            a, b = os.stat(sky_root + at), os.stat(real_root + src_of(r))
            if (a.st_dev, a.st_ino) != (b.st_dev, b.st_ino):
                problems.append(f"{at}: want {src_of(r)}, but it is a different file")
        for s in r.get("subs", []):  # locked submounts the bind had to bring along
            sub = posixpath.join(at, s)
            expected.add(sub)
            if sub not in mounts:
                problems.append(f"{sub}: a locked submount of {src_of(r)}, but nothing is mounted there")
                continue
            if r["mode"] and mounts[sub]["opts"].split(",")[0] != r["mode"]:
                problems.append(f"{sub}: want {r['mode']}, mounted {mounts[sub]['opts'].split(',')[0]}")
            a, b = os.stat(sky_root + sub), os.stat(real_root + posixpath.join(src_of(r), s))
            if (a.st_dev, a.st_ino) != (b.st_dev, b.st_ino):
                problems.append(f"{sub}: want {posixpath.join(src_of(r), s)}, but it is a different file")
        if k == "kexec":
            if r["layer"] not in m["super"]:
                problems.append(f"{at}: overlay does not have the layer {r['layer']}")
            with open(sky_root + p) as f:
                if f"kernel {r['kernel']}" not in f.read():
                    problems.append(f"{p}: not the stub that calls kernel {r['kernel']}")
    for extra in sorted(set(mounts) - expected):
        problems.append(f"{extra}: mounted ({mounts[extra]['fstype']}) but not in the table")
    return problems


# ---------------------------------------------------------------- talking to the daemon

def call(sock_path, req, timeout=10):
    """One request, one JSON line back."""
    with socket.socket(socket.AF_UNIX) as s:
        s.settimeout(timeout)
        s.connect(sock_path)
        s.sendall(json.dumps(req).encode() + b"\n")
        line = s.makefile("rb").readline()
    return json.loads(line) if line else {"ok": False, "error": "daemon closed the connection"}


def peer(conn):
    """(pid, uid, gid) of the other end, filled in by Linux; pid is 0 when the peer is outside our PID namespace."""
    return struct.unpack("3i", conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))


if __name__ == "__main__":
    # python3 sky.py ns DAEMON_SOCK NAME | python3 sky.py call DAEMON_SOCK '{"op": "status"}'
    if len(sys.argv) == 4 and sys.argv[1] == "ns":
        r = call(sys.argv[2], {"op": "ns", "name": sys.argv[3]})
        print(table_text(r["rows"], r["settings"]) if r.get("ok") else r)
    elif len(sys.argv) == 4 and sys.argv[1] == "call":
        print(json.dumps(call(sys.argv[2], json.loads(sys.argv[3])), indent=1))
    else:
        sys.exit("usage: sky.py ns DAEMON_SOCK NAME | sky.py call DAEMON_SOCK JSON")
