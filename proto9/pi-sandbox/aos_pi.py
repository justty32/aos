#!/usr/bin/env python3
"""aos-pi: runs the pi coding agent on a work dir inside a proto9 aos-daemon proc (no init), its brain only through /llm served by one llm kernel or a stack of them; gives it one task, prints the result, pi's locks and the daemon's warnings, then shuts everything down."""

import argparse
import json
import os
import shutil
import sys
import time

sys.dont_write_bytecode = True  # keep the repo free of __pycache__
from daemon_ctl import DAEMON_BIN, Daemon, DaemonError, read, write

PROG = "aos-pi"
HERE = os.path.dirname(os.path.abspath(__file__))
FNM_NODE = os.path.expanduser("~/.local/share/fnm/node-versions/v24.14.1/installation/bin/node")
PI_PKG_REL = os.path.join("lib", "node_modules", "@earendil-works", "pi-coding-agent")
PORT = 8787
PI_ARGS = ["--mode", "json", "--thinking", "off"]
SKY_DESCRIPTION = ("/ belongs to aos-pi, the side that runs you (read-only). Only your home /home/pi (your work "
                   "dir is ~/work, its .git is read-only) and /tmp are writable. There is no network: the model "
                   "is reached only through /llm (see /llm/.aos/interfaces/aos/llm).")


def fail(code, msg, exit_code=1):
    sys.stdout.flush()
    print("%s: error: %s %s" % (PROG, code, msg), file=sys.stderr, flush=True)
    sys.exit(exit_code)


def warn(msg):
    print("%s: warning: %s" % (PROG, msg), file=sys.stderr, flush=True)


def find_node():
    """node and the pi package next to it (fnm's node by default)."""
    node = FNM_NODE if os.path.exists(FNM_NODE) else os.path.realpath(shutil.which("node") or FNM_NODE)
    return node, os.path.join(os.path.dirname(os.path.dirname(node)), PI_PKG_REL)


def base_sky():
    """What any proc here needs to run a dynamically linked program from /usr: /usr, /bin /lib /lib64 as on the
    host (symlinks stay symlinks), /dev, a 256m /tmp."""
    sky = [{"type": "bind", "src": "/usr", "dst": "/usr"}]
    for d in ("/bin", "/lib", "/lib64"):
        if os.path.islink(d):
            sky.append({"type": "symlink", "target": os.readlink(d), "dst": d})
        elif os.path.isdir(d):
            sky.append({"type": "bind", "src": d, "dst": d})
    return sky + [{"type": "dev", "dst": "/dev"}, {"type": "tmpfs", "dst": "/tmp", "size": "256m"}]


def pi_sky(sky_files, home, work, llm_dir, node, pi_pkg, git_ro=True, extra=()):
    """The standard layout pi lives in: / read-only (it belongs to the side that runs pi), /.aos its declaration,
    /etc/passwd one line, node and pi under /opt, /llm the brain, /home/pi writable, ~/work the real work dir,
    ~/work/.git read-only on top. No /proc, no network (net none is in the proc config)."""
    sky = base_sky() + [
        {"type": "bind", "src": os.path.join(sky_files, ".aos"), "dst": "/.aos"},
        {"type": "bind", "src": os.path.join(sky_files, "passwd"), "dst": "/etc/passwd"},
        {"type": "bind", "src": node, "dst": "/opt/node/bin/node"},
        {"type": "bind", "src": pi_pkg, "dst": "/opt/pi"},
        {"type": "bind", "src": llm_dir, "dst": "/llm"},
        {"type": "bind", "src": home, "dst": "/home/pi", "rw": True},
        {"type": "bind", "src": work, "dst": "/home/pi/work", "rw": True},
    ]
    if git_ro and os.path.lexists(os.path.join(work, ".git")):
        sky.append({"type": "bind", "src": os.path.join(work, ".git"), "dst": "/home/pi/work/.git"})
    return sky + list(extra)


def write_sky_files(sky_files):
    write(os.path.join(sky_files, ".aos", "interfaces", "aos", "description"), SKY_DESCRIPTION + "\n")
    write(os.path.join(sky_files, "passwd"), "pi:x:0:0:pi:/home/pi:/bin/bash\n")


PI_ENV = {"PATH": "/opt/node/bin:/usr/bin:/bin", "HOME": "/home/pi", "USER": "pi", "LOGNAME": "pi",
          "LANG": "C.UTF-8", "PI_OFFLINE": "1", "PI_SKIP_VERSION_CHECK": "1", "PI_TELEMETRY": "0"}
PI_LOCKS = {"cgroup": {"memory.max": "2G", "pids.max": "512"}}


def write_pi_config(home, model):
    """pi's provider: http to the relay on its own loopback, a fake key; rewritten every run."""
    models = {"providers": {"aosllm": {
        "name": "aos /llm", "baseUrl": "http://127.0.0.1:%d/v1" % PORT, "api": "openai-completions",
        "apiKey": "fake-key-pi-never-sees-a-real-one",
        "compat": {"supportsDeveloperRole": False, "supportsStore": False, "maxTokensField": "max_tokens"},
        "models": [{"id": model, "name": model + " via /llm", "contextWindow": 200000, "maxTokens": 4096,
                    "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0}}]}}}
    write(os.path.join(home, ".pi", "agent", "models.json"), json.dumps(models, indent=2) + "\n")
    write(os.path.join(home, ".pi", "agent", "settings.json"), json.dumps(
        {"defaultProvider": "aosllm", "defaultModel": model, "retry": {"baseDelayMs": 500}}, indent=2) + "\n")


def pi_events(path):
    out = []
    for line in read(path).split("\n"):
        try:
            out.append(json.loads(line))
        except ValueError:
            pass
    return out


def pi_outcome(events):
    """Done or not from pi's json events (not its exit code: pi exits 0 even when every request failed)."""
    msgs = [e["message"] for e in events if e.get("type") == "message_end"
            and e.get("message", {}).get("role") == "assistant"]
    last = msgs[-1] if msgs else {}
    stop = last.get("stopReason")
    settled = any(e.get("type") == "agent_settled" for e in events)
    text = " ".join(c.get("text", "").strip() for c in last.get("content", []) if c.get("type") == "text")
    return {"done": stop == "stop" and settled, "stop_reason": stop, "settled": settled, "turns": len(msgs),
            "error": last.get("errorMessage"), "final": text,
            "tools": [(e.get("toolName"), not e.get("isError")) for e in events
                      if e.get("type") == "tool_execution_end"]}


class Sandbox:
    """One aos-pi run: a daemon, a stack of llm kernels, and procs in pi's sky."""

    def __init__(self, a):
        self.a = a
        self.top = os.path.join(a.sandbox_root, a.name)
        self.home, self.run = os.path.join(self.top, "home"), os.path.join(self.top, "run")
        self.node, self.pi_pkg = (a.node, a.pi) if a.node else find_node()
        self.d = None
        self.kernels = []  # [{"name", "dir", "state", "limit"}], bottom first

    def p(self, *x):
        return os.path.join(self.run, *x)

    def prepare(self):
        for p in (self.node, os.path.join(self.pi_pkg, "dist", "bundle", "cli.js"), self.a.daemon):
            if not os.path.exists(p):
                raise DaemonError("missing %s" % p)
        shutil.rmtree(self.run, ignore_errors=True)  # the last run's logs stay until the next run
        os.makedirs(self.p("logs"))
        os.makedirs(os.path.join(self.home, "work"), exist_ok=True)  # mount point of ~/work
        write_sky_files(self.p("sky"))
        write_pi_config(self.home, self.a.model)
        os.makedirs(self.p("kbin"))
        for f in ("llm_kernel.py", "fake_brain.py", "relay.js"):
            shutil.copy(os.path.join(HERE, f), self.p("kbin", f))
        if self.a.fake_script:
            shutil.copy(self.a.fake_script, self.p("kbin", "fake_script.json"))

    def proc_config(self, name, argv, sky, env, net="none", cwd="/", locks=None):
        c = {"name": name, "argv": argv, "env": env, "cwd": cwd, "ns": sky, "net": net,
             "stdout": self.p("logs", name + ".out"), "stderr": self.p("logs", name + ".err")}
        if locks:
            c["locks"] = locks
        return c

    def start_kernels(self):
        for i in range(self.a.stack):
            name, top = "llm-%d" % i, i == self.a.stack - 1
            kdir, state = self.p(name, "out"), self.p(name, "state")
            os.makedirs(kdir)
            os.makedirs(state)
            limit = self.a.limit if top else self.a.lower_limit
            sky = base_sky() + [{"type": "bind", "src": self.p("kbin"), "dst": "/k"},
                                {"type": "bind", "src": kdir, "dst": "/llm", "rw": True},
                                {"type": "bind", "src": state, "dst": "/state", "rw": True}]
            argv = ["/usr/bin/python3", "/k/llm_kernel.py", "--dir", "/llm", "--model", self.a.model,
                    "--limit", str(limit), "--budget", "/state/budget.json", "--log", "/state/ledger.jsonl"]
            if i == 0:
                argv += ["--upstream", self.a.upstream]
                if self.a.fake:
                    argv += ["--fake"] + (["--fake-script", "/k/fake_script.json"] if self.a.fake_script else [])
            else:  # no network: its only upstream is the dir the kernel below puts out
                sky.append({"type": "bind", "src": self.kernels[-1]["dir"], "dst": "/up"})
                argv += ["--upstream", "/up"]
            c = self.proc_config(name, argv, sky, {"PATH": "/usr/bin:/bin", "HOME": "/tmp"},
                                 net="host" if i == 0 else "none")
            self.d.start_proc(c, self.p(name + ".json"))
            if not wait_until_exists(os.path.join(kdir, "sock"), 10):
                raise DaemonError("%s made no socket: %s" % (name, read(self.p("logs", name + ".err")).strip()[-400:]))
            self.kernels.append({"name": name, "dir": kdir, "state": state, "limit": limit})

    def start(self):
        self.prepare()
        self.d = Daemon(self.run, self.a.daemon)
        self.d.start()
        self.start_kernels()

    def sky(self, extra=()):
        return pi_sky(self.p("sky"), self.home, os.path.abspath(self.a.work), self.kernels[-1]["dir"], self.node,
                      self.pi_pkg, git_ro=not self.a.git_rw, extra=extra)

    def run_in_sky(self, name, argv, timeout, env=None, extra=()):
        """Run one proc in pi's sky until it ends; returns its exit fact."""
        c = self.proc_config(name, argv, self.sky(extra), dict(PI_ENV, **(env or {})), cwd="/home/pi/work",
                             locks=PI_LOCKS)
        self.d.start_proc(c, self.p(name + ".json"))
        self.locks = self.d.fact(name, "locks")
        ended = self.d.wait_dead(name, timeout)
        return {"exit": self.d.fact(name, "exit").strip(), "ended": ended, "locks": self.locks,
                "ns_check": self.d.fact(name, "ns_check").strip()}

    def run_pi(self, task, name="pi", cont=False, timeout=None):
        argv = ["/opt/node/bin/node", "/llm/relay", "--llm", "/llm", "--port", str(PORT), "--",
                "/opt/pi/dist/bundle/cli.js"] + PI_ARGS + ["--provider", "aosllm", "--model", self.a.model]
        argv += (["--continue"] if cont else []) + [task]
        before = [len(ledger(k)) for k in self.kernels]
        t0 = time.monotonic()
        r = self.run_in_sky(name, argv, timeout or self.a.timeout)
        r["seconds"] = round(time.monotonic() - t0, 1)
        r.update(pi_outcome(pi_events(self.p("logs", name + ".out"))))
        r["ledgers"] = [ledger(k)[n:] for k, n in zip(self.kernels, before)]
        r["stderr_tail"] = read(self.p("logs", name + ".err"))[-800:]
        return r

    def stop(self):
        if self.d:
            self.d.stop()


def ledger(k):
    return [json.loads(l) for l in read(os.path.join(k["state"], "ledger.jsonl")).splitlines() if l.strip()]


def wait_until_exists(path, timeout):
    end = time.monotonic() + timeout
    while time.monotonic() < end and not os.path.exists(path):
        time.sleep(0.05)
    return os.path.exists(path)


def report(sb, r):
    print("pi: %s (stopReason %s, %d LLM turns, %ss, proc exit %s)" % (
        "DONE" if r["done"] else "NOT DONE", r["stop_reason"], r["turns"], r["seconds"], r["exit"]))
    print("tools: %s" % ", ".join("%s%s" % (t, "" if ok else "(failed)") for t, ok in r["tools"]))
    if r["error"]:
        print("error: %s" % r["error"])
    print("final: %s" % r["final"])
    for k, lines in zip(sb.kernels, r["ledgers"]):
        res = [x["result"] for x in lines]
        print("%s: %d request(s) this run: %s; %s" % (k["name"], len(lines), ", ".join(
            "%s %d" % (x, res.count(x)) for x in sorted(set(res))) or "-", read(os.path.join(k["dir"], "status"))
            .replace("\n", "; ").strip("; ")))
    print("pi locks:\n  " + r["locks"].strip().replace("\n", "\n  "))
    w = sb.d.warnings()
    print("daemon warnings: %s" % ("none" if not w else "\n  " + "\n  ".join(w)))
    print("logs: %s (kept until the next run); home: %s" % (sb.run, sb.home))


def parser():
    ap = argparse.ArgumentParser(prog=PROG, description="Run the pi coding agent on WORK inside an aos-daemon proc "
                                 "whose only way to the model is /llm; print the result and shut down.")
    ap.error = lambda m: fail("ArgumentsBad", "%s (usage: %s --help)" % (m, PROG), 2)
    ap.add_argument("work", help="the work dir (pi sees it as ~/work, writable; its .git read-only)")
    ap.add_argument("task", help="what pi should do, one sentence")
    ap.add_argument("--model", required=True, help="model id the kernels allow and pi uses")
    ap.add_argument("--limit", type=int, default=20, help="most requests pi gets (the top kernel's cap; default 20)")
    ap.add_argument("--stack", type=int, default=1, help="how many llm kernels on top of each other (default 1); "
                    "only the bottom one has network")
    ap.add_argument("--lower-limit", type=int, help="cap of the kernels below the top (default 2 x --limit)")
    ap.add_argument("--upstream", default="http://127.0.0.1:4000/v1", help="the bottom kernel's upstream (LiteLLM)")
    ap.add_argument("--name", default="pi", help="sandbox name: the home is SANDBOX_ROOT/NAME/home (default pi)")
    ap.add_argument("--sandbox-root", default=os.path.expanduser("~/.aos/sandbox"))
    ap.add_argument("--continue", dest="cont", action="store_true", help="continue pi's last session in this home")
    ap.add_argument("--git-rw", action="store_true", help="leave ~/work/.git writable (default: read-only on top)")
    ap.add_argument("--timeout", type=float, default=600, help="seconds pi may take (default 600)")
    ap.add_argument("--fake", action="store_true", help="the bottom kernel answers from a script; no model is called")
    ap.add_argument("--fake-script", help="json script for --fake (default: answer FAKE OK)")
    ap.add_argument("--daemon", default=DAEMON_BIN, help="the aos-daemon binary")
    ap.add_argument("--node", help="node binary (default: fnm's v24.14.1)")
    ap.add_argument("--pi", help="pi package dir (with --node)")
    return ap


def check_args(a):
    if a.stack < 1 or a.limit < 0:
        fail("ArgumentsBad", "--stack must be >= 1 and --limit >= 0", 2)
    if a.lower_limit is None:
        a.lower_limit = 2 * a.limit
    if not os.path.isdir(a.work):
        fail("WorkDirMissing", "%s is not a directory" % a.work, 2)
    if bool(a.node) != bool(a.pi):
        fail("ArgumentsBad", "--node and --pi go together", 2)


def main():
    if len(sys.argv) == 1:
        fail("ArgumentsBad", "no arguments (usage: %s --help)" % PROG, 2)
    a = parser().parse_args()
    check_args(a)
    sb = Sandbox(a)
    try:
        sb.start()
        r = sb.run_pi(a.task, cont=a.cont)
        report(sb, r)
    except DaemonError as e:
        sb.stop()
        fail("SandboxFailed", str(e))
    sb.stop()
    if not r["done"]:
        fail("NotDone", "pi stopped with stopReason %s%s" % (r["stop_reason"], ": " + r["error"] if r["error"] else ""))


if __name__ == "__main__":
    main()
