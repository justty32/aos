#!/usr/bin/env python3
"""mini: runs one command in the smallest sandbox, the one line systemd-run --user --scope (cpu, mem, pids) + unshare -UrmpnC (own user, mount, pid, net, cgroup namespaces), optional net kernel and uid N; or, with --kernels a,b,c, nests kernels found by name in $AOS_HOME/kernels (a name may be a bundle: a folder whose _chain.json lists more names, expanded in place; each kernel runs the next inside the environment it set up; a cgroup, net or llm kernel brings the /run/user mask along; a net kernel inside an llm kernel that lets the llm's upstream through is refused) around the command; everything else is left open."""

import argparse
import ipaddress
import json
import os
import pwd
import re
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading

PROG = "mini"
HERE = os.path.dirname(os.path.abspath(__file__))
NET_DECL = os.path.join(".aos", "interfaces", "aos", "net")
KEYS = {"name", "argv", "cwd", "env", "cpu", "mem", "pids", "net", "uid"}
INIT_CGROUP_NS = "cgroup:[4026531835]"


def fail(code, msg, exit_code=1):
    sys.stdout.flush()
    print("%s: error: %s %s" % (PROG, code, msg), file=sys.stderr, flush=True)
    sys.exit(exit_code)


def default_env():
    e = {"PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8"}
    for k in ("HOME", "USER", "LOGNAME", "TERM"):
        if k in os.environ:
            e[k] = os.environ[k]
    return e


def load(path, argv_override):
    with open(path) as f:
        c = json.load(f)
    if not isinstance(c, dict):
        raise ValueError("want a json object")
    bad = set(c) - KEYS
    if bad:
        raise ValueError("unknown keys: %s (known: %s)" % (", ".join(sorted(bad)), ", ".join(sorted(KEYS))))
    if argv_override:
        c["argv"] = argv_override
    if not isinstance(c.get("argv"), list) or not c["argv"] or not all(isinstance(x, str) for x in c["argv"]):
        raise ValueError("argv: want a non-empty list of strings")
    c.setdefault("name", "mini")
    c.setdefault("cwd", os.getcwd())
    c.setdefault("env", default_env())
    c.setdefault("net", "none")
    c.setdefault("uid", 0)
    if not str(c["name"]).replace("-", "").replace("_", "").isalnum():
        raise ValueError("name: letters, digits, - and _ only")
    if not isinstance(c["uid"], int) or c["uid"] < 0:
        raise ValueError("uid: want 0 (you) or N >= 1 (a subordinate uid)")
    if c.get("cpu") is not None:
        cpu = str(c["cpu"])
        c["cpu"] = cpu if cpu.endswith("%") else cpu + "%"
    if c.get("pids") is not None and (not isinstance(c["pids"], int) or c["pids"] < 1):
        raise ValueError("pids: want an integer >= 1")
    return c


def subid_range(path):
    user = pwd.getpwuid(os.getuid()).pw_name
    try:
        with open(path) as f:
            for line in f:
                p = line.strip().split(":")
                if len(p) == 3 and p[0] in (user, str(os.getuid())):
                    return int(p[1]), int(p[2])
    except OSError:
        pass
    return None


# ------------------------------------------------------------ the net kernel's side

def net_decl(d):
    """The aos/net declaration of dir d: (ctl socket path)."""
    try:
        with open(os.path.join(d, NET_DECL, "kind")) as f:
            kind = f.read().strip()
        with open(os.path.join(d, NET_DECL, "ctl")) as f:
            ctl = f.read().strip()
    except OSError as e:
        raise ValueError("%s does not declare aos/net (%s)" % (d, e.strerror))
    if kind != "veth":
        raise ValueError("%s declares aos/net kind %r, mini knows only veth" % (d, kind))
    return os.path.join(d, ctl)


def ctl_call(sock, req):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(15)
    try:
        s.connect(sock)
        s.sendall((json.dumps(req) + "\n").encode())
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = s.recv(4096)
            if not chunk:
                break
            buf += chunk
    finally:
        s.close()
    return json.loads(buf or b'{"ok": false, "error": "no answer"}')


# ------------------------------------------------------------ the line

def build(c, info=None, gate=None):
    """The command line, outermost first. info: the net kernel's answer to info (None = no net kernel)."""
    sd = ["systemd-run", "--user", "--scope", "--quiet", "--collect", "--unit", c["unit"]]
    if c.get("cpu"):
        sd += ["-p", "CPUQuota=" + c["cpu"]]
    if c.get("mem"):
        sd += ["-p", "MemoryMax=" + str(c["mem"]), "-p", "MemorySwapMax=0"]
    if c.get("pids"):
        sd += ["-p", "TasksMax=%d" % c["pids"]]
    line = sd
    if info:  # the sandbox's user ns becomes a child of the net kernel's outer one (so its rules stay out of reach)
        line += ["nsenter", "--user=/proc/%s/ns/user" % info["outer_pid"], "--preserve-credentials"]
    if c["uid"] == 0:
        line += ["unshare", "-UrmpnC"]
    else:
        if info:
            start, count = 1, info["subids"]  # the outer ns already maps 1.. to your subordinate ids
            sg = start
        else:
            su, sgr = subid_range("/etc/subuid"), subid_range("/etc/subgid")
            if not su or not sgr:
                raise ValueError("uid %d needs a range for you in /etc/subuid and /etc/subgid" % c["uid"])
            start, sg, count = su[0], sgr[0], min(su[1], sgr[1])
        if not count or c["uid"] > count:
            raise ValueError("uid %d is outside the subordinate range (%d ids)" % (c["uid"], count or 0))
        line += ["unshare", "-U", "--map-user=0", "--map-users=1:%d:%d" % (start, count),
                 "--map-group=0", "--map-groups=1:%d:%d" % (sg, count), "-mpnC"]
    line += ["--fork", "--kill-child", "--mount-proc"]
    line += [sys.executable, "-I", os.path.abspath(__file__), "--inside"] + (["--gate", gate] if gate else []) + ["--"]
    if c["uid"]:
        line += [shutil.which("setpriv") or "setpriv", "--reuid=%d" % c["uid"], "--regid=%d" % c["uid"],
                 "--clear-groups", "--inh-caps=-all", "--bounding-set=-all", "--no-new-privs"]
    env = dict(c["env"], MINI_UNIT=c["unit"])  # which scope the command runs in (its cgroup ns hides it)
    line += ["env", "-i"] + ["%s=%s" % kv for kv in sorted(env.items())] + c["argv"]
    return line


def inside(argv):
    """First program in the sandbox (root there): wait for the net kernel if asked, bring lo up, exec the rest."""
    gate = None
    if argv[:1] == ["--gate"]:
        gate, argv = argv[1], argv[2:]
    if argv[:1] == ["--"]:
        argv = argv[1:]
    if gate:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(gate)
        s.sendall(b"ready\n")
        ans = s.makefile().readline().strip()
        s.close()
        if ans != "ok":
            fail("NetFailed", ans or "no answer from mini outside", 125)
    else:
        subprocess.run(["ip", "link", "set", "lo", "up"], stderr=subprocess.DEVNULL)
    try:
        os.execvp(argv[0], argv)
    except OSError as e:
        fail("ExecFailed", "%s: %s" % (argv[0], e.strerror), 127)


def gatekeeper(listener, ctl, result):
    """Outside: take the one connection from the sandbox, have the net kernel pull a veth into its netns."""
    try:
        conn, _ = listener.accept()
    except OSError as e:
        result["error"] = "the sandbox never called (%s)" % e
        return
    finally:
        listener.close()
    with conn:
        import struct
        pid = struct.unpack("3i", conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")))[0]
        conn.makefile().readline()
        try:
            r = ctl_call(ctl, {"op": "attach", "pid": pid})
        except (OSError, ValueError) as e:
            r = {"ok": False, "error": str(e)}
        result.update(r)
        conn.sendall(b"ok\n" if r.get("ok") else ("%s\n" % r.get("error", "attach failed")).encode())


def give_back(paths):
    """Hand files a sandbox with uid N wrote back to you: chown -R 0:0 inside the same id map (no root)."""
    su, sg = subid_range("/etc/subuid"), subid_range("/etc/subgid")
    if not su or not sg:
        fail("NoSubids", "no range for you in /etc/subuid or /etc/subgid", 2)
    n = min(su[1], sg[1])
    argv = ["unshare", "--user", "--map-user=0", "--map-users=1:%d:%d" % (su[0], n), "--map-group=0",
            "--map-groups=1:%d:%d" % (sg[0], n), "--", "chown", "-R", "0:0"] + paths
    print(shlex.join(argv), flush=True)
    sys.exit(subprocess.call(argv))


# ------------------------------------------------------------ --kernels: nested kernels found by name

KINDS = {"cg_kernel.py": "cgroup", "net_kernel.py": "net", "mask_kernel.py": "mask", "uid_kernel.py": "uid",
         "llm_kernel.py": "llm"}
AUTO_MASK = "aos/mask/run-user"
AUTO_MASK_FOR = ("cgroup", "net", "llm")  # limits that one call over D-Bus to systemd --user would get around
KERNELS_USAGE = ("mini.py [--name N] [--cwd D] [--dry-run|--print] [--kernels NAME,NAME,...] [--no-auto-mask] "
                 "-- COMMAND...")


def kernel_dirs():
    """Where names are looked up, first match wins: the folders in $MINI_KERNELS_PATH (separated by :), then
    $AOS_HOME/kernels."""
    dirs = [d for d in os.environ.get("MINI_KERNELS_PATH", "").split(":") if d]
    if os.environ.get("AOS_HOME"):
        dirs.append(os.path.join(os.environ["AOS_HOME"], "kernels"))
    return dirs


def kernel_program(prog, jsonfile):
    """A bare file name (cg_kernel.py) is one of mini's own programs, next to mini.py; otherwise $VARS and ~ are
    expanded and a relative path is relative to the folder of the kernel's json file."""
    if "/" not in prog and "$" not in prog:
        return os.path.join(HERE, prog)
    p = os.path.expanduser(os.path.expandvars(prog))
    return p if os.path.isabs(p) else os.path.normpath(os.path.join(os.path.dirname(jsonfile), p))


CHAIN = "_chain.json"   # a folder with this file is a bundle: one name that stands for a chain of kernels
MAX_BUNDLE_DEPTH = 8    # bundles inside bundles, at most this deep


class KernelError(ValueError):
    """Finding or expanding kernel names went wrong; code is the error code mini prints (exit 2)."""

    def __init__(self, code, msg):
        super().__init__(msg)
        self.code = code


def is_path(name):
    return name.startswith(("/", "./", "../", "~")) or name.endswith(".json")


def check_name(name):
    if ".." in name.split("/") or not name.strip("/") or "//" in name or name.startswith("_") or "/_" in name:
        raise KernelError("KernelNotFound", "kernel name %r: want a/b/c (no .., no part starting with _)" % name)


def lookup(name, dirs):
    """A name in these folders, first folder that has it wins: ("file", NAME.json) or ("bundle", NAME/). Both in one
    folder is an error: which one is meant is not guessed."""
    for d in dirs:
        f, b = os.path.join(d, name + ".json"), os.path.join(d, name)
        hf, hb = os.path.isfile(f), os.path.isfile(os.path.join(b, CHAIN))
        if hf and hb:
            raise KernelError("KernelNameClash", "kernel %s: both %s (one kernel) and %s/ (a bundle, it has %s) "
                              "exist; rename one of them" % (name, f, b, CHAIN))
        if hf:
            return "file", f
        if hb:
            return "bundle", b
    raise KernelError("KernelNotFound", "kernel %s: not found in %s" % (name, ":".join(dirs)))


def load_kernel(name, path):
    """One kernel file -> {name, kind, program, config, file, from}."""
    with open(path) as f:
        k = json.load(f)
    if not isinstance(k, dict) or not isinstance(k.get("program"), str):
        raise KernelError("KernelNotFound", "kernel %s (%s): want {\"program\": ..., \"config\": {...}}" % (name, path))
    bad = set(k) - {"description", "program", "config"}
    if bad:
        raise KernelError("KernelNotFound", "kernel %s: unknown keys %s" % (name, ", ".join(sorted(bad))))
    prog = kernel_program(k["program"], path)
    if not os.path.isfile(prog):
        raise KernelError("KernelNotFound", "kernel %s: program %s not found" % (name, prog))
    return {"name": name, "kind": KINDS.get(os.path.basename(prog), "other"), "program": prog,
            "config": k.get("config", {}), "file": path, "from": []}


def resolve(entry, bundle=None):
    """A name -> (full name, "file" or "bundle", path). At the top (--kernels) and for a name with a / inside a
    bundle: looked up in $MINI_KERNELS_PATH, then $AOS_HOME/kernels. Inside a bundle (bundle = (its name, its
    folder)), a name without / (or starting with ./) is one of the bundle's own: cg in aos/base is aos/base/cg, found
    in that folder only. A path (/..., ~..., ....json; at the top also ./...) is that file or bundle folder."""
    if bundle and (entry.startswith("./") or "/" not in entry):
        local = entry[2:] if entry.startswith("./") else entry
        check_name(local)
        bname, bdir = bundle
        kind, path = lookup(local, [bdir])
        return (bname.rstrip("/") + "/" + local if not is_path(bname) else os.path.join(bdir, local)), kind, path
    if entry.startswith(("/", "~")) or (not bundle and is_path(entry)):
        path = os.path.abspath(os.path.expanduser(entry))
        if os.path.basename(path) == CHAIN and os.path.isfile(path):
            return entry, "bundle", os.path.dirname(path)
        if os.path.isdir(path) and os.path.isfile(os.path.join(path, CHAIN)):
            return entry, "bundle", path
        if not os.path.isfile(path):
            raise KernelError("KernelNotFound", "kernel %s: no such file (or folder with %s)" % (entry, CHAIN))
        return entry, "file", path
    check_name(entry)
    dirs = kernel_dirs()
    if not dirs:
        raise KernelError("KernelNotFound", "kernel %s: nowhere to look (set AOS_HOME, whose kernels/ holds the "
                          "kernels by name, or MINI_KERNELS_PATH)" % entry)
    kind, path = lookup(entry, dirs)
    return entry, kind, path


def load_chain(name, folder):
    path = os.path.join(folder, CHAIN)
    try:
        with open(path) as f:
            c = json.load(f)
    except (OSError, ValueError) as e:
        raise KernelError("KernelBundleBad", "bundle %s: %s: %s" % (name, path, e))
    if not isinstance(c, dict) or set(c) - {"description", "chain"}:
        raise KernelError("KernelBundleBad", "bundle %s: %s: want {\"description\": ..., \"chain\": [names, "
                          "outermost first]}" % (name, path))
    chain = c.get("chain")
    if not isinstance(chain, list) or not chain or not all(isinstance(x, str) and x.strip() for x in chain):
        raise KernelError("KernelBundleBad", "bundle %s: %s: chain must be a non-empty list of names" % (name, path))
    return [x.strip() for x in chain]


def expand(entry, bundle=None, stack=()):
    """A name -> the kernels it stands for, outermost first: one kernel, or a bundle's chain expanded in place (each
    kernel remembers the bundles it came from in "from", outermost first). stack: the bundles we are inside, as
    (name, real folder); a bundle that is already in it is a loop, more than MAX_BUNDLE_DEPTH is too deep."""
    full, kind, path = resolve(entry, bundle)
    if kind == "file":
        k = load_kernel(full, path)
        k["from"] = [n for n, _ in stack]
        return [k]
    real = os.path.realpath(path)
    trail = [n for n, _ in stack] + [full]
    if real in [r for _, r in stack]:
        raise KernelError("KernelBundleLoop", "bundles include each other: %s" % " -> ".join(trail))
    if len(stack) >= MAX_BUNDLE_DEPTH:
        raise KernelError("KernelBundleTooDeep", "bundles nested more than %d deep: %s" % (
            MAX_BUNDLE_DEPTH, " -> ".join(trail)))
    out = []
    for e in load_chain(full, path):
        out += expand(e, (full, path), tuple(stack) + ((full, real),))
    return out


def find_kernel(name):
    """A name -> the list of kernels it stands for (one, or a bundle's chain expanded)."""
    return expand(name)


def shown(k):
    """aos/base/cg (from aos/base)."""
    return k["name"] + (" (from %s)" % ">".join(k["from"]) if k.get("from") else "")


def layer_line(k):
    """The line a kernel adds to .aos/kernels (the kernel writes it; mini shows the same with --dry-run)."""
    return "%s %s" % (k["kind"], k["name"]) + (" from %s" % ">".join(k["from"]) if k.get("from") else "")


def parse_kernels_args(args):
    o = {"kernels": [], "name": "mini", "cwd": os.getcwd(), "dry_run": False, "print": False, "auto_mask": True}
    if "--" not in args:
        fail("ArgumentsBad", "want: " + KERNELS_USAGE, 2)
    i = args.index("--")
    own, o["argv"] = args[:i], args[i + 1:]
    k = 0
    while k < len(own):
        a = own[k]
        if a.startswith("--kernels="):
            a, own = "--kernels", own[:k] + ["--kernels", a.split("=", 1)[1]] + own[k + 1:]
        if a in ("--name", "--cwd", "--kernels") and k + 1 < len(own):
            if a == "--kernels":  # one argument, names separated by commas (several --kernels add up)
                o["kernels"] += [n.strip() for n in own[k + 1].split(",") if n.strip()]
            else:
                o[a[2:]] = own[k + 1]
            k += 2
        elif a in ("--dry-run", "--print"):
            o[a[2:].replace("-", "_")] = True
            k += 1
        elif a == "--no-auto-mask":
            o["auto_mask"] = False
            k += 1
        else:
            fail("ArgumentsBad", "unknown option %r (want: %s)" % (a, KERNELS_USAGE), 2)
    if not o["argv"]:
        fail("ArgumentsBad", "nothing to run after --", 2)
    if not str(o["name"]).replace("-", "").replace("_", "").isalnum():
        fail("ArgumentsBad", "--name: letters, digits, - and _ only", 2)
    return o


def covers_run_user(k):
    """Does this mask kernel cover /run/user/<uid> (its default when it lists no paths)?"""
    paths = k["config"].get("paths")
    if paths is None:
        return True
    return any((p if isinstance(p, str) else p.get("path", "")).rstrip("/") in ("/run/user/{uid}",
               "/run/user/%d" % os.getuid(), "/run/user") for p in paths)


def add_auto_mask(ks):
    """With a cgroup, net or llm kernel on and nothing covering /run/user/<uid>: add aos/mask/run-user, innermost
    (just before a uid kernel, which must stay last), so nothing inside can ask systemd --user over D-Bus for a
    process outside every limit. Returns the new list and whether it added one."""
    if not any(k["kind"] in AUTO_MASK_FOR for k in ks) or any(k["kind"] == "mask" and covers_run_user(k) for k in ks):
        return ks, False
    try:
        m = find_kernel(AUTO_MASK)
        if len(m) != 1 or m[0]["kind"] != "mask":
            raise ValueError("not one mask kernel")
        m = m[0]
    except (OSError, ValueError):  # not in the kernels folders: the same thing, built in
        m = {"name": AUTO_MASK, "kind": "mask", "program": os.path.join(HERE, "mask_kernel.py"),
             "config": {"paths": [{"path": "/run/user/{uid}", "how": "tmpfs"}]}, "file": "(built in)", "from": []}
    m = dict(m, auto=True)
    at = next((i for i, k in enumerate(ks) if k["kind"] == "uid"), len(ks))
    return ks[:at] + [m] + ks[at:], True


def port_in(spec, port):
    """A net kernel port spec (4000, "4000", "4000-4010", or {"port": ...}) covers this port?"""
    if isinstance(spec, dict):
        spec = spec.get("port")
    a, _, b = str(spec).partition("-")
    try:
        return int(a) <= port <= int(b or a)
    except ValueError:
        return False


def llm_bypasses(ks):
    """An llm kernel whose upstream is ip:port, and a net kernel further in that lets that very ip:port through
    (host_ports for this machine's loopback, an allow rule for any other address): the agent could talk to the
    upstream directly, around the llm kernel's count and model list. One sentence per such pair."""
    out = []
    for i, k in enumerate(ks):
        up = str(k["config"].get("upstream", "")) if k["kind"] == "llm" else ""
        m = re.match(r"^https?://(\[[^]]*\]|[^/:]+)(?::(\d+))?(/|$)", up)
        if not m:
            continue
        host, port = m.group(1).strip("[]"), int(m.group(2) or (443 if up.startswith("https") else 80))
        try:
            ip = ipaddress.ip_address("127.0.0.1" if host == "localhost" else host)
        except ValueError:
            continue  # a host name: no address to compare with
        for n in ks[i + 1:]:
            how = lets_through(n["config"], ip, port) if n["kind"] == "net" else None
            if how:
                out.append("%s (net kernel) lets %s:%d through (its %s), and it sits inside %s (llm kernel), whose "
                           "upstream is %s: the agent could reach the upstream directly, around the llm kernel's count "
                           "and model list. Put %s before %s in --kernels (outside it), or take port %d out of its %s"
                           % (shown(n), host, port, how, shown(k), up, n["name"], k["name"], port, how))
    return out


def lets_through(c, ip, port):
    """Which part of a net kernel's config lets tcp to ip:port through: "host_ports" (this machine's loopback),
    "allow list", or None. Loopback inside is the sandbox's own lo, so for it only host_ports count."""
    if ip.is_loopback:
        return "host_ports" if any(port_in(p, port) for p in c.get("host_ports") or []) else None
    for r in c.get("allow") or []:
        try:
            to = ipaddress.ip_network(str(r.get("to")), strict=False)
        except (AttributeError, ValueError):
            continue
        if r.get("proto", "tcp") == "tcp" and port_in(r, port) and ip.version == to.version and ip in to:
            return "allow list"
    return None


def outer_layers():
    """How many layers an outer environment already has (mini started inside a sandbox), so the numbers go on."""
    outer = os.environ.get("AOS_ENV") or "/"
    try:
        with open(os.path.join(outer, ".aos", "kernels")) as f:
            return len([l for l in f.read().splitlines() if l.strip()])
    except OSError:
        return 0


def root_env(run):
    """The folder the outermost kernel reads: nothing declared yet, plus who you are on the machine. Inside a
    sandbox that has one already (mini started by the agent), start from a copy of that one."""
    root = os.path.join(run, "0-root")
    outer = os.environ.get("AOS_ENV") or "/"  # the rule: $AOS_ENV first, / when it is not set
    if os.path.isdir(os.path.join(outer, ".aos", "interfaces")) or (outer != "/" and os.path.isdir(os.path.join(
            outer, ".aos"))):
        shutil.copytree(os.path.join(outer, ".aos"), os.path.join(root, ".aos"), symlinks=True)
    else:
        os.makedirs(os.path.join(root, ".aos"))
        with open("/proc/self/uid_map") as f:
            init = f.read().split() == ["0", "0", "4294967295"]
        su = subid_range("/etc/subuid") if init else None
        for name, text in (("kernels", ""), ("host_uid", "%d\n" % os.getuid() if init else ""),
                           ("host_subuid", "%d %d\n" % su if su else "")):
            with open(os.path.join(root, ".aos", name), "w") as f:
                f.write(text)
    for dp, dns, fns in os.walk(root):
        os.chmod(dp, 0o755)
        for fn in fns:
            os.chmod(os.path.join(dp, fn), 0o644)
    return root


def kernels_main(args):
    o = parse_kernels_args(args)
    ks = []
    try:
        for n in o["kernels"]:
            ks += find_kernel(n)
    except KernelError as e:
        fail(e.code, str(e), 2)
    except (OSError, ValueError) as e:
        fail("KernelNotFound", str(e), 2)
    bad = llm_bypasses(ks)  # before anything runs (--dry-run too): this order is refused, not warned about
    if bad:
        more = " (and %d more like it)" % (len(bad) - 1) if len(bad) > 1 else ""
        fail("KernelOrderBad", "%s%s. Nothing was started." % (bad[0], more), 2)
    if o["auto_mask"]:
        ks, added = add_auto_mask(ks)
        if added:
            print("mini: added %s innermost (a cgroup, net or llm kernel is on; --no-auto-mask leaves /run/user/%d "
                  "open)" % (AUTO_MASK, os.getuid()), file=sys.stderr, flush=True)
    scoped = os.readlink("/proc/self/ns/cgroup") == INIT_CGROUP_NS  # outside any sandbox: make a scope
    unit = "mini-%s-%d.scope" % (o["name"], os.getpid()) if scoped else None
    env = default_env()
    if unit:
        env["MINI_UNIT"] = unit
    with open(os.path.join(HERE, "leaf.py")) as f:
        leaf_src = f.read()
    chain = []
    for k in ks:
        chain += [sys.executable, "-I", k["program"], "--name", k["name"]] + \
            (["--from", ">".join(k["from"])] if k.get("from") else []) + ["--json", json.dumps(k["config"]), "--"]
    chain += [sys.executable, "-I", "-c", leaf_src, "stage1", "--env-json", json.dumps(env, sort_keys=True), "--"]
    chain += o["argv"]
    line = (["systemd-run", "--user", "--scope", "--quiet", "--collect", "--unit", unit, "-p", "Delegate=yes", "--"]
            if scoped else []) + chain
    if o["dry_run"] or o["print"]:  # the layers after expanding bundles (numbered as in .aos/kernels), then the line
        to = sys.stderr if o["print"] else sys.stdout
        first = outer_layers() + 1
        for i, k in enumerate(ks):
            print("%slayer %d: %s%s" % ("mini: " if o["print"] else "# ", first + i, layer_line(k),
                                        " (added by mini)" if k.get("auto") else ""), file=to)
        text = shlex.join(line).replace(shlex.quote(leaf_src), '"$(cat %s)"' % os.path.join(HERE, "leaf.py"))
        print(("mini: " if o["print"] else "") + text, file=to, flush=True)
        if o["dry_run"]:
            return
    run = tempfile.mkdtemp(prefix="aos-mini-", dir="/tmp")  # readable by a uid N further in (your home is not)
    os.chmod(run, 0o711)
    cenv = dict(os.environ, AOS_ENV=root_env(run))
    if unit:
        cenv["MINI_UNIT"] = unit
    try:
        p = subprocess.Popen(line, cwd=o["cwd"], env=cenv, start_new_session=not unit)
    except OSError as e:
        shutil.rmtree(run, ignore_errors=True)
        fail("StartFailed", "%s: %s" % (line[0], e.strerror))

    def stop(sig):
        """The whole scope gets the signal; 5 s later whatever is left gets SIGKILL (the leaf's unshare holds
        SIGTERM back and the agent as pid 1 may ignore it). Inside a sandbox there is no scope: the process group."""
        if unit:
            subprocess.run(["systemctl", "--user", "kill", "--signal=%d" % sig, unit], capture_output=True)
        else:
            try:
                os.killpg(p.pid, sig)
            except OSError:
                pass
        try:
            p.wait(5)
            return
        except subprocess.TimeoutExpired:
            pass
        if unit:
            subprocess.run(["systemctl", "--user", "kill", "--signal=KILL", unit], capture_output=True)
        else:
            try:
                os.killpg(p.pid, signal.SIGKILL)
            except OSError:
                pass

    def forward(sig, _):
        threading.Thread(target=stop, args=(sig,), daemon=True).start()
    for s_ in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(s_, forward)
    rc = p.wait()
    shutil.rmtree(run, ignore_errors=True)
    sys.exit(128 - rc if rc < 0 else rc)


def kernels_mode(args):
    """--kernels-style options, or a -- with no config file before it (no --kernels = no kernels at all)."""
    own = args[:args.index("--")] if "--" in args else args
    if any(a.startswith("--kernels") or a in ("--name", "--cwd", "--no-auto-mask") for a in own):
        return True
    return "--" in args and not [a for a in own if not a.startswith("-")]


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "--inside":
        return inside(sys.argv[2:])
    if len(sys.argv) >= 2 and sys.argv[1] == "--give-back":
        if len(sys.argv) < 3:
            fail("ArgumentsBad", "--give-back DIR...", 2)
        return give_back(sys.argv[2:])
    if kernels_mode(sys.argv[1:]):
        return kernels_main(sys.argv[1:])
    ap = argparse.ArgumentParser(prog=PROG, description="Run one command in the minimal sandbox described by a "
                                 "json config; exits with the command's code (128+N if killed by signal N).",
                                 epilog="Also: mini.py --give-back DIR... (chown files written as uid N back to you); mini.py [--name N] "
                                 "[--cwd D] [--dry-run|--print] [--kernels NAME,NAME,...] [--no-auto-mask] -- COMMAND... "
                                 "(nest kernels by name, see README)")
    ap.error = lambda m: fail("ArgumentsBad", "%s (usage: %s --help)" % (m, PROG), 2)
    ap.add_argument("config", help="json: name, argv, cwd, env, cpu, mem, pids, net, uid (see README)")
    ap.add_argument("argv", nargs="*", help="after --: the command, instead of the config's argv")
    ap.add_argument("--dry-run", action="store_true", help="print the line that would run, run nothing")
    ap.add_argument("--print", action="store_true", help="print the line on stderr, then run it")
    if len(sys.argv) == 1:
        ap.error("no arguments")
    a = ap.parse_args()
    try:
        c = load(a.config, a.argv)
    except (OSError, ValueError) as e:
        fail("ConfigBad", "%s: %s" % (a.config, e), 2)
    c["unit"] = "mini-%s-%d.scope" % (c["name"], os.getpid())
    info, ctl = None, None
    if c["net"] != "none":
        try:
            ctl = net_decl(c["net"])
            info = ctl_call(ctl, {"op": "info"}) if not a.dry_run or os.path.exists(ctl) else None
        except (OSError, ValueError) as e:
            if not a.dry_run:
                fail("NetKernelUnreachable", "%s: %s" % (c["net"], e))
        if info is not None and not info.get("ok"):
            fail("NetKernelRefused", info.get("error", "?"))
        if info is None:
            info = {"outer_pid": "<outer-pid>", "subids": 65536}
    tmp = None
    gate = None
    if info:
        tmp = tempfile.mkdtemp(prefix="aos-mini-", dir=os.environ.get("XDG_RUNTIME_DIR") or None)
        gate = os.path.join(tmp, "gate.sock")
    try:
        line = build(c, info, gate)
    except ValueError as e:
        fail("ConfigBad", str(e), 2)
    if a.dry_run:
        print(shlex.join(line))
        if tmp:
            os.rmdir(tmp)
        return
    if a.print:
        print("mini: " + shlex.join(line), file=sys.stderr, flush=True)
    result = {}
    t = None
    if gate:
        lst = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        lst.bind(gate)
        lst.listen(1)
        lst.settimeout(30)
        t = threading.Thread(target=gatekeeper, args=(lst, ctl, result), daemon=True)
        t.start()
    try:
        p = subprocess.Popen(line, cwd=c["cwd"])
    except OSError as e:
        fail("StartFailed", "%s: %s" % (line[0], e.strerror))

    def stop(sig):
        """unshare blocks SIGTERM/SIGINT while it waits, and the sandbox's pid 1 ignores signals it has no handler
        for: signal the whole scope, and if it is still there after 5 s, kill unshare (--kill-child then SIGKILLs
        pid 1, which ends the pid namespace)."""
        subprocess.run(["systemctl", "--user", "kill", "--signal=%d" % sig, c["unit"]], capture_output=True)
        try:
            p.wait(5)
        except subprocess.TimeoutExpired:
            p.kill()

    def forward(sig, _):
        threading.Thread(target=stop, args=(sig,), daemon=True).start()
    for s in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(s, forward)
    rc = p.wait()
    if t:
        t.join(1)
    if tmp:
        shutil.rmtree(tmp, ignore_errors=True)
    if gate and not result.get("ok"):
        print("%s: error: NetFailed %s" % (PROG, result.get("error", "the sandbox never reached the net kernel")),
              file=sys.stderr, flush=True)
    sys.exit(128 - rc if rc < 0 else rc)


if __name__ == "__main__":
    main()
