#!/usr/bin/env python3
"""Runs the same probe.sh in three sandboxes (aos-pi, Anthropic's sandbox-runtime srt, OpenAI Codex's `codex sandbox`), each set up to mean "only the work dir is writable, no network", and writes the three-column table as markdown."""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import types

sys.dont_write_bytecode = True  # keep the repo free of __pycache__
import accept
import aos_pi
from daemon_ctl import DAEMON_BIN, read, write

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.expanduser("~/.aos/scratch/proto9-impl-1127/pi/compare")
SRT = os.path.expanduser("~/.aos/scratch/proto9-impl-1127/srt/node_modules/.bin/srt")
NODE_BIN = os.path.dirname(aos_pi.find_node()[0])
CODEX = shutil.which("codex") or "/usr/bin/codex"


def parse(text):
    return {r[0]: (r[1], r[2], r[3]) for r in (l.split("\t", 3) for l in text.splitlines() if l.count("\t") == 3)}


def host_env(d, out, work, llm_sock, ptrace_pid, tag):
    """PROBE_* for srt and Codex: they see the host's own paths."""
    return {"PROBE_WORK": work, "PROBE_GIT": os.path.join(work, ".git"),
            "PROBE_RO": ":".join(["/", "/usr", "/etc", os.path.expanduser("~")]),
            "PROBE_OUTSIDE": outside_dir(d, tag), "PROBE_SECRETS": secrets(),
            "PROBE_LLM_SOCK": llm_sock, "PROBE_LLM_BAD_MODEL": "not-fake-model",
            "PROBE_LITELLM": "http://127.0.0.1:4000/v1/models", "PROBE_UNIX_SOCK": out.sock_path,
            "PROBE_ABSTRACT": out.abstract, "PROBE_VSOCK_PORT": str(out.vsock_port or ""), "PROBE_SHM_ID": out.shm_id,
            "PROBE_MQ": out.mq, "PROBE_HOST_PID": str(os.getpid()), "PROBE_PTRACE_PID": str(ptrace_pid)}


def outside_dir(d, tag):
    p = os.path.join(d, "outside-" + tag)
    os.makedirs(p, exist_ok=True)
    return p


def secrets():
    return ":".join([os.path.expanduser("~/.ssh"), os.path.join(accept.REPO, "AGENTS.md"),
                     os.path.expanduser("~/.pi/agent/auth.json")])


def run_aos_pi(d, out):
    work = os.path.join(d, "work-aos-pi")
    accept.make_work(work)
    ns = types.SimpleNamespace(work=work, model="fake-model", limit=5, stack=1, lower_limit=10, upstream="http://127.0.0.1:4000/v1",
                               name="compare", sandbox_root=os.path.join(d, "aos-pi"), cont=False, git_rw=False,
                               timeout=120, fake=True, fake_script=None, daemon=DAEMON_BIN, node=None, pi=None)
    sb = aos_pi.Sandbox(ns)
    try:
        sb.start()
        probe_dir = os.path.join(sb.run, "probe")
        os.makedirs(probe_dir)
        shutil.copy(os.path.join(HERE, "probe.sh"), probe_dir)
        env = host_env(d, out, "/home/pi/work", "/llm/sock", "", "aos-pi")
        env.update({"PROBE_WORK": "/home/pi/work", "PROBE_GIT": "/home/pi/work/.git",
                    "PROBE_RO": "/:/.aos:/llm:/usr:/etc:" + os.path.expanduser("~")})
        pid = sb.d.fact(sb.kernels[-1]["name"], "pid").split("ns: ")[-1].split()[0]
        env["PROBE_PTRACE_PID"] = pid
        sb.run_in_sky("probe", ["/bin/bash", "/opt/probe/probe.sh"], 180, env=env,
                      extra=[{"type": "bind", "src": probe_dir, "dst": "/opt/probe"}])
        return parse(read(sb.p("logs", "probe.out"))), read(sb.p("logs", "probe.err"))
    finally:
        sb.stop()


def outside_kernel(d):
    """A fake llm kernel outside, for srt and Codex: does 'one allowed unix socket' work there?"""
    kd = os.path.join(d, "llm-outside")
    os.makedirs(kd)
    p = subprocess.Popen([sys.executable, os.path.join(HERE, "llm_kernel.py"), "--dir", kd, "--upstream",
                          "http://127.0.0.1:1/v1", "--model", "fake-model", "--limit", "5", "--budget",
                          os.path.join(kd, "..", "llm-outside-budget.json"), "--log", os.path.join(d, "llm-outside.jsonl"),
                          "--fake", "--no-relay"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    aos_pi.wait_until_exists(os.path.join(kd, "sock"), 10)
    return p, os.path.join(kd, "sock")


SRT_SETTINGS = {"network": {"allowedDomains": [], "deniedDomains": []},
                "filesystem": {"denyRead": [], "allowWrite": ["WORK"], "denyWrite": []}}


def run_srt(d, out, sock, kpid):
    work = os.path.join(d, "work-srt")
    accept.make_work(work)
    settings = json.loads(json.dumps(SRT_SETTINGS).replace("WORK", work))
    sp = os.path.join(d, "srt-settings.json")
    write(sp, json.dumps(settings, indent=1) + "\n")
    env = dict(os.environ, PATH=NODE_BIN + ":" + os.environ["PATH"], **host_env(d, out, work, sock, kpid, "srt"))
    r = subprocess.run([SRT, "--settings", sp, "bash", os.path.join(HERE, "probe.sh")], cwd=work, env=env,
                       capture_output=True, text=True, timeout=300)
    return parse(r.stdout), "exit %d; %s" % (r.returncode, r.stderr[-600:])


# a profile of our own: the host root readable, the -C dir (the workspace root) writable, no network;
# Codex keeps .git under a workspace root read-only by itself. (The built-in ":workspace" also gives /tmp.)
CODEX_ARGS = ["-c", 'permissions.aospi={filesystem={":root"="read", ":workspace_roots"="write"}, '
              'network={enabled=false}}', "-P", "aospi"]


def run_codex(d, out, sock, kpid):
    work = os.path.join(d, "work-codex")
    accept.make_work(work)
    env = dict(os.environ, **host_env(d, out, work, sock, kpid, "codex"))
    r = subprocess.run([CODEX, "sandbox", "-C", work] + CODEX_ARGS + ["--", "bash", os.path.join(HERE, "probe.sh")],
                       cwd=work, env=env, capture_output=True, text=True, timeout=300)
    return parse(r.stdout), "exit %d; %s" % (r.returncode, r.stderr[-600:])


def cell(row):
    if row is None:
        return "-"
    want, got, detail = row
    word = {"ok": "open"}.get(got, got)
    mark = "" if got == want or got == "n/a" else " **(!)**"
    detail = detail.replace("|", "\\|").replace(os.path.expanduser("~"), "~")[:90]
    return "%s%s<br>`%s`" % (word, mark, detail) if detail else word + mark


def table(results):
    names = []
    for r in results.values():
        for n in r[0]:
            if n not in names:
                names.append(n)
    lines = ["| check | want | aos-pi | srt | Codex |", "|---|---|---|---|---|"]
    for n in names:
        want = next(r[0][n][0] for r in results.values() if n in r[0])
        lines.append("| `%s` | %s | %s |" % (n.replace(os.path.expanduser("~"), "~"), {"blocked": "blocked", "ok": "open"}[want],
                                            " | ".join(cell(results[k][0].get(n)) for k in ("aos-pi", "srt", "codex"))))
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="the same probe in aos-pi, srt and Codex; prints a markdown table")
    ap.add_argument("--out", help="write the table (and the settings used) to this markdown file")
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()
    os.makedirs(BASE, exist_ok=True)
    d = tempfile.mkdtemp(prefix="run-", dir=BASE)
    out = accept.Outside(d)
    kp, sock = outside_kernel(d)
    results = {}
    try:
        for name, fn in (("aos-pi", lambda: run_aos_pi(d, out)), ("srt", lambda: run_srt(d, out, sock, kp.pid)),
                         ("codex", lambda: run_codex(d, out, sock, kp.pid))):
            t0 = time.monotonic()
            try:
                results[name] = fn()
            except Exception as e:
                results[name] = ({}, "could not run: %s" % e)
            print("%s: %d lines in %.1fs; %s" % (name, len(results[name][0]), time.monotonic() - t0,
                                                 results[name][1].strip()[-300:]), file=sys.stderr)
        left = {t: os.listdir(outside_dir(d, t)) for t in results if os.listdir(outside_dir(d, t))}
    finally:
        kp.terminate()
        kp.wait(5)
        out.close()
    md = table(results)
    print(md)
    if left:
        print("\nthe outside dir got: %s" % left)
    if a.out:
        write(a.out, md + "\n")
    if not a.keep:
        shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    main()
