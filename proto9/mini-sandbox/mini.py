#!/usr/bin/env python3
"""mini: runs one command in the smallest sandbox, the one line systemd-run --user --scope (cpu, mem, pids) + unshare -UrmpnC (own user, mount, pid, net, cgroup namespaces), optional net kernel and uid N; or, with --kernels, nests kernels found by name (each one runs the next inside the environment it set up) around the command; everything else is left open."""

import argparse
import json
import os
import pwd
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

def kernel_dirs():
    """Where names are looked up, first match wins: $MINI_KERNELS_PATH (folders separated by :), else kernels/
    next to this file."""
    return [d for d in (os.environ.get("MINI_KERNELS_PATH") or os.path.join(HERE, "kernels")).split(":") if d]


def find_kernel(name):
    """A name (aos/base-low) -> {name, program, config, file}. A name that is a path (has a leading / or ./, or
    ends in .json) is that file."""
    if name.startswith(("/", "./", "../", "~")) or name.endswith(".json"):
        path = os.path.abspath(os.path.expanduser(name))
        if not os.path.isfile(path):
            raise ValueError("kernel %s: no such file" % name)
    else:
        if ".." in name.split("/") or not name.strip("/"):
            raise ValueError("kernel name %r: want a/b/c, no .." % name)
        found = [os.path.join(d, name + ".json") for d in kernel_dirs() if os.path.isfile(os.path.join(d, name + ".json"))]
        if not found:
            raise ValueError("kernel %s: not found in %s" % (name, ":".join(kernel_dirs())))
        path = found[0]
    with open(path) as f:
        k = json.load(f)
    if not isinstance(k, dict) or not isinstance(k.get("program"), str):
        raise ValueError("kernel %s (%s): want {\"program\": ..., \"config\": {...}}" % (name, path))
    bad = set(k) - {"description", "program", "config"}
    if bad:
        raise ValueError("kernel %s: unknown keys %s" % (name, ", ".join(sorted(bad))))
    prog = k["program"] if os.path.isabs(k["program"]) else os.path.join(HERE, k["program"])
    if not os.path.isfile(prog):
        raise ValueError("kernel %s: program %s not found" % (name, prog))
    return {"name": name, "program": prog, "config": k.get("config", {}), "file": path}


def parse_kernels_args(args):
    o = {"kernels": [], "name": "mini", "cwd": os.getcwd(), "dry_run": False, "print": False}
    if "--" not in args:
        fail("ArgumentsBad", "want: mini.py [--name N] [--cwd D] [--dry-run|--print] --kernels NAME... -- COMMAND...", 2)
    i = args.index("--")
    own, o["argv"] = args[:i], args[i + 1:]
    k, in_names = 0, False
    while k < len(own):
        a = own[k]
        if a in ("--name", "--cwd") and k + 1 < len(own):
            o[a[2:]] = own[k + 1]
            k += 2
            in_names = False
        elif a in ("--dry-run", "--print"):
            o[a[2:].replace("-", "_")] = True
            k += 1
            in_names = False
        elif a == "--kernels":
            in_names = True
            k += 1
        elif in_names and not a.startswith("--"):
            o["kernels"].append(a)
            k += 1
        else:
            fail("ArgumentsBad", "unknown option %r" % a, 2)
    if not o["argv"]:
        fail("ArgumentsBad", "nothing to run after --", 2)
    if not str(o["name"]).replace("-", "").replace("_", "").isalnum():
        fail("ArgumentsBad", "--name: letters, digits, - and _ only", 2)
    return o


def root_env(run):
    """The folder the outermost kernel reads: nothing declared yet, plus who you are on the machine. Inside a
    sandbox that has one already (mini started by the agent), start from a copy of that one."""
    root = os.path.join(run, "0-root")
    outer = os.environ.get("AOS_ENV")
    if outer and os.path.isdir(os.path.join(outer, ".aos")):
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
    try:
        ks = [find_kernel(n) for n in o["kernels"]]
    except (OSError, ValueError) as e:
        fail("KernelNotFound", str(e), 2)
    scoped = os.readlink("/proc/self/ns/cgroup") == INIT_CGROUP_NS  # outside any sandbox: make a scope
    unit = "mini-%s-%d.scope" % (o["name"], os.getpid()) if scoped else None
    env = default_env()
    if unit:
        env["MINI_UNIT"] = unit
    with open(os.path.join(HERE, "leaf.py")) as f:
        leaf_src = f.read()
    chain = []
    for k in ks:
        chain += [sys.executable, "-I", k["program"], "--name", k["name"], "--json", json.dumps(k["config"]), "--"]
    chain += [sys.executable, "-I", "-c", leaf_src, "stage1", "--env-json", json.dumps(env, sort_keys=True), "--"]
    chain += o["argv"]
    line = (["systemd-run", "--user", "--scope", "--quiet", "--collect", "--unit", unit, "-p", "Delegate=yes", "--"]
            if scoped else []) + chain
    if o["dry_run"] or o["print"]:
        shown = shlex.join(line).replace(shlex.quote(leaf_src), '"$(cat %s)"' % os.path.join(HERE, "leaf.py"))
        print(("mini: " if o["print"] else "") + shown, file=sys.stderr if o["print"] else sys.stdout, flush=True)
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


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "--inside":
        return inside(sys.argv[2:])
    if "--kernels" in sys.argv[1:sys.argv.index("--") if "--" in sys.argv else None]:
        return kernels_main(sys.argv[1:])
    if len(sys.argv) >= 2 and sys.argv[1] == "--give-back":
        if len(sys.argv) < 3:
            fail("ArgumentsBad", "--give-back DIR...", 2)
        return give_back(sys.argv[2:])
    ap = argparse.ArgumentParser(prog=PROG, description="Run one command in the minimal sandbox described by a "
                                 "json config; exits with the command's code (128+N if killed by signal N).",
                                 epilog="Also: mini.py --give-back DIR... (chown files written as uid N back to you); mini.py [--name N] "
                                 "[--cwd D] [--dry-run|--print] --kernels NAME... -- COMMAND... (nest kernels by name, "
                                 "see README)")
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
