#!/usr/bin/env python3
"""Acceptance run for aos-pi: one llm kernel and a stack of two, each with the probe in pi's sky (what must be blocked), pi doing the four-tool task, the ledgers checked against pi's own count, the top kernel used up while the one below gets nothing, and nothing left over afterwards."""

import argparse
import ctypes
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import types

sys.dont_write_bytecode = True  # keep the repo free of __pycache__
import aos_pi
from daemon_ctl import DAEMON_BIN, read, write

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
BASE = os.path.expanduser("~/.aos/scratch/proto9-impl-1127/pi/accept")
OUR_CMDS = ("/k/llm_kernel.py", "/llm/relay", "/opt/pi/", "probe.sh")

PROJECT = {
    "NOTES.md": "# Notes\n\nThe secret word is: pinecone\n",
    "config.ini": "[app]\nname = demo\nlevel = low\ncolor = blue\n",
    "test_app.py": (
        "import configparser, pathlib\n"
        "c = configparser.ConfigParser()\n"
        "c.read('config.ini')\n"
        "assert c['app']['level'] == 'high', 'config.ini: level is %s, want high' % c['app']['level']\n"
        "assert c['app']['color'] == 'blue', 'config.ini: color changed'\n"
        "h = pathlib.Path('hello.txt')\n"
        "assert h.exists(), 'hello.txt is missing'\n"
        "assert h.read_text().strip() == 'pinecone', 'hello.txt has %r' % h.read_text()\n"
        "print('ALL TESTS PASSED')\n"),
}
TASK = ("You are working in ~/work (the current directory). Do these four steps with your tools, one tool per step: "
        "1) Use the read tool to read NOTES.md. "
        "2) Use the write tool to create a new file hello.txt whose whole content is the secret word from NOTES.md. "
        "3) Use the edit tool to change the line `level = low` in config.ini to `level = high` (change nothing else). "
        "4) Use the bash tool to run `python3 test_app.py` and report its output. "
        "Keep your final answer to one or two lines.")
FAKE_SCRIPT = [{"when": "four steps", "steps": [
    {"tool": "read", "args": {"path": "NOTES.md"}},
    {"tool": "write", "args": {"path": "hello.txt", "content": "pinecone\n"}},
    {"tool": "edit", "args": {"path": "config.ini", "edits": [{"oldText": "level = low", "newText": "level = high"}]}},
    {"tool": "bash", "args": {"command": "python3 test_app.py"}},
    {"text": "FAKE: ran the four steps"}]}]

# what the brief requires blocked (or working); the other probe lines are shown but do not fail the run
MUST = re.compile(r"^(write_work|write_root|write_ro:.*|write_outside|git_.*|symlink_.*|read:.*|read_etc_shadow|"
                  r"proc_absent|net_.*|llm_.*|unix_.*|ipc_.*|kill_host_pid)$")


def log(*a):
    print(*a, flush=True)


# ---------------------------------------------------------------- things outside the sandbox to reach for

class Outside:
    """A unix socket (by path and abstract), a SysV segment and a POSIX queue on the host, for the probe to try."""

    def __init__(self, d):
        self.d, self.socks = d, []
        os.makedirs(os.path.join(d, "outside"))
        self.sock_path = os.path.join(d, "outside.sock")
        self.abstract = "aos-pi-accept-%d-%s" % (os.getpid(), os.path.basename(d))
        for addr in (self.sock_path, "\0" + self.abstract):
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.bind(addr)
            s.listen(4)
            self.socks.append(s)
            threading.Thread(target=self.accept_loop, args=(s,), daemon=True).start()
        self.vsock_port = None
        try:  # vsock knows no network namespace: a listener here may be reachable from a net-none sky
            s = socket.socket(socket.AF_VSOCK, socket.SOCK_STREAM)
            s.bind((socket.VMADDR_CID_ANY, socket.VMADDR_PORT_ANY))
            s.listen(4)
            self.vsock_port = s.getsockname()[1]
            self.socks.append(s)
            threading.Thread(target=self.accept_loop, args=(s,), daemon=True).start()
        except OSError:
            pass
        self.shm_id = re.search(r"\d+", subprocess.run(["ipcmk", "-M", "4096"], capture_output=True, text=True,
                                                        check=True).stdout).group(0)
        self.rt = ctypes.CDLL("librt.so.1", use_errno=True)
        self.mq = "/aos-pi-accept-%d" % os.getpid()
        fd = self.rt.mq_open(self.mq.encode(), os.O_CREAT | os.O_RDWR, 0o600, None)
        if fd < 0:
            raise OSError(ctypes.get_errno(), "mq_open " + self.mq)
        os.close(fd)

    @staticmethod
    def accept_loop(s):
        while True:
            try:
                c, _ = s.accept()
                c.close()
            except OSError:
                return

    def close(self):
        for s in self.socks:  # shutdown wakes the accept thread, so the address is free at once
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            s.close()
        subprocess.run(["ipcrm", "-m", self.shm_id], capture_output=True)
        self.rt.mq_unlink(self.mq.encode())


# ---------------------------------------------------------------- what is left over (before / after)

def snapshot():
    ids = set()
    for p in (DAEMON_BIN, aos_pi.find_node()[0], "/usr/bin/python3", "/usr/bin/bash"):
        st = os.stat(os.path.realpath(p))
        ids.add((st.st_dev, st.st_ino))
    st = os.stat(DAEMON_BIN)
    daemon_id = (st.st_dev, st.st_ino)
    procs = set()
    for d in filter(str.isdigit, os.listdir("/proc")):
        try:
            st = os.stat("/proc/%s/exe" % d)
        except OSError:
            continue
        cmd = read("/proc/%s/cmdline" % d).replace("\0", " ")
        if (st.st_dev, st.st_ino) == daemon_id or ((st.st_dev, st.st_ino) in ids and any(x in cmd for x in OUR_CMDS)):
            procs.add("%s %s" % (d, cmd[:100]))
    ipcs = subprocess.run(["ipcs"], capture_output=True, text=True).stdout
    return {"processes (this aos-daemon binary; our kernels, relays, pi, probe)": procs,
            # only mount points we could have made: other aos-daemon tests mount and unmount next to us
            "mounts under the run dirs": {l.split(" - ")[0].split(" ", 5)[4] for l in read("/proc/self/mountinfo")
                                          .splitlines() if l.split(" ")[4].startswith(BASE)},
            "SysV IPC (key id)": {" ".join(l.split()[:2]) for l in ipcs.splitlines() if re.match(r"0x[0-9a-f]+\s", l)},
            "/dev/mqueue": set(os.listdir("/dev/mqueue")) if os.path.isdir("/dev/mqueue") else set()}


def leftovers(before, after, cgroups):
    # only what is new counts: things that went away meanwhile are other people's
    bad = ["%s: new %s" % (k, sorted(after[k] - before[k])[:4]) for k in before if after[k] - before[k]]
    units = subprocess.run(["systemctl", "--user", "list-units", "aos-daemon-*", "--all", "--no-legend", "--plain"],
                           capture_output=True, text=True).stdout
    for cg in cgroups:  # our daemons' scopes only: another aos-daemon may be running next to us
        if cg and os.path.exists(cg):
            bad.append("cgroup still there: " + cg)
        if cg and os.path.basename(cg) in units:
            bad.append("systemd unit still there: " + os.path.basename(cg))
    return bad


# ---------------------------------------------------------------- one mode: a stack of N kernels

def make_work(d):
    for name, text in PROJECT.items():
        write(os.path.join(d, name), text)
    git = ["git", "-C", d, "-c", "user.name=accept", "-c", "user.email=accept@localhost"]
    subprocess.run(git[:3] + ["init", "-q"], check=True)
    subprocess.run(git + ["add", "."], check=True)
    subprocess.run(git + ["commit", "-qm", "start"], check=True)


def run_probe(sb, out, work):
    probe_dir = os.path.join(sb.run, "probe")
    os.makedirs(probe_dir)
    shutil.copy(os.path.join(HERE, "probe.sh"), probe_dir)
    sib = re.search(r"ns: (\d+)", sb.d.fact(sb.kernels[-1]["name"], "pid"))
    env = {"PROBE_WORK": "/home/pi/work", "PROBE_GIT": "/home/pi/work/.git", "PROBE_RO": "/:/.aos:/llm:/usr:/etc",
           "PROBE_OUTSIDE": os.path.join(out.d, "outside"),
           "PROBE_SECRETS": ":".join([os.path.expanduser("~/.ssh"), os.path.join(REPO, "AGENTS.md"),
                                      os.path.expanduser("~/.pi/agent/auth.json"), os.path.abspath(work)]),
           "PROBE_LLM_SOCK": "/llm/sock", "PROBE_LLM_BAD_MODEL": "not-" + sb.a.model,
           "PROBE_LITELLM": "http://127.0.0.1:4000/v1/models", "PROBE_UNIX_SOCK": out.sock_path,
           "PROBE_ABSTRACT": out.abstract, "PROBE_VSOCK_PORT": str(out.vsock_port or ""), "PROBE_SHM_ID": out.shm_id, "PROBE_MQ": out.mq,
           "PROBE_HOST_PID": str(os.getpid()), "PROBE_PTRACE_PID": sib.group(1) if sib else ""}
    r = sb.run_in_sky("probe", ["/bin/bash", "/opt/probe/probe.sh"], 180, env=env,
                      extra=[{"type": "bind", "src": probe_dir, "dst": "/opt/probe"}])
    rows = [l.split("\t", 3) for l in read(sb.p("logs", "probe.out")).splitlines() if l.count("\t") == 3]
    return r, rows


def check_outside_untouched(out):
    left = os.listdir(os.path.join(out.d, "outside"))
    return ["outside dir got %s" % left] if left else []


def run_mode(a, stack, base):
    """Returns the list of failures of this mode."""
    fails = []
    d = os.path.join(base, "stack%d" % stack)
    work = os.path.join(d, "work")
    make_work(work)
    script = os.path.join(d, "fake_script.json")
    write(script, json.dumps(FAKE_SCRIPT, indent=1) + "\n")
    ns = types.SimpleNamespace(work=work, model=a.model, limit=a.limit, stack=stack, lower_limit=2 * a.limit,
                               upstream=a.upstream, name="accept", sandbox_root=d, cont=False, git_rw=False,
                               timeout=a.timeout, fake=a.fake, fake_script=script if a.fake else None,
                               daemon=DAEMON_BIN, node=None, pi=None)
    sb, out, cgroup = aos_pi.Sandbox(ns), None, None
    try:
        out = Outside(d)
        sb.start()
        cgroup = sb.d.status_field("cgroup")
        decl = os.path.join(sb.kernels[-1]["dir"], ".aos", "interfaces", "aos", "llm")
        log("== stack %d: daemon %s, Landlock ABI %s; /llm declares: %s" % (
            stack, sb.d.pid, sb.d.status_field("landlock_abi"), " ".join(sorted(os.listdir(decl)))))
        # the probe: the same sky as pi, no model
        pr, rows = run_probe(sb, out, work)
        log("PROBE exit %s, ns_check %s (WANT GOT name detail)" % (pr["exit"], pr["ns_check"]))
        for name, want, got, detail in rows:
            must = bool(MUST.match(name))
            bad = got != want and must
            log("  %s %-8s %-8s %-26s %s" % ("FAIL" if bad else ("    " if must else "info"), want, got, name,
                                            detail[:100]))
            if bad:
                fails.append("probe " + name)
        if not rows:
            fails.append("probe printed nothing: " + read(sb.p("logs", "probe.err"))[-300:])
        fails += check_outside_untouched(out)
        # pi does the four-tool task
        m = sb.run_pi(TASK, name="pi-main")
        hello = read(os.path.join(work, "hello.txt")).strip()
        level = re.search(r"^level = (\w+)", read(os.path.join(work, "config.ini")), re.M)
        used = [t for t, ok in m["tools"] if ok]
        test_out = read(sb.p("logs", "pi-main.out"))
        checks = {"read": "read" in used, "write": "write" in used and hello == "pinecone",
                  "edit": "edit" in used and bool(level) and level.group(1) == "high",
                  "bash": "bash" in used and "ALL TESTS PASSED" in test_out, "done (stopReason stop)": m["done"]}
        log("PI MAIN: %s, stopReason %s, %d LLM turns, %ss; tools %s" % (
            "DONE" if m["done"] else "NOT DONE", m["stop_reason"], m["turns"], m["seconds"], m["tools"]))
        log("  final: %s" % m["final"][:200])
        for k, ok in checks.items():
            log("  %-24s %s" % (k, "PASS" if ok else "FAIL"))
            if not ok:
                fails.append("pi " + k)
        fails += ledger_checks(sb, m, "main", a.fake)
        # use up the top kernel: pi is refused, the kernels below get nothing
        top = sb.kernels[-1]
        write(os.path.join(top["state"], "budget.json"), json.dumps({"used": top["limit"], "limit": top["limit"]}) + "\n")
        x = sb.run_pi("Say hello in one word.", name="pi-exhausted")
        log("PI EXHAUSTED: %s, stopReason %s, %d LLM turns, error %s" % (
            "DONE" if x["done"] else "NOT DONE", x["stop_reason"], x["turns"], (x["error"] or "")[:90]))
        fails += ledger_checks(sb, x, "exhausted", a.fake)
        if x["done"]:
            fails.append("exhausted: pi says done")
        if any(l["result"] != "refused" for l in x["ledgers"][-1]):
            fails.append("exhausted: the top kernel let something through")
        for k, lines in zip(sb.kernels[:-1], x["ledgers"][:-1]):
            log("  %s (below) got %d request(s) while the top was used up" % (k["name"], len(lines)))
            if lines:
                fails.append("exhausted: %s got %d" % (k["name"], len(lines)))
        log("pi locks: " + m["locks"].strip().replace("\n", " | "))
        log("daemon warnings: %s" % (sb.d.warnings() or "none"))
    except Exception as e:  # report and go on to the cleanup check
        fails.append("error: %s" % e)
        log("ERROR %s" % e)
    finally:
        sb.stop()
        if out:
            out.close()
    return fails, cgroup


def ledger_checks(sb, r, what, fake):
    """pi's assistant messages = the top kernel's ledger lines; each request the top sent = one line below."""
    fails = []
    lines = r["ledgers"]
    top = lines[-1]
    ok = r["turns"] == len(top)
    log("  count %s: pi assistant messages %d, %s ledger %d -> %s" % (
        what, r["turns"], sb.kernels[-1]["name"], len(top), "MATCH" if ok else "MISMATCH"))
    if not ok:
        fails.append("count %s top" % what)
    for i in range(len(lines) - 1, 0, -1):
        passed = sum(1 for l in lines[i] if l["result"] in ("sent", "fake"))
        below = len(lines[i - 1])
        ok = passed == below
        log("  count %s: %s sent %d, %s ledger %d -> %s" % (what, sb.kernels[i]["name"], passed,
                                                            sb.kernels[i - 1]["name"], below, "MATCH" if ok else "MISMATCH"))
        if not ok:
            fails.append("count %s %s" % (what, sb.kernels[i - 1]["name"]))
    return fails


def main():
    ap = argparse.ArgumentParser(description="aos-pi acceptance: probe, the four tools, ledgers, budget, leftovers")
    ap.add_argument("--fake", action="store_true", help="the bottom kernel answers from a script; no model is called")
    ap.add_argument("--model", default="fake-model", help="model id (a real one without --fake)")
    ap.add_argument("--limit", type=int, default=20, help="the top kernel's cap (default 20)")
    ap.add_argument("--stacks", default="1,2", help="which stack heights to run (default 1,2)")
    ap.add_argument("--upstream", default="http://127.0.0.1:4000/v1")
    ap.add_argument("--timeout", type=float, default=300)
    ap.add_argument("--keep", action="store_true", help="keep the run dirs")
    a = ap.parse_args()
    if not os.path.exists(DAEMON_BIN):
        subprocess.run(["make", "-C", os.path.dirname(os.path.dirname(os.path.dirname(DAEMON_BIN)))], check=True)
    os.makedirs(BASE, exist_ok=True)
    before = snapshot()
    base = tempfile.mkdtemp(prefix="run-", dir=BASE)
    log("run dir %s; %s; model %s; limit %d" % (base, "FAKE" if a.fake else "REAL upstream " + a.upstream, a.model, a.limit))
    fails, cgroups = [], []
    for s in [int(x) for x in a.stacks.split(",")]:
        f, cg = run_mode(a, s, base)
        fails += ["stack%d: %s" % (s, x) for x in f]
        cgroups.append(cg)
    if a.keep:
        log("kept %s" % base)
    else:
        shutil.rmtree(base, ignore_errors=True)
    time.sleep(0.5)
    bad = leftovers(before, snapshot(), cgroups)
    log("cleanup: %s" % ("ok" if not bad else "LEFTOVERS " + "; ".join(bad)))
    fails += ["cleanup: " + b for b in bad]
    log("SUMMARY %s" % ("ok" if not fails else "FAILED %d: %s" % (len(fails), ", ".join(fails))))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
