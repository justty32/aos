#!/usr/bin/env python3
"""Stacking tests for mini --kernels a,b,c: different kernels together, some of them (none: no --kernels), in other orders (uid in the middle must fail closed), the /run/user mask mini adds with a cgroup or net kernel (and --no-auto-mask), the same kind twice (net in net, cgroup in cgroup, mask on mask: the tighter one wins), mini started inside mini, pi --fake through the stack, and nothing left over afterwards; PASS/FAIL/info lines."""

import sys

sys.dont_write_bytecode = True  # before importing accept: keep the repo free of __pycache__

import argparse  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import shutil  # noqa: E402
import socket  # noqa: E402
import subprocess  # noqa: E402
import time  # noqa: E402

import accept as A  # noqa: E402  (test servers, last_json)

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.expanduser("~/.aos/scratch/proto9-mini-1127/stack")
MINI, PROBE = os.path.join(HERE, "mini.py"), os.path.join(HERE, "probe.py")
AOS_HOME = os.path.normpath(os.path.join(HERE, "..", "..", "proto8"))  # the kernels by name: $AOS_HOME/kernels
HOST = "169.254.77.1"
RESULTS = []


def log(*a):
    print(*a, flush=True)


def record(name, ok, detail, must=True):
    tag = ("PASS" if ok else "FAIL") if must else "info"
    RESULTS.append((name, tag))
    log("%-30s %s  %s" % (name, tag, detail))


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=1)


def probe_src():
    with open(PROBE) as f:
        return f.read()


def check_argv(spec):
    """probe.py check, given as source: it also runs where a uid kernel took your home away."""
    return ["python3", "-I", "-c", probe_src(), "check", json.dumps(spec)]


class Run:
    def __init__(self, rc, out, err, seen):
        self.rc, self.out, self.err, self.seen = rc, out, err, seen
        self.j = A.last_json(out)


def mini(name, kernels, argv, cwd=None, timeout=120, while_running=None, env=None, flags=()):
    """mini.py --kernels a,b,c -- ARGV (no --kernels at all when the list is empty)."""
    cmd = [sys.executable, MINI, "--name", name, "--cwd", cwd or BASE] + list(flags) + \
        (["--kernels", ",".join(kernels)] if kernels else []) + ["--"] + argv
    p = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                         env=dict(os.environ, **(env or {})))
    unit = "mini-%s-%d.scope" % (name, p.pid)
    seen = while_running(p, unit) if while_running else None
    try:
        out, err = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        p.terminate()
        out, err = p.communicate()
    return Run(p.returncode, out, err, seen)


def scope_dir(unit):
    u = os.getuid()
    return "/sys/fs/cgroup/user.slice/user-%d.slice/user@%d.service/app.slice/%s" % (u, u, unit)


def where_is_pasta(p, unit):
    """From outside, while it runs: which cgroup in the scope holds pasta (once the net kernel has moved it into
    its own k-net), and is that under the limited one."""
    t0, found = time.monotonic(), None
    while time.monotonic() - t0 < 15 and p.poll() is None:
        top = scope_dir(unit)
        for dp, _, _ in os.walk(top):
            try:
                pids = open(os.path.join(dp, "cgroup.procs")).read().split()
            except OSError:
                continue
            for q in pids:
                try:
                    cmd = open("/proc/%s/cmdline" % q, "rb").read().split(b"\0")[0]
                except OSError:
                    continue
                if cmd.endswith(b"/pasta"):
                    limited, d = False, dp
                    while len(d) > len(top):
                        try:
                            if open(os.path.join(d, "memory.max")).read().strip() != "max":
                                limited = True
                        except OSError:
                            pass
                        d = os.path.dirname(d)
                    found = {"cgroup": dp[len(top):] or "/", "under_limits": limited}
        if found and (found["cgroup"].endswith("/k-net") or time.monotonic() - t0 > 8):
            return found
        time.sleep(0.1)
    return found


# ---------------------------------------------------------------- what is left over

def snapshot(ports):
    marks = (HERE, BASE, "pasta", "aos-mini", "mini-")
    procs = {}
    for q in os.listdir("/proc"):
        if not q.isdigit() or int(q) == os.getpid():
            continue
        try:
            st = os.stat("/proc/" + q)
            cmd = open("/proc/%s/cmdline" % q, "rb").read().replace(b"\0", b" ").decode(errors="replace")
        except OSError:
            continue
        if (st.st_uid == os.getuid() or 100000 <= st.st_uid < 165536) and any(m in cmd for m in marks) and \
                os.path.basename(cmd.split(" ", 1)[0]) not in ("zsh", "bash"):
            procs[int(q)] = cmd.strip()[:120]
    netns = set()
    for q in procs:
        try:
            netns.add(os.readlink("/proc/%d/ns/net" % q))
        except OSError:
            pass
    r = subprocess.run(["systemctl", "--user", "list-units", "--all", "--plain", "--no-legend", "mini-*"],
                       capture_output=True, text=True)
    rd = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
    return {"procs": procs, "netns": netns, "units": sorted(l.split()[0] for l in r.stdout.splitlines() if l.strip()),
            "dirs": sorted(["/tmp/" + d for d in os.listdir("/tmp") if d.startswith("aos-mini-")] +
                           [rd + "/" + d for d in os.listdir(rd) if d.startswith("aos-mini-")])}


# ---------------------------------------------------------------- the kernels used here (by name, from BASE/kernels)

def make_kernels(pa, pb, pc):
    k = os.path.join(BASE, "kernels", "t")
    write_json(os.path.join(k, "base.json"), {"description": "test cgroup kernel", "program": "cg_kernel.py",
                                              "config": {"cpu": "20%", "mem": "200M", "pids": 40}})
    write_json(os.path.join(k, "net-ab.json"), {"description": "test net kernel: host ports A, B; 5 MB",
                                                "program": "net_kernel.py",
                                                "config": {"host_ports": [pa, pb], "quota": "5mb"}})
    write_json(os.path.join(k, "net-a-2mb.json"), {"description": "test net kernel: host port A; 2 MB",
                                                   "program": "net_kernel.py",
                                                   "config": {"host_ports": [pa], "quota": "2mb"}})
    write_json(os.path.join(k, "net-ac-10mb.json"), {"description": "test net kernel: host ports A, C; 10 MB",
                                                     "program": "net_kernel.py",
                                                     "config": {"host_ports": [pa, pc], "quota": "10mb"}})
    write_json(os.path.join(k, "cg-tight.json"), {"description": "test cgroup kernel, tight", "program": "cg_kernel.py",
                                                  "config": {"cpu": "20%", "mem": "200M", "pids": 30}})
    write_json(os.path.join(k, "cg-loose.json"), {"description": "test cgroup kernel, loose", "program": "cg_kernel.py",
                                                  "config": {"cpu": "80%", "mem": "500M", "pids": 100}})


# ---------------------------------------------------------------- the checks

def escape_stop(unit):
    subprocess.run(["systemctl", "--user", "stop", unit], capture_output=True)
    subprocess.run(["systemctl", "--user", "reset-failed", unit], capture_output=True)


def auto_masked(kernels, flags=()):
    """mini.py adds aos/mask/run-user when a cgroup or net kernel is on and no mask is (unless --no-auto-mask)."""
    return "--no-auto-mask" not in flags and any(("base" in k or "net" in k or "cg-" in k) for k in kernels) and \
        not any("mask" in k for k in kernels)


def judge(name, kernels, r, pa, pc, extra="", flags=()):
    """One combination: every limit of the kernels it has must hold; what it does not have is shown as info."""
    j = r.j
    auto = auto_masked(kernels, flags)
    has = lambda kind: any(kind in k for k in kernels) or (kind == "mask" and auto)
    if not j:
        record(name, False, "no answer: rc %s err %s" % (r.rc, r.err.strip()[-300:]))
        return
    bad, got = [], []
    if has("base"):
        ok = 0.15 <= j.get("cpu_ratio", 0) <= 0.25
        ok = ok and j.get("mem_end") == "killed by signal 9" and j.get("mem_reached_mb", 999) < 200
        ok = ok and j.get("forked", 99) < 40
        (got if ok else bad).append("limits cpu %s, mem %s at %s MB, forked %s" % (
            j.get("cpu_ratio"), j.get("mem_end"), j.get("mem_reached_mb"), j.get("forked")))
    if has("net"):
        a, c = j.get("tcp %s:%d" % (HOST, pa)), j.get("tcp %s:%d" % (HOST, pc))
        (got if a == "ok" and c != "ok" and "eth0" in j["ifaces"] else bad).append(
            "net A %s, C %s" % (a, (c or "")[:40]))
    else:
        (got if j["ifaces"] == ["lo"] else bad).append("no net (ifaces %s)" % j["ifaces"])
    blocked = not str(j.get("escape_busctl", "rc 0")).startswith("rc 0") and \
        not str(j.get("escape_systemd_run", "rc 0")).startswith("rc 0")
    said = "added aos/mask/run-user" in r.err
    if auto != said:
        bad.append("mask added by mini: %s, expected %s" % (said, auto))
    elif auto:
        got.append("mask added by mini")
    if has("mask") or has("uid"):
        (got if blocked else bad).append("escape blocked (busctl: %s)" % str(j.get("escape_busctl"))[:60])
    else:
        (bad if blocked else got).append("escape OPEN, as without a mask (busctl %s)" % str(j.get(
            "escape_busctl"))[:30])
    if has("uid"):
        (got if j["uid"] == 1 and "Permission" in j.get("secret", "") else bad).append(
            "uid %s, 600 file %s" % (j["uid"], j.get("secret")))
    else:
        (got if j["uid"] == 0 and j.get("secret", "").startswith("read") else bad).append("uid 0, 600 file read")
    record(name, not bad, "[%s%s] %s%s" % (",".join(kernels) or "no --kernels", " " + " ".join(flags) if flags else "",
                                           "; ".join(bad + got), extra))


def matrix(pa, pc, secret):
    log("\n== a. different kernels together, some of them, other orders")
    combos = [
        ("a_none", [], ()),
        ("a_base", ["t/base"], ()),
        ("a_base_no_auto_mask", ["t/base"], ("--no-auto-mask",)),
        ("a_base_net", ["t/base", "t/net-ab"], ()),
        ("a_base_net_no_auto_mask", ["t/base", "t/net-ab"], ("--no-auto-mask",)),
        ("a_base_mask", ["t/base", "aos/mask/run-user"], ()),
        ("a_base_mask_uid", ["t/base", "aos/mask/run-user", "aos/uid/1"], ()),
        ("a_all", ["t/base", "t/net-ab", "aos/mask/run-user", "aos/uid/1"], ()),
        ("a_mask_outermost", ["aos/mask/run-user", "t/base", "t/net-ab", "aos/uid/1"], ()),
        ("a_net_outermost", ["t/net-ab", "t/base", "aos/mask/run-user", "aos/uid/1"], ()),
        ("a_mask_inside_net", ["t/base", "t/net-ab", "aos/mask/run-user"], ()),
    ]
    for name, ks, flags in combos:
        unit = "mini-stk-%s-%d.service" % (name.replace("_", "-"), os.getpid())
        outfile = os.path.join(BASE, name + ".escape")
        spec = {"secret": secret, "tcp": [[HOST, pa], [HOST, pc]], "escape": [unit, outfile]}
        if "t/base" in ks:
            spec.update(cpu=1.5, pids=100, mem=400)
        if ("aos/mask/run-user" in ks or auto_masked(ks, flags)) and "aos/uid/1" not in ks:
            spec["umount"] = "/run/user/%d" % os.getuid()
        env = {"XDG_RUNTIME_DIR": os.environ.get("XDG_RUNTIME_DIR", ""),
               "DBUS_SESSION_BUS_ADDRESS": os.environ.get("DBUS_SESSION_BUS_ADDRESS", "")}
        argv = ["env"] + ["%s=%s" % kv for kv in env.items()] + check_argv(spec)
        watch = where_is_pasta if "t/net-ab" in ks else None
        r = mini(name.replace("_", "-"), ks, argv, cwd="/", while_running=watch, flags=flags)
        extra = ""
        if r.seen:
            extra = "; pasta in %s, %s the cgroup limits" % (r.seen["cgroup"],
                                                              "under" if r.seen["under_limits"] else "OUTSIDE")
        if "umount" in spec:
            extra += "; umount of the mask inside: %s" % r.j.get("umount")
        judge(name, ks, r, pa, pc, extra, flags)
        if "umount" in spec and r.j.get("umount") == "ok":
            record(name + "_mask_kept", False, "the agent could remove the mask")
        escape_stop(unit)
    log("\n== a. uid in the middle (the layers after it lose your home): must fail closed")
    for name, ks in (("a_uid_before_mask", ["t/base", "aos/uid/1", "aos/mask/run-user"]),
                     ("a_uid_before_net", ["t/base", "aos/uid/1", "t/net-ab"])):
        r = mini(name.replace("_", "-"), ks, ["sh", "-c", "echo AGENT_RAN"], cwd="/")
        record(name, r.rc != 0 and "AGENT_RAN" not in r.out,
               "[%s] exit %s, agent ran: %s; %s" % (" ".join(ks), r.rc, "AGENT_RAN" in r.out,
                                                    (r.err.strip().splitlines() or ["-"])[-1][:140]))


def same_kind(pa, pb, pc, ssh_file):
    log("\n== b. the same kind twice: the tighter one wins, a looser inner one changes nothing")
    r = mini("b-net-tight", ["t/net-ab", "t/net-a-2mb"],
             check_argv({"tcp": [[HOST, pa], [HOST, pb]], "get": [HOST, pa, 4_000_000, 8]}))
    j = r.j
    a, b = j.get("tcp %s:%d" % (HOST, pa)), j.get("tcp %s:%d" % (HOST, pb))
    got = j.get("get_bytes", -1)
    record("b_net_in_net_tighter", a == "ok" and b != "ok" and 1_500_000 < got < 2_000_000,
           "outer A,B 5 MB; inner A 2 MB: A %s, B %s; asked 4 MB, got %d before the cut" % (a, (b or "")[:40], got))
    r = mini("b-net-loose", ["t/net-ab", "t/net-ac-10mb"],
             check_argv({"tcp": [[HOST, pa], [HOST, pc]], "get": [HOST, pa, 8_000_000, 10]}))
    j = r.j
    a, c = j.get("tcp %s:%d" % (HOST, pa)), j.get("tcp %s:%d" % (HOST, pc))
    got = j.get("get_bytes", -1)
    warned = "not allowed by the outer" in r.err and "more than the outer" in r.err
    record("b_net_in_net_looser", a == "ok" and c != "ok" and 4_000_000 < got < 5_000_000 and warned,
           "outer A,B 5 MB; inner asks A,C 10 MB: A %s, C %s; asked 8 MB, got %d before the outer cut; inner "
           "kernel warned: %s" % (a, (c or "")[:40], got, warned))
    for name, ks in (("b_cg_in_cg_looser", ["t/cg-tight", "t/cg-loose"]),
                     ("b_cg_in_cg_tighter", ["t/cg-loose", "t/cg-tight"])):
        r = mini(name.replace("_", "-"), ks, check_argv({"cpu": 1.5, "pids": 100, "mem": 400}))
        j = r.j
        ok = 0.15 <= j.get("cpu_ratio", 0) <= 0.25 and j.get("mem_end") == "killed by signal 9" and \
            j.get("mem_reached_mb", 999) < 200 and j.get("forked", 99) < 30
        warned = "applies" in r.err
        record(name, ok and (warned or name.endswith("tighter")),
               "[%s] (20%%/200M/30 and 80%%/500M/100) cpu %s, mem %s at %s MB, forked %s; warned about the looser "
               "inner: %s" % (" ".join(ks), j.get("cpu_ratio"), j.get("mem_end"), j.get("mem_reached_mb"),
                              j.get("forked"), warned))
    if ssh_file:
        unit = "mini-stk-mask2-%d.service" % os.getpid()
        env = ["env", "XDG_RUNTIME_DIR=%s" % os.environ.get("XDG_RUNTIME_DIR", ""),
               "DBUS_SESSION_BUS_ADDRESS=%s" % os.environ.get("DBUS_SESSION_BUS_ADDRESS", "")]
        r = mini("b-mask2", ["aos/mask/run-user", "aos/mask/ssh"],
                 env + ["sh", "-c", 'cat $AOS_ENV/.aos/interfaces/aos/mask/paths; exec "$@"', "sh"] +
                 check_argv({"secret": ssh_file, "escape": [unit, os.path.join(BASE, "mask2.escape")]}))
        j = r.j
        blocked = not str(j.get("escape_busctl", "rc 0")).startswith("rc 0")
        paths = [l for l in r.out.splitlines() if l.startswith(("tmpfs", "hole", "absent"))]
        record("b_mask_on_mask", blocked and "No such file" in j.get("secret", "") and len(paths) == 2,
               "run-user then ssh: escape %s; %s: %s; declared %s" % (
                   "blocked" if blocked else "OPEN", ssh_file.replace(os.path.expanduser("~"), "~"),
                   j.get("secret"), paths))
        escape_stop(unit)


def nested(pa, pb, pc):
    log("\n== c. mini inside mini (the agent starts another sandbox): never looser than the outer one")
    outer = ["t/cg-tight", "aos/mask/run-user", "t/net-ab"]
    env = ["env", "MINI_PASTA=%s" % os.environ["MINI_PASTA"], "MINI_KERNELS_PATH=%s" % os.environ["MINI_KERNELS_PATH"],
           "AOS_HOME=%s" % os.environ["AOS_HOME"],
           "XDG_RUNTIME_DIR=%s" % os.environ.get("XDG_RUNTIME_DIR", ""),
           "DBUS_SESSION_BUS_ADDRESS=%s" % os.environ.get("DBUS_SESSION_BUS_ADDRESS", "")]
    for name, inner in (("c_mini_in_mini_looser", ["t/cg-loose", "t/net-ac-10mb"]), ("c_mini_in_mini_bare", [])):
        unit = "mini-stk-%s-%d.service" % (name.replace("_", "-"), os.getpid())
        spec = {"cpu": 1.5, "pids": 100, "mem": 400, "tcp": [[HOST, pa], [HOST, pb], [HOST, pc]],
                "escape": [unit, os.path.join(BASE, name + ".escape")]}
        argv = env + ["python3", MINI, "--name", "inner"] + (["--kernels", ",".join(inner)] if inner else []) + ["--", "sh", "-c",
                      "cat $AOS_ENV/.aos/kernels | tr '\\n' ','; echo; exec \"$@\"", "sh"] + check_argv(spec)
        r = mini(name.replace("_", "-"), outer, argv)
        j = r.j
        tcp = {p: j.get("tcp %s:%d" % (HOST, p)) for p in (pa, pb, pc)}
        blocked = not str(j.get("escape_busctl", "rc 0")).startswith("rc 0")
        lim = 0.15 <= j.get("cpu_ratio", 0) <= 0.25 and j.get("mem_end") == "killed by signal 9" and \
            j.get("mem_reached_mb", 999) < 200 and j.get("forked", 99) < 30
        want_b = "ok" if not inner else "closed"
        net_ok = tcp[pa] == "ok" and tcp[pc] != "ok" and ((tcp[pb] == "ok") == (want_b == "ok"))
        chain = (r.out.strip().splitlines() or [""])[0]
        record(name, bool(j) and lim and net_ok and blocked,
               "outer [%s], inner [%s]: chain %s; cpu %s, mem %s at %s MB, forked %s; A %s, B %s (want %s), C %s; "
               "escape %s" % (" ".join(outer), " ".join(inner) or "no kernels", chain, j.get("cpu_ratio"),
                              j.get("mem_end"), j.get("mem_reached_mb"), j.get("forked"), tcp[pa],
                              "ok" if tcp[pb] == "ok" else "closed", want_b, "ok" if tcp[pc] == "ok" else "closed",
                              "blocked" if blocked else "OPEN"))
        escape_stop(unit)


def pi_in_stack():
    """pi --fake (the real agent, a fake brain) through the whole stack, like accept.py's pi_fake but by names."""
    sys.path.insert(0, A.PI_SANDBOX)
    import aos_pi
    node, pkg = aos_pi.find_node()
    cli = os.path.join(pkg, "dist", "bundle", "cli.js")
    if not (os.path.exists(node) and os.path.exists(cli)):
        record("d_pi_fake_stack", True, "no node/pi here; skipped", must=False)
        return
    log("\n== d. pi --fake through base + net + mask (fake brain outside behind 127.0.0.1:PORT)")
    brain, state, work, home = (os.path.join(BASE, x) for x in ("brain", "brain-state", "work", "pihome"))
    for d in (state, work):
        os.makedirs(d)
    for f, t in A.PROJECT.items():
        with open(os.path.join(work, f), "w") as fh:
            fh.write(t)
    write_json(os.path.join(BASE, "fake_script.json"), A.FAKE_SCRIPT)
    blog = open(os.path.join(BASE, "brain.log"), "w")
    bp = subprocess.Popen([sys.executable, os.path.join(A.PI_SANDBOX, "llm_kernel.py"), "--dir", brain,
                           "--upstream", "http://unused.invalid/v1", "--model", A.MODEL, "--limit", "50",
                           "--budget", os.path.join(state, "budget.json"), "--log", os.path.join(state, "ledger.jsonl"),
                           "--fake", "--fake-script", os.path.join(BASE, "fake_script.json"), "--no-relay"],
                          stdout=blog, stderr=subprocess.STDOUT)
    bridge = None
    try:
        end = time.monotonic() + 10
        while not os.path.exists(os.path.join(brain, "sock")) and time.monotonic() < end:
            time.sleep(0.05)
        bridge = A.Bridge(os.path.join(brain, "sock"))
        k = os.path.join(BASE, "kernels", "t")
        write_json(os.path.join(k, "base-pi.json"), {"program": "cg_kernel.py",
                                                     "config": {"cpu": "200%", "mem": "2G", "pids": 512}})
        write_json(os.path.join(k, "net-pi.json"), {"program": "net_kernel.py", "config": {"host_ports": [bridge.port]}})
        models = {"providers": {"aosllm": {
            "name": "fake brain via the net kernel", "baseUrl": "http://%s:%d/v1" % (HOST, bridge.port),
            "api": "openai-completions", "apiKey": "fake-key",
            "compat": {"supportsDeveloperRole": False, "supportsStore": False, "maxTokensField": "max_tokens"},
            "models": [{"id": A.MODEL, "name": A.MODEL, "contextWindow": 200000, "maxTokens": 4096,
                        "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0}}]}}}
        os.makedirs(os.path.join(home, ".pi", "agent"))
        write_json(os.path.join(home, ".pi", "agent", "models.json"), models)
        write_json(os.path.join(home, ".pi", "agent", "settings.json"),
                   {"defaultProvider": "aosllm", "defaultModel": A.MODEL, "retry": {"baseDelayMs": 500}})
        env = ["env", "PATH=%s:/usr/bin:/bin" % os.path.dirname(node), "HOME=%s" % home, "PI_OFFLINE=1",
               "PI_SKIP_VERSION_CHECK=1", "PI_TELEMETRY=0"]
        t0 = time.monotonic()
        r = mini("pi", ["t/base-pi", "t/net-pi", "aos/mask/run-user"],
                 env + [node, cli, "--mode", "json", "--thinking", "off", "--provider", "aosllm", "--model", A.MODEL,
                        A.TASK], cwd=work, timeout=180)
        sec = round(time.monotonic() - t0, 1)
        events = []
        for line in r.out.splitlines():
            try:
                events.append(json.loads(line))
            except ValueError:
                pass
        o = aos_pi.pi_outcome(events)
        hello = open(os.path.join(work, "hello.txt")).read().strip() if os.path.exists(
            os.path.join(work, "hello.txt")) else None
        tools = [t for t, ok in o["tools"] if ok]
        record("d_pi_fake_stack", o["done"] and tools == ["read", "write", "edit", "bash"] and hello == "pinecone",
               "[t/base-pi t/net-pi aos/mask/run-user] %s in %ss (exit %s), tools %s, hello.txt %r" % (
                   "DONE" if o["done"] else "NOT DONE", sec, r.rc, o["tools"], hello))
        if not o["done"]:
            log(r.err[-800:])
    finally:
        if bridge:
            bridge.close()
        bp.terminate()
        bp.wait()
        blog.close()


def main():
    ap = argparse.ArgumentParser(description="Stacking tests for mini --kernels (PASS/FAIL/info lines).")
    ap.add_argument("--pasta", help="pasta binary (default: on PATH, else %s)" % A.DEFAULT_PASTA)
    ap.add_argument("--keep", action="store_true", help="keep %s afterwards" % BASE)
    ap.add_argument("--no-pi", action="store_true", help="skip pi --fake")
    a = ap.parse_args()
    pasta = a.pasta or shutil.which("pasta") or A.DEFAULT_PASTA
    if not os.access(pasta, os.X_OK):
        sys.exit("stack_test: error: PastaMissing no pasta at %s (install passt, or --pasta PATH)" % pasta)
    shutil.rmtree(BASE, ignore_errors=True)
    os.makedirs(BASE)
    os.environ["MINI_PASTA"] = pasta
    os.environ["MINI_KERNELS_PATH"] = os.path.join(BASE, "kernels")  # t/...; aos/... from this checkout's proto8
    os.environ["AOS_HOME"] = AOS_HOME
    servers = [A.start_server() for _ in range(3)]
    pa, pb, pc = (s.server_address[1] for s in servers)
    before = snapshot((pa, pb, pc))
    log("test servers on the host: A 127.0.0.1:%d, B 127.0.0.1:%d, C 127.0.0.1:%d; inside they are %s:<port>" % (
        pa, pb, pc, HOST))
    make_kernels(pa, pb, pc)
    secret = os.path.join(BASE, "secret600")
    with open(secret, "w") as f:
        f.write("top secret\n")
    os.chmod(secret, 0o600)
    sshd = os.path.expanduser("~/.ssh")
    ssh_file = os.path.join(sshd, sorted(os.listdir(sshd))[0]) if os.path.isdir(sshd) and os.listdir(sshd) else None
    t0 = time.monotonic()
    try:
        matrix(pa, pc, secret)
        same_kind(pa, pb, pc, ssh_file)
        nested(pa, pb, pc)
        if not a.no_pi:
            pi_in_stack()
    finally:
        for s in servers:
            s.shutdown()
            s.server_close()
    time.sleep(1)
    after = snapshot((pa, pb, pc))
    left = {k: (sorted(set(after[k]) - set(before[k])) if k != "procs" else
                {p: c for p, c in after[k].items() if p not in before[k]}) for k in after}
    open_ports = [p for p in (pa, pb, pc) if socket.socket().connect_ex(("127.0.0.1", p)) == 0]
    record("cleanup", not any(left.values()) and not open_ports, "left over: %s; test servers still open: %s" % (
        {k: v for k, v in left.items() if v} or "nothing", open_ports or "none"))
    fails = [n for n, t in RESULTS if t == "FAIL"]
    log("\nSUMMARY %s (%d PASS, %d FAIL, %d info, %.0fs)%s" % (
        "ok" if not fails else "FAILED", sum(t == "PASS" for _, t in RESULTS), len(fails),
        sum(t == "info" for _, t in RESULTS), time.monotonic() - t0, ": " + ", ".join(fails) if fails else ""))
    if not a.keep and not fails:
        shutil.rmtree(BASE, ignore_errors=True)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
