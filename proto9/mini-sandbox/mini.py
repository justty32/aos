#!/usr/bin/env python3
"""mini: runs one command in the smallest sandbox, the one line systemd-run --user --scope (cpu, mem, pids) + unshare -UrmpnC (own user, mount, pid, net, cgroup namespaces), optional net kernel and uid N; or, with --kernels a,b,c, nests kernels found by name in $AOS_HOME/kernels around the command (bundles, merge, use/replace/without, one of each kernel, uid innermost, the /run/user mask, orders that go around an llm kernel refused: see chain.py), neighbouring cgroup and mask kernels flattened into one layer, the user namespaces counted before anything starts, what the agent gets written to .aos/effective/ and .aos/lock.json (--explain, --lock, --diff); everything else is left open."""

import os
import sys

sys.dont_write_bytecode = True  # mini.py imports its kernels' modules: keep the repo free of __pycache__
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import argparse  # noqa: E402
import json  # noqa: E402
import pwd  # noqa: E402
import shlex  # noqa: E402
import shutil  # noqa: E402
import signal  # noqa: E402
import socket  # noqa: E402
import subprocess  # noqa: E402
import tempfile  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402

import chain  # noqa: E402
import effective  # noqa: E402
import nest  # noqa: E402

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

KERNELS_USAGE = ("mini.py [--name N] [--cwd D] [--dry-run|--print] [--kernels NAME,NAME,...] [--no-auto-mask] "
                 "-- COMMAND...; mini.py --explain|--lock --kernels NAME,...; mini.py --diff A B (A, B: lock files "
                 "or NAME,NAME,...)")


def layer_line(k):
    """The line a kernel adds to .aos/kernels (the kernel writes it; mini shows the same with --dry-run)."""
    return "%s %s" % (k["kind"], k["name"]) + (" from %s" % ">".join(k["from"]) if k.get("from") else "")


def parse_kernels_args(args):
    o = {"kernels": [], "name": "mini", "cwd": os.getcwd(), "dry_run": False, "print": False, "auto_mask": True,
         "explain": False, "lock": False, "diff": None, "argv": []}
    i = args.index("--") if "--" in args else len(args)
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
        elif a == "--diff" and k + 2 < len(own):
            o["diff"] = own[k + 1:k + 3]
            k += 3
        elif a in ("--dry-run", "--print", "--explain", "--lock"):
            o[a[2:].replace("-", "_")] = True
            k += 1
        elif a == "--no-auto-mask":
            o["auto_mask"] = False
            k += 1
        else:
            fail("ArgumentsBad", "unknown option %r (want: %s)" % (a, KERNELS_USAGE), 2)
    if not o["argv"] and not (o["explain"] or o["lock"] or o["diff"]):
        fail("ArgumentsBad", ("nothing to run after --" if "--" in args else "want: " + KERNELS_USAGE), 2)
    if not str(o["name"]).replace("-", "").replace("_", "").isalnum():
        fail("ArgumentsBad", "--name: letters, digits, - and _ only", 2)
    return o


def outer_dir():
    return os.environ.get("AOS_ENV") or "/"  # the rule: $AOS_ENV first, / when it is not set


def outer_layers():
    """How many layers an outer environment already has (mini started inside a sandbox), so the numbers go on."""
    try:
        with open(os.path.join(outer_dir(), ".aos", "kernels")) as f:
            return len([l for l in f.read().splitlines() if l.strip()])
    except OSError:
        return 0


def outer_lock():
    """The layers of the chain we run inside (its .aos/lock.json), if any."""
    try:
        with open(os.path.join(outer_dir(), ".aos", "lock.json")) as f:
            return [r for r in json.load(f).get("layers", [])]
    except (OSError, ValueError, AttributeError):
        return []


def root_env(run, lock, eff):
    """The folder the outermost kernel reads: nothing declared yet, plus who you are on the machine, what the whole
    chain gives the agent (effective/, computed before starting) and the lock. Inside a sandbox that has one already
    (mini started by the agent), start from a copy of that one."""
    root = os.path.join(run, "0-root")
    outer = outer_dir()
    if os.path.isdir(os.path.join(outer, ".aos", "interfaces")) or (outer != "/" and os.path.isdir(os.path.join(
            outer, ".aos"))):
        shutil.copytree(os.path.join(outer, ".aos"), os.path.join(root, ".aos"), symlinks=True)
        shutil.rmtree(os.path.join(root, ".aos", "effective"), ignore_errors=True)  # the outer chain's: ours replaces it
    else:
        os.makedirs(os.path.join(root, ".aos"))
        with open("/proc/self/uid_map") as f:
            init = f.read().split() == ["0", "0", "4294967295"]
        su = subid_range("/etc/subuid") if init else None
        for name, text in (("kernels", ""), ("host_uid", "%d\n" % os.getuid() if init else ""),
                           ("host_subuid", "%d %d\n" % su if su else "")):
            with open(os.path.join(root, ".aos", name), "w") as f:
                f.write(text)
    effective.write(os.path.join(root, ".aos"), eff, lock)
    for dp, dns, fns in os.walk(root):
        os.chmod(dp, 0o755)
        for fn in fns:
            os.chmod(os.path.join(dp, fn), 0o644)
    return root


def userns_limit():
    """(limit, how it was found): nested user namespaces this chain may use from here. $MINI_USERNS_MAX if set (for
    tests); otherwise what Linux still allows below this point (33 from the machine), minus chain.USERNS_KEEP kept
    for sandboxes the agent starts inside when mini runs on the machine itself (inside a sandbox, mini is such a
    sandbox: the outer mini kept those for it)."""
    if os.environ.get("MINI_USERNS_MAX", "").isdigit():
        return int(os.environ["MINI_USERNS_MAX"]), "MINI_USERNS_MAX"
    free = nest.userns_room(40)
    keep = chain.USERNS_KEEP if nest.in_init_userns() else 0
    return free - keep, "%d can still be nested below this point, %d kept for sandboxes the agent starts inside" % (
        free, keep)


def plan_text(ks, groups, first):
    out = []
    for g in groups:
        nums = [first + i for i in g]
        span = "%d" % nums[0] if len(nums) == 1 else "%d-%d" % (nums[0], nums[-1])
        out.append("[%s %s]" % (chain.group_kind(ks, g), span))
    return out


def build_lock(names, auto_mask=True):
    """Names -> everything mini knows before starting: kernels, notes, the plan, the lock, effective values."""
    ks, notes, added = chain.expand_all(names, auto_mask)
    groups = chain.plan(ks)
    need, parts = chain.userns_needed(ks, groups)
    first = outer_layers() + 1
    rs = effective.records(ks, groups, first, outer_lock())
    lock = {"kernels": names, "layers": rs, "plan": [[first + i for i in g] for g in groups],
            "plan_text": plan_text(ks, groups, first), "userns": need,
            "userns_parts": ["%s %d" % (w, n) for w, n in parts], "userns_by_kind": chain.userns_summary(ks, groups)}
    return ks, notes, added, groups, lock, effective.compute(rs)


def lock_or_names(arg, auto_mask):
    if os.path.isfile(arg):
        try:
            return effective.load_lock(arg)
        except (OSError, ValueError) as e:
            fail("ArgumentsBad", "%s: %s" % (arg, e), 2)
    return build_lock([n.strip() for n in arg.split(",") if n.strip()], auto_mask)[4]


def flat_argv(ks, g):
    layers = [{"kind": ks[i]["kind"], "name": ks[i]["name"], "from": ">".join(ks[i]["from"]),
               "config": ks[i]["config"]} for i in g]
    return [sys.executable, "-I", os.path.join(HERE, "flat_kernel.py"), "--json", json.dumps({"layers": layers}), "--"]


def kernels_main(args):
    o = parse_kernels_args(args)
    try:
        if o["diff"]:
            a, b = (lock_or_names(x, o["auto_mask"]) for x in o["diff"])
            sys.exit(1 if effective.diff(a, b, sys.stdout) else 0)
        ks, notes, added, groups, lock, eff = build_lock(o["kernels"], o["auto_mask"])
    except chain.KernelError as e:
        fail(e.code, str(e), 2)
    except (OSError, ValueError) as e:
        fail("KernelNotFound", str(e), 2)
    limit, why = userns_limit()
    need = lock["userns"]
    limit_line = "%d needed (%s); limit here %d (%s)%s" % (need, lock["userns_by_kind"], limit, why,
                                                            "; TOO MANY, mini would refuse" if need > limit else "")
    if o["explain"]:
        effective.explain(lock, eff, notes + ([{"text": "added %s innermost (a cgroup, net or llm kernel is on)" %
                                                chain.AUTO_MASK}] if added else []), limit_line, sys.stdout)
        return
    if o["lock"]:
        print(json.dumps(lock, indent=1))
        return
    to = sys.stderr if not o["dry_run"] else sys.stdout
    for n in notes:
        if n["run"] or o["dry_run"]:
            print("%s%s" % ("# note: " if o["dry_run"] else "mini: ", n["text"]), file=to, flush=True)
    if need > limit:
        fail("KernelTooDeep", "this chain needs %d nested user namespaces (%s), more than the %d allowed here (%s). "
             "To need fewer: write cgroup and mask kernels next to each other (they run as one layer), merge kernels "
             "of one kind ({\"merge\": [...]} in a %s), use fewer net kernels (2 each) and llm kernels; mini.py "
             "--explain shows the plan. Nothing was started." % (need, lock["userns_by_kind"], limit, why,
                                                                  chain.CHAIN), 2)
    if added:
        print("mini: added %s innermost%s (a cgroup, net or llm kernel is on; --no-auto-mask leaves /run/user/%d open)"
              % (chain.AUTO_MASK, ", just before the uid kernel" if ks and ks[-1]["kind"] == "uid" else "",
                 os.getuid()), file=sys.stderr, flush=True)
    if eff.looser and not o["dry_run"]:
        print("mini: %d setting(s) written looser than an outer layer's; the outer ones apply (details: mini.py "
              "--explain)" % len(eff.looser), file=sys.stderr, flush=True)
    scoped = os.readlink("/proc/self/ns/cgroup") == INIT_CGROUP_NS  # outside any sandbox: make a scope
    unit = "mini-%s-%d.scope" % (o["name"], os.getpid()) if scoped else None
    env = default_env()
    if unit:
        env["MINI_UNIT"] = unit
    with open(os.path.join(HERE, "leaf.py")) as f:
        leaf_src = f.read()
    line = []
    for g in groups:
        if len(g) > 1:
            line += flat_argv(ks, g)
            continue
        k = ks[g[0]]
        line += [sys.executable, "-I", k["program"], "--name", k["name"]] + \
            (["--from", ">".join(k["from"])] if k.get("from") else []) + ["--json", json.dumps(k["config"]), "--"]
    line += [sys.executable, "-I", "-c", leaf_src, "stage1", "--env-json", json.dumps(env, sort_keys=True), "--"]
    line += o["argv"]
    line = (["systemd-run", "--user", "--scope", "--quiet", "--collect", "--unit", unit, "-p", "Delegate=yes", "--"]
            if scoped else []) + line
    if o["dry_run"] or o["print"]:  # the layers after expanding bundles (numbered as in .aos/kernels), then the line
        to = sys.stderr if o["print"] else sys.stdout
        pre = "mini: " if o["print"] else "# "
        for r, k in zip(lock["layers"][-len(ks):] if ks else [], ks):
            print("%slayer %d: %s%s  (file %s)" % (pre, r["layer"], layer_line(k), " (added by mini)" if k.get("auto")
                                                   else "", r["file"] if isinstance(r["file"], str) else
                                                   " + ".join(r["file"])), file=to)
        print("%splan: %d real layers instead of %d: %s; user namespaces: %s" % (
            pre, len(groups), len(ks), " ".join(lock["plan_text"]), limit_line), file=to)
        text = shlex.join(line).replace(shlex.quote(leaf_src), '"$(cat %s)"' % os.path.join(HERE, "leaf.py"))
        print(("mini: " if o["print"] else "") + text, file=to, flush=True)
        if o["dry_run"]:
            return
    run = tempfile.mkdtemp(prefix="aos-mini-", dir="/tmp")  # readable by a uid N further in (your home is not)
    os.chmod(run, 0o711)
    cenv = dict(os.environ, AOS_ENV=root_env(run, lock, eff))
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
    sweep(unit, p.pid)
    shutil.rmtree(run, ignore_errors=True)
    sys.exit(128 - rc if rc < 0 else rc)


def sweep(unit, pgid):
    """The chain has ended (its outermost process is gone); anything still in the scope (or, inside a sandbox, in
    the process group) is left over from a layer that failed half way (e.g. util-linux unshare's id-mapping helper
    when a user namespace could not be made, which holds our stdout and the scope open for ever): kill it, so mini
    returns and nothing is left behind."""
    if unit:
        r = subprocess.run(["systemctl", "--user", "show", "-p", "ActiveState", "--value", unit], capture_output=True,
                           text=True)
        if r.stdout.strip() in ("active", "activating", "deactivating"):
            subprocess.run(["systemctl", "--user", "kill", "--signal=KILL", unit], capture_output=True)
            for _ in range(50):
                r = subprocess.run(["systemctl", "--user", "show", "-p", "ActiveState", "--value", unit],
                                   capture_output=True, text=True)
                if r.stdout.strip() not in ("active", "activating", "deactivating"):
                    break
                time.sleep(0.1)
    else:
        try:
            os.killpg(pgid, signal.SIGKILL)
        except OSError:
            pass


def kernels_mode(args):
    """--kernels-style options, or a -- with no config file before it (no --kernels = no kernels at all)."""
    own = args[:args.index("--")] if "--" in args else args
    if any(a.startswith("--kernels") or a in ("--name", "--cwd", "--no-auto-mask", "--explain", "--lock", "--diff")
           for a in own):
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
                                 epilog="Also: mini.py --give-back DIR... (chown files written as uid N back to you); " +
                                 KERNELS_USAGE + " (nest kernels by name, see README)")
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
