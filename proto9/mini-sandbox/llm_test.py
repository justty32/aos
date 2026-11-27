#!/usr/bin/env python3
"""Acceptance run for the nested llm kernel of mini: pi --fake through aos/base-low,aos/llm/fake with and without a net kernel (four tools, ledger = pi's turns), a used-up budget (429), no way to LiteLLM 4000 around the kernel, the brain without any network, llm inside a net kernel, llm on llm, the auto mask, a net kernel inside an llm kernel that lets its upstream through (refused, nothing started; net first runs), the budget carried over through state, optionally one real model run, and nothing left over afterwards; PASS/FAIL/info lines."""

import sys

sys.dont_write_bytecode = True  # before importing accept: keep the repo free of __pycache__

import argparse  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import shutil  # noqa: E402
import socket  # noqa: E402
import subprocess  # noqa: E402
import time  # noqa: E402

import accept as A  # noqa: E402  (test servers, PROJECT, TASK, last_json)
import stack_test as S  # noqa: E402  (snapshot, check_argv, probe source)

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.expanduser("~/.aos/scratch/proto9-mini-1127/llm")
MINI = os.path.join(HERE, "mini.py")
AOS_HOME = os.path.normpath(os.path.join(HERE, "..", "..", "proto8"))  # this checkout's kernels
HOST = "169.254.77.1"
LITELLM = 4000
RELAY_PORT = 8787
RESULTS = S.RESULTS  # one list, so S.record and ours add up


def log(*a):
    print(*a, flush=True)


record = S.record


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=1)


def demo(name):
    """A kernel from $AOS_HOME/kernels, as a dict."""
    with open(os.path.join(AOS_HOME, "kernels", name + ".json")) as f:
        return json.load(f)


def test_kernel(tname, base_name, **over):
    """t/<tname>: a copy of a kernel from $AOS_HOME/kernels with some config changed (e.g. a state folder we can read
    afterwards)."""
    k = demo(base_name)
    k["config"] = dict(k["config"], **over)
    write_json(os.path.join(BASE, "kernels", "t", tname + ".json"), k)


def state_of(tname):
    return os.path.join(BASE, "state", tname)


def ledger(tname):
    p = os.path.join(state_of(tname), "ledger.jsonl")
    return [json.loads(l) for l in open(p)] if os.path.exists(p) else []


def budget(tname):
    p = os.path.join(state_of(tname), "budget.json")
    return json.load(open(p)) if os.path.exists(p) else None


def mini(name, kernels, argv, cwd=None, timeout=180, flags=()):
    cmd = [sys.executable, MINI, "--name", name, "--cwd", cwd or BASE] + list(flags) + \
        ["--kernels", ",".join(kernels), "--"] + argv
    p = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        out, err = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        p.terminate()
        out, err = p.communicate()
    return S.Run(p.returncode, out, err, None)


def summary_line(err):
    """The llm kernel's last words: 'llm-kernel: NAME: N answered (...), M refused, ...'."""
    return next((l for l in reversed(err.splitlines()) if l.startswith("llm-kernel: ") and " answered " in l), "")


def answered(err):
    l = summary_line(err)
    try:
        return int(l.split(": ", 2)[2].split()[0])
    except (IndexError, ValueError):
        return -1


def host_ip():
    """This machine's address on its own network (where a LiteLLM on 0.0.0.0 would also listen)."""
    try:
        r = json.loads(subprocess.run(["ip", "-j", "route", "get", "1.1.1.1"], capture_output=True, text=True).stdout)
        return r[0]["prefsrc"]
    except (ValueError, KeyError, IndexError):
        return None


def escape_env():
    return ["env", "XDG_RUNTIME_DIR=%s" % os.environ.get("XDG_RUNTIME_DIR", ""),
            "DBUS_SESSION_BUS_ADDRESS=%s" % os.environ.get("DBUS_SESSION_BUS_ADDRESS", "")]


# ---------------------------------------------------------------- pi

class Pi:
    def __init__(self):
        sys.path.insert(0, A.PI_SANDBOX)
        import aos_pi
        self.aos_pi = aos_pi
        self.node, pkg = aos_pi.find_node()
        self.cli = os.path.join(pkg, "dist", "bundle", "cli.js")
        self.ok = os.path.exists(self.node) and os.path.exists(self.cli)

    def home(self, model):
        """pi's home: its provider is http://127.0.0.1:8787/v1, which the relay (inside, on pi's own lo) joins to the
        declared socket."""
        home = os.path.join(BASE, "pihome-" + model)
        if not os.path.exists(home):
            models = {"providers": {"aosllm": {
                "name": "the llm kernel through the relay", "baseUrl": "http://127.0.0.1:%d/v1" % RELAY_PORT,
                "api": "openai-completions", "apiKey": "fake-key",
                "compat": {"supportsDeveloperRole": False, "supportsStore": False, "maxTokensField": "max_tokens"},
                "models": [{"id": model, "name": model, "contextWindow": 200000, "maxTokens": 4096,
                            "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0}}]}}}
            write_json(os.path.join(home, ".pi", "agent", "models.json"), models)
            write_json(os.path.join(home, ".pi", "agent", "settings.json"),
                       {"defaultProvider": "aosllm", "defaultModel": model, "retry": {"baseDelayMs": 500}})
        return home

    def work(self, name):
        w = os.path.join(BASE, "work-" + name)
        os.makedirs(w)
        for f, t in A.PROJECT.items():
            with open(os.path.join(w, f), "w") as fh:
                fh.write(t)
        return w

    def run(self, name, kernels, model="fake-model", timeout=240):
        """pi in the sandbox, behind the relay the llm kernel put out (found through $AOS_ENV)."""
        work = self.work(name)
        relay = 'exec node "$(cut -d" " -f1 "$AOS_ENV/.aos/interfaces/aos/llm/relay")" --port %d -- "$@"' % RELAY_PORT
        argv = ["env", "PATH=%s:/usr/bin:/bin" % os.path.dirname(self.node), "HOME=%s" % self.home(model),
                "PI_OFFLINE=1", "PI_SKIP_VERSION_CHECK=1", "PI_TELEMETRY=0", "sh", "-c", relay, "sh", self.cli,
                "--mode", "json", "--thinking", "off", "--provider", "aosllm", "--model", model, A.TASK]
        t0 = time.monotonic()
        r = mini(name, kernels, argv, cwd=work, timeout=timeout)
        r.sec = round(time.monotonic() - t0, 1)
        with open(os.path.join(BASE, name + ".out"), "w") as f:
            f.write(r.out + "\n--- stderr\n" + r.err)
        events = []
        for line in r.out.splitlines():
            try:
                events.append(json.loads(line))
            except ValueError:
                pass
        r.o = self.aos_pi.pi_outcome(events)
        hp = os.path.join(work, "hello.txt")
        r.hello = open(hp).read().strip() if os.path.exists(hp) else None
        r.level = "level = high" in open(os.path.join(work, "config.ini")).read()
        r.tools = [t for t, ok in r.o["tools"] if ok]
        r.four = r.o["done"] and r.tools == ["read", "write", "edit", "bash"] and r.hello == "pinecone" and r.level
        return r


def pi_detail(r):
    return "%s in %ss (exit %s), stopReason %s, tools %s, hello.txt %r, level high %s, %d turns; final %r" % (
        "DONE" if r.o["done"] else "NOT DONE", r.sec, r.rc, r.o["stop_reason"], r.o["tools"], r.hello, r.level,
        r.o["turns"], (r.o["final"] or r.o.get("error") or "")[:120])


# ---------------------------------------------------------------- the checks

def probe_net(name, kernels, pa, hip, extra=None, flags=()):
    """probe.py check in the stack: interfaces, A, LiteLLM 4000 every way we can think of, the brain, the escape."""
    unit = "mini-llm-%s-%d.service" % (name.replace("_", "-"), os.getpid())
    tcp = [["127.0.0.1", LITELLM], [HOST, LITELLM], [HOST, pa]] + ([[hip, LITELLM]] if hip else [])
    spec = {"tcp": tcp, "escape": [unit, os.path.join(BASE, name + ".escape")], "llm": {"posts": 1}}
    spec.update(extra or {})
    r = mini(name.replace("_", "-"), kernels, escape_env() + S.check_argv(spec), cwd="/", timeout=90, flags=flags)
    S.escape_stop(unit)
    j = r.j
    j["_blocked"] = bool(j) and not str(j.get("escape_busctl", "rc 0")).startswith("rc 0") and \
        not str(j.get("escape_systemd_run", "rc 0")).startswith("rc 0")
    j["_litellm"] = {"%s:%s" % (h, p): j.get("tcp %s:%s" % (h, p)) for h, p in tcp if p == LITELLM}
    j["_a"] = j.get("tcp %s:%s" % (HOST, pa))
    return r, j


def litellm_closed(j):
    return all(v != "ok" for v in j["_litellm"].values())


def short(d):
    return "; ".join("%s %s" % (k, str(v)[:45]) for k, v in d.items())


def check_nonet(pi, pa, hip):
    log("\n== e. aos/base-low,aos/llm/fake: no net kernel (pi has only lo), the brain through the socket")
    r, j = probe_net("e_nonet_probe", ["aos/base-low", "aos/llm/fake"], pa, hip)
    auto = "added aos/mask/run-user" in r.err
    record("e_nonet_probe", bool(j) and j["ifaces"] == ["lo"] and j.get("llm_codes") == [200] and litellm_closed(j)
           and j["_a"] != "ok" and j["_blocked"] and auto,
           "ifaces %s; brain over the socket %s; LiteLLM: %s; test server A %s; escape %s (mask added: %s)" % (
               j.get("ifaces"), j.get("llm_codes"), short(j["_litellm"]), str(j["_a"])[:40],
               "blocked" if j["_blocked"] else "OPEN", auto))
    if not pi.ok:
        record("e_pi_nonet", True, "no node/pi here; skipped", must=False)
        return
    r = pi.run("e_pi_nonet", ["aos/base-low", "aos/llm/fake"])
    n = answered(r.err)
    record("e_pi_nonet", r.four and n == r.o["turns"],
           "[aos/base-low aos/llm/fake] %s; the kernel answered %d (%s)" % (pi_detail(r), n, summary_line(r.err)[12:]))
    if not r.four:
        log(r.err[-1200:])


def check_net(pi, pa, hip):
    log("\n== e. aos/base-low, llm, then a net kernel that lets only test server A through (llm outside the net kernel)")
    test_kernel("llm-net", "aos/llm/fake", state=state_of("llm-net"))
    test_kernel("llm-net-probe", "aos/llm/fake", state=state_of("llm-net-probe"))
    ks = ["aos/base-low", "t/llm-net-probe", "t/net-a"]
    r, j = probe_net("e_net_probe", ks, pa, hip)
    record("e_net_probe", bool(j) and "eth0" in j["ifaces"] and j["_a"] == "ok" and litellm_closed(j) and
           j.get("llm_codes") == [200] and j["_blocked"] and len(ledger("llm-net-probe")) == 1,
           "[%s] ifaces %s; A %s; LiteLLM: %s; brain %s, ledger %d line(s); escape %s" % (
               " ".join(ks), j.get("ifaces"), j["_a"], short(j["_litellm"]), j.get("llm_codes"),
               len(ledger("llm-net-probe")), "blocked" if j["_blocked"] else "OPEN"))
    if not pi.ok:
        return
    ks = ["aos/base-low", "t/llm-net", "t/net-a"]
    r = pi.run("e_pi_net", ks)
    lines = ledger("llm-net")
    record("e_pi_net", r.four and len(lines) == r.o["turns"] == answered(r.err),
           "[%s] %s; ledger %d lines (%s)" % (" ".join(ks), pi_detail(r), len(lines),
                                              ",".join(sorted({l["result"] for l in lines}))))
    if not r.four:
        log(r.err[-1200:])


def check_budget(pi):
    log("\n== e. budget: a limit of 2 (three requests), and a used-up budget under pi")
    test_kernel("llm-two", "aos/llm/fake", limit=2, state=state_of("llm-two"))
    r = mini("e-budget", ["t/llm-two"], S.check_argv({"llm": {"posts": 3, "bad_model": "gpt-other",
                                                              "state": state_of("llm-two")}}), cwd="/")
    j, lines, b = r.j, ledger("llm-two"), budget("llm-two")
    why = [l.get("why") or l["result"] for l in lines]
    record("e_budget_429", j.get("llm_codes") == [200, 200, 429] and j.get("llm_bad_model") == 403 and
           b == {"used": 2, "limit": 2} and why == ["fake", "fake", "budget", "model"],
           "codes %s, other model %s; ledger %s; budget outside %s; the state folder inside: list %s, write %s "
           "(outside unchanged)" % (j.get("llm_codes"), j.get("llm_bad_model"), why, b, j.get("llm_state_list"),
                                    j.get("llm_state_write")))
    if not pi.ok:
        return
    test_kernel("llm-used", "aos/llm/fake", limit=3, state=state_of("llm-used"))
    write_json(os.path.join(state_of("llm-used"), "budget.json"), {"used": 3, "limit": 3})
    r = pi.run("e_pi_used_up", ["aos/base-low", "t/llm-used"], timeout=120)
    lines = ledger("llm-used")
    refused = [l for l in lines if l.get("why") == "budget"]
    record("e_pi_used_up", not r.o["done"] and not r.tools and lines and len(refused) == len(lines),
           "pi %s (exit %s), error %r; ledger %d lines, all refused for the budget: %s" % (
               "DONE" if r.o["done"] else "NOT DONE", r.rc, (r.o.get("error") or "")[:80], len(lines),
               len(refused) == len(lines)))


def check_inside_net(pa):
    log("\n== e. llm inside a net kernel: the layers inside lose the network, the brain stays")
    test_kernel("llm-in", "aos/llm/fake")
    ks = ["t/net-a", "t/llm-in"]
    r = mini("e-inside-net", ks, ["sh", "-c", 'ls "$AOS_ENV/.aos/interfaces/aos" | tr "\\n" " "; echo; exec "$@"',
                                  "sh"] + S.check_argv({"tcp": [[HOST, pa]], "llm": {"posts": 1}}), cwd="/")
    j = r.j
    kinds = (r.out.strip().splitlines() or [""])[0].split()
    a = j.get("tcp %s:%s" % (HOST, pa))
    record("e_llm_inside_net", j.get("ifaces") == ["lo"] and a != "ok" and j.get("llm_codes") == [200] and
           j.get("llm_network") == "cut" and "net" not in kinds,
           "[%s] ifaces %s; A %s; brain %s; declared kinds inside %s; llm network %s" % (
               " ".join(ks), j.get("ifaces"), str(a)[:40], j.get("llm_codes"), kinds, j.get("llm_network")))


def check_llm_on_llm():
    log("\n== e. llm on llm: the outer one (3 requests) refuses first, the agent cannot go around the inner one")
    test_kernel("llm-outer", "aos/llm/fake", limit=3, state=state_of("llm-outer"))
    k = demo("aos/llm/fake")
    k["config"] = {"models": ["fake-model"], "limit": 10, "state": state_of("llm-inner")}  # upstream: the outer one
    write_json(os.path.join(BASE, "kernels", "t", "llm-inner.json"), k)
    r = mini("e-llm-on-llm", ["t/llm-outer", "t/llm-inner"], S.check_argv({"llm": {"posts": 4}}), cwd="/")
    j = r.j
    outer, inner = ledger("llm-outer"), ledger("llm-inner")
    warned = "mini: 1 setting(s) written looser" in r.err  # its limit 10 above the outer 3: one summary line
    others = j.get("llm_other_socks", {})
    record("e_llm_on_llm", j.get("llm_codes") == [200, 200, 200, 429] and len(inner) == 4 and
           [l["result"] for l in outer] == ["fake"] * 3 + ["refused"] and warned and len(others) == 1 and
           all(v != 200 for v in others.values()),
           "codes %s; inner ledger %d (statuses %s), outer %s; inner warned it is looser: %s; the outer socket "
           "straight from inside: %s" % (j.get("llm_codes"), len(inner), [l.get("status") for l in inner],
                                         [l["result"] for l in outer], warned,
                                         {os.path.basename(os.path.dirname(p)): v for p, v in others.items()}))


def check_auto_mask():
    log("\n== e. auto mask with only an llm kernel; --no-auto-mask leaves the way out open")
    for name, flags in (("e_auto_mask_llm_only", ()), ("e_no_auto_mask_llm_only", ("--no-auto-mask",))):
        unit = "mini-llm-%s-%d.service" % (name.replace("_", "-"), os.getpid())
        r = mini(name.replace("_", "-"), ["aos/llm/fake"], escape_env() + S.check_argv(
            {"escape": [unit, os.path.join(BASE, name + ".escape")]}), cwd="/", flags=flags)
        S.escape_stop(unit)
        j = r.j
        blocked = bool(j) and not str(j.get("escape_busctl", "rc 0")).startswith("rc 0") and \
            not str(j.get("escape_systemd_run", "rc 0")).startswith("rc 0")
        want = not flags
        record(name, bool(j) and blocked == want and ("added aos/mask/run-user" in r.err) == want,
               "escape %s (busctl %s); mask added: %s" % ("blocked" if blocked else "OPEN",
                                                           str(j.get("escape_busctl"))[:50],
                                                           "added aos/mask/run-user" in r.err))


def check_order(pa):
    log("\n== e. a net kernel inside an llm kernel that lets the llm's upstream through: refused before anything runs")
    test_kernel("llm-up-a", "aos/llm/fake", upstream="http://127.0.0.1:%d/v1" % pa)  # A stands in for LiteLLM
    for name, flags in (("e_order_refused", ()), ("e_order_refused_dry", ("--dry-run",))):
        mark = os.path.join(BASE, name + ".ran")
        before = S.snapshot((pa,))
        r = mini(name.replace("_", "-"), ["t/llm-up-a", "t/net-a"], ["sh", "-c", "touch " + mark], cwd="/",
                 timeout=30, flags=flags)
        after = S.snapshot((pa,))
        new = {k: (sorted(set(after[k]) - set(before[k])) if k != "procs" else
                   [p for p in after[k] if p not in before[k]]) for k in after}
        said = "KernelOrderBad" in r.err and "t/net-a" in r.err and "t/llm-up-a" in r.err
        record(name, r.rc not in (0, None) and said and not os.path.exists(mark) and not r.out.strip() and
               not any(new.values()),
               "[t/llm-up-a,t/net-a%s] exit %s; the command ran: %s; new: %s; %s" % (
                   " " + " ".join(flags) if flags else "", r.rc, os.path.exists(mark),
                   {k: v for k, v in new.items() if v} or "nothing", r.err.strip().splitlines()[-1][:200]))
    mark = os.path.join(BASE, "e_order_net_first.ran")
    r = mini("e-order-net-first", ["t/net-a", "t/llm-up-a"], ["sh", "-c", "touch " + mark], cwd="/", timeout=60)
    record("e_order_net_first", r.rc == 0 and os.path.exists(mark) and "KernelOrderBad" not in r.err,
           "[t/net-a,t/llm-up-a] exit %s; the command ran: %s" % (r.rc, os.path.exists(mark)))


def check_state():
    log("\n== e. state: the budget carries over from one run to the next only when the config names a state folder")
    test_kernel("llm-keep", "aos/llm/fake", limit=3, state=state_of("llm-keep"))
    test_kernel("llm-fresh", "aos/llm/fake", limit=3)
    codes = {}
    for t in ("llm-keep", "llm-fresh"):
        codes[t] = [mini("e-state-%d" % n, ["t/" + t], S.check_argv({"llm": {"posts": 2}}), cwd="/").j.get("llm_codes")
                    for n in (1, 2)]
    record("e_state_carries", codes["llm-keep"] == [[200, 200], [200, 429]] and
           codes["llm-fresh"] == [[200, 200], [200, 200]] and budget("llm-keep") == {"used": 3, "limit": 3},
           "limit 3, two runs of 2 requests: with state %s (budget file %s), without %s" % (
               codes["llm-keep"], budget("llm-keep"), codes["llm-fresh"]))


def check_real(pi, model):
    log("\n== e. the real model %s through LiteLLM 127.0.0.1:%d, at most 10 requests" % (model, LITELLM))
    if socket.socket().connect_ex(("127.0.0.1", LITELLM)) != 0:
        record("e_pi_real", True, "LiteLLM is not listening on 127.0.0.1:%d; skipped" % LITELLM, must=False)
        return
    test_kernel("llm-real", "aos/llm/litellm-luna", models=[model], limit=10, state=state_of("llm-real"))
    r = pi.run("e_pi_real", ["aos/base-low", "t/llm-real"], model=model, timeout=300)
    lines = ledger("llm-real")
    tokens = sum((l.get("usage") or {}).get("total_tokens", 0) for l in lines)
    record("e_pi_real", r.four and len(lines) == r.o["turns"] and all(l.get("status") == 200 for l in lines),
           "[aos/base-low t/llm-real(%s, limit 10)] %s; ledger %d lines, statuses %s, about %d tokens" % (
               model, pi_detail(r), len(lines), [l.get("status") for l in lines], tokens))


def main():
    ap = argparse.ArgumentParser(description="Acceptance run for mini's nested llm kernel (PASS/FAIL/info lines).")
    ap.add_argument("--pasta", help="pasta binary (default: on PATH, else %s)" % A.DEFAULT_PASTA)
    ap.add_argument("--keep", action="store_true", help="keep %s afterwards" % BASE)
    ap.add_argument("--no-pi", action="store_true", help="skip the pi runs")
    ap.add_argument("--model", help="also one real run with this model through LiteLLM (at most 10 requests)")
    a = ap.parse_args()
    if a.model and a.model.startswith("claude"):
        sys.exit("llm_test: error: ArgumentsBad not a claude-* model here")
    pasta = a.pasta or shutil.which("pasta") or A.DEFAULT_PASTA
    if not os.access(pasta, os.X_OK):
        sys.exit("llm_test: error: PastaMissing no pasta at %s (install passt, or --pasta PATH)" % pasta)
    shutil.rmtree(BASE, ignore_errors=True)
    os.makedirs(BASE)
    S.BASE = BASE  # stack_test's snapshot marks
    os.environ.update(MINI_PASTA=pasta, AOS_HOME=AOS_HOME, MINI_KERNELS_PATH=os.path.join(BASE, "kernels"))
    srv = A.start_server()
    pa = srv.server_address[1]
    before = S.snapshot((pa,))
    hip = host_ip()
    write_json(os.path.join(BASE, "kernels", "t", "net-a.json"), {
        "description": "test net kernel: only test server A on the host", "program": "net_kernel.py",
        "config": {"host_ports": [pa]}})
    log("test server A on the host: 127.0.0.1:%d (inside %s:%d); LiteLLM 127.0.0.1:%d %s; this machine's address %s" % (
        pa, HOST, pa, LITELLM, "listening" if socket.socket().connect_ex(("127.0.0.1", LITELLM)) == 0 else
        "not listening", hip))
    pi = Pi()
    if a.no_pi:
        pi.ok = False
    t0 = time.monotonic()
    try:
        check_nonet(pi, pa, hip)
        check_net(pi, pa, hip)
        check_budget(pi)
        check_inside_net(pa)
        check_llm_on_llm()
        check_auto_mask()
        check_order(pa)
        check_state()
        if a.model and pi.ok:
            check_real(pi, a.model)
    finally:
        srv.shutdown()
        srv.server_close()
    time.sleep(1)
    after = S.snapshot((pa,))
    left = {k: (sorted(set(after[k]) - set(before[k])) if k != "procs" else
                {p: c for p, c in after[k].items() if p not in before[k]}) for k in after}
    still = socket.socket().connect_ex(("127.0.0.1", pa)) == 0
    record("cleanup", not any(left.values()) and not still, "left over: %s; test server still open: %s" % (
        {k: v for k, v in left.items() if v} or "nothing", still))
    fails = [n for n, t in RESULTS if t == "FAIL"]
    log("\nSUMMARY %s (%d PASS, %d FAIL, %d info, %.0fs)%s" % (
        "ok" if not fails else "FAILED", sum(t == "PASS" for _, t in RESULTS), len(fails),
        sum(t == "info" for _, t in RESULTS), time.monotonic() - t0, ": " + ", ".join(fails) if fails else ""))
    if not a.keep and not fails:
        shutil.rmtree(BASE, ignore_errors=True)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
