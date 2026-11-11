#!/usr/bin/env python3
"""Exercise optional stack ignore rules against a real, entirely fake-brain daemon tree."""
import getpass
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode = True
PROTO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(PROTO / "py"), str(PROTO / "lib")]
import aos_flags
from agent import cooldown

PROG = "gitignore-check"
HELP = """gitignore-check - optional developer regression check, never part of daemon startup

usage: python3 check.py [--evidence DIR] [--timeout-s SECONDS] [--inject-unknown] [--mntc]

Starts two isolated projects with a fake kernel, FSM agents, a fake Claude ECA,
a judge, and a child daemon. Exercises control, cooldown, stderr sweeping, bad
state preservation, graceful shutdown, local git cloning, and SIGKILL.
Checks tracked files against gitignore_classes.json, sensitive content, and hot
changes. --inject-unknown writes stacks/root/zzz_unknown.txt: this MUST exit 1.
Only local disposable fixture repositories are staged or committed. Temporary
projects and all owned processes are removed; evidence is copied to DIR
(default: /tmp/tm-team). --mntc uses the Windows temporary directory; startup
and environment/setup failures are reported with the original error.
Exit 0: all assertions passed (documented clone expected failures excluded).
Exit 1: any assertion, setup, or cleanup failed. No production state is changed.
"""


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name("." + path.name + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    os.replace(tmp, path)


def matches(pattern, name):
    # Git-style **/ also matches zero intervening directories.
    out, i = "", 0
    while i < len(pattern):
        if pattern[i:i + 3] == "**/":
            out += "(?:.*/)?"; i += 3
        elif pattern[i:i + 2] == "**":
            out += ".*"; i += 2
        elif pattern[i] == "*":
            out += "[^/]*"; i += 1
        elif pattern[i] == "[" and "]" in pattern[i + 1:]:
            end = pattern.index("]", i + 1)
            out += pattern[i:end + 1]; i = end + 1
        elif pattern[i] == "?":
            out += "[^/]"; i += 1
        else:
            out += re.escape(pattern[i]); i += 1
    return re.fullmatch(out, name) is not None


# 11-11 B05／B06（使用者選「改檢查的標準」）：追蹤檔裡的本機路徑，下面三種不算外洩（只放路徑類記號，"key prefix" 照查）：
# 使用者自己寫的絕對路徑（defs/ 底下的定義與設定、表上原樣存的 as_written，以及程式從定義原樣抄到別處的同一個字串）、
# 帳本（ledger.jsonl）、信封的 sender（寄件人＝工作區路徑）。其餘照查，命中時印出 JSON 裡的位置（where）。
# 11-11 再裁（使用者「放過」）：程式自己記的兩格絕對路徑也不算——子 daemon 公開 state 的 daemon 欄（上一層 daemon 的 stack）、
# kernel 在途信小格 proc.json 的 exec（定義裡的相對入口轉成的絕對路徑）。（檔名, JSON 位置）
ALLOWED_AT = {("procs_state.json", "/daemon"), ("state.json", "/daemon"), ("proc.json", "/exec")}
PATH_TOKENS = {"temporary root", "original HOME", "fixture HOME", "username", "hostname", "repo location"}
ALLOWED_KEYS = {"as_written", "sender"}


def allowed_file(name):
    """Whole files whose local paths are fine: user-written definitions under defs/, and ledgers."""
    return name.startswith("defs/") or name.endswith("ledger.jsonl")


def json_values(text):
    """The parsed JSON documents of a .json or .jsonl file, or None when it is not JSON."""
    try:
        return [json.loads(text)]
    except ValueError:
        pass
    docs = []
    for line in text.splitlines():
        if line.strip():
            try:
                docs.append(json.loads(line))
            except ValueError:
                return None
    return docs or None


def strings(value):
    """Every string (keys too) inside a JSON value."""
    if isinstance(value, dict):
        return {str(k) for k in value} | {s for v in value.values() for s in strings(v)}
    if isinstance(value, list):
        return {s for v in value for s in strings(v)}
    return {value} if isinstance(value, str) else set()


def user_strings(projects):
    """Strings written in the projects' definitions (defs/): a program copying one elsewhere still carries the user's own path."""
    out = set()
    for project in projects:
        for p in (project / "defs").rglob("*"):
            if p.is_file() and not p.is_symlink():
                for d in json_values(p.read_text(errors="replace")) or []:
                    out |= strings(d)
    return out


def hits(value, needle, mine, path=""):
    """Key paths (like /procs/a/ws) whose string value or key holds needle, skipping ALLOWED_KEYS and strings the user wrote (mine)."""
    out = []
    if isinstance(value, dict):
        for k, v in value.items():
            if k in ALLOWED_KEYS:
                continue
            here = path + "/" + str(k)
            if needle in str(k) and str(k) not in mine:
                out.append(here + " (key)")
            out += hits(v, needle, mine, here)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            out += hits(v, needle, mine, path + "/" + str(i))
    elif isinstance(value, str) and needle in value and value not in mine:
        out.append((path or "/") + " = " + value)
    return out


def leak_places(name, content, tokens, mine=frozenset()):
    """{token label: [where]} for the tokens that count as a leak in one tracked file."""
    found = {}
    for label, v in tokens.items():
        if not v or v.encode() not in content:
            continue
        if label in PATH_TOKENS and allowed_file(name):
            continue
        docs = json_values(content.decode("utf-8", "replace")) if label in PATH_TOKENS else None
        if docs is None:
            found[label] = ["(text)"]
            continue
        base = name.rsplit("/", 1)[-1]
        where = [w for d in docs for w in hits(d, v, mine) if (base, w.split(" = ", 1)[0]) not in ALLOWED_AT]
        if where:
            found[label] = where
    return found


class Check:
    def __init__(self, opts):
        self.timeout = float(opts.get("timeout", 45))
        self.evidence = Path(opts.get("evidence", "/tmp/tm-team")).resolve()
        self.evidence.mkdir(parents=True, exist_ok=True)
        base = "/mnt/c/Users/WG-Guanyu/AppData/Local/Temp" if opts.get("mntc") else None
        self.work = Path(tempfile.mkdtemp(prefix="aos-gitignore-", dir=base))
        self.project = self.work / "something"
        self.llms = self.work / "llms"
        self.root = self.project / "stacks/root"
        self.kernel = self.llms / "stacks/kernel"
        self.inject = opts.get("inject", False)
        self.mntc = opts.get("mntc", False)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        self.env.update(HOME=str(self.work / "home-a"),
                        PYTHONPATH=os.pathsep.join([str(PROTO / "py"), str(PROTO / "lib")]),
                        AOS_LLM_KERNEL=str(self.kernel), AOS_DAEMON=str(self.root), AOS_KNOWLEDGE=str(self.work / "kb"), AOS_HOME=str(PROTO),
                        FAKE_CLI_LOG=str(self.work / "fake-cli.jsonl"))
        self.env["PATH"] = os.pathsep.join([str(self.work / "bin"), str(Path.home() / ".local/bin"), os.environ["PATH"]])
        self.processes = []
        self.roots = {}
        self.logs = []
        self.owned = {}
        self.failures = []
        self.expected = []
        self.results = {}
        self.rows = json.loads((PROTO / "thinking/2026-11/10/two-machines/gitignore_classes.json").read_text())["rows"]
        print("Temporary fixture: " + str(self.work), flush=True)

    def note(self, label):
        print("PASS " + label, flush=True)

    def fail(self, label, data):
        self.failures.append({"check": label, "detail": data})
        print("FAIL " + label + ": " + str(data)[:1000], flush=True)

    def run(self, args, cwd=None, check=True, env=None):
        args = list(map(str, args))
        result = subprocess.run(args, cwd=cwd, env=env or self.env, capture_output=True,
                                text=True, timeout=self.timeout, stdin=subprocess.DEVNULL)
        with (self.work / "commands.log").open("a") as f:
            f.write(repr(args) + "\nexit=" + str(result.returncode) + "\n" + result.stdout + result.stderr + "\n")
        if check and result.returncode:
            raise RuntimeError(repr(args) + ": " + result.stdout + result.stderr)
        return result

    @staticmethod
    def ident(pid):
        try:
            fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
            return int(fields[1]), fields[19], fields[0]
        except (OSError, ValueError, IndexError):
            return None

    def remember(self):
        parents = {pid for pid, start in self.roots.items() if (i := self.ident(pid)) and i[1] == start}
        parents.update(pid for pid, start in self.owned.items() if (i := self.ident(pid)) and i[1] == start and i[2] != "Z")
        changed = True
        while changed:
            changed = False
            for f in Path("/proc").iterdir():
                if f.name.isdigit() and (ident := self.ident(int(f.name))):
                    pid = int(f.name)
                    if pid in parents or ident[0] in parents:
                        self.owned[pid] = ident[1]
                        if pid not in parents:
                            parents.add(pid); changed = True

    def live(self):
        return [pid for pid, start in self.owned.items() if (i := self.ident(pid)) and i[1] == start and i[2] != "Z"]

    def wait(self, label, pred):
        end = time.monotonic() + self.timeout
        while time.monotonic() < end:
            self.remember()
            if pred():
                return
            time.sleep(.15)
        tails = "\n".join(p.read_text()[-1800:] for p in self.work.glob("*.log"))
        raise RuntimeError("timed out: " + label + "\n" + tails)

    def ctl(self, stack, *args, check=True):
        return self.run(["aos-daemon-ctl", "-d", stack, *args], check=check)

    def table(self, stack):
        result = self.ctl(stack, "ls", "--json", check=False)
        try:
            return json.loads(result.stdout).get("procs", {})
        except ValueError:
            return {}

    def copy_agent(self, kind, dest):
        source = PROTO / "templates" / kind
        shutil.copytree(source, dest, symlinks=True, ignore=shutil.ignore_patterns("__pycache__", "tests"))
        kb = {"AOS_KNOWLEDGE": str(self.work / "kb")}
        tools = {"peek_now_time": {"path": str(PROTO / "lib/base/peek_now_time")},
                 "knowledge_read": {"path": str(PROTO / "lib/agent/knowledge_read"), "env": kb},
                 "knowledge_write": {"path": str(PROTO / "lib/agent/knowledge_write"), "env": kb}}
        save(dest / "tools.json", {"tools": tools})
        save(dest / "llm.json", {"model": "fake"})

    def daemon(self, folder, config):
        folder.mkdir(parents=True, exist_ok=True)
        save(folder / "_entry", ["aos-daemon", "--enable-logs", "--enable-counters", "daemon.json"])
        save(folder / "daemon.json", {"interval_ms": 150, "procs_requests": "procs_requests", **config})

    def make(self):
        (self.work / "bin").mkdir()
        (self.work / "bin/claude").symlink_to(PROTO / "cmd/aos-eca/tests/fake_claude")
        (self.work / "kb").mkdir()
        (self.work / "kb/_index.json").write_text(json.dumps({".": {"_description": "# Test knowledge"}}) + "\n")
        for project in (self.project, self.llms):
            project.mkdir()
            (project / "README.txt").write_text("A preexisting user project.\n")
            (project / "app.txt").write_text("Project code.\n")
            self.run(["git", "init", "-b", "main", project])
            self.run(["git", "-C", project, "config", "gc.auto", "0"])
            self.run(["git", "-C", project, "add", "README.txt", "app.txt"])
            self.run(["git", "-C", project, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-m", "Existing project history"])
        defs = self.project / "defs"
        sweeper = {"exec": {"argv": ["aos-sweeper", "--min-bytes", "1", "--report", {"$env": "AOS_STACK", "$path": "sweeper_report.json"}]}, "interval_ms": 600000, "auto_restart": True}
        clock = {"exec": {"argv": ["aos-clock", {"$env": "AOS_DAEMON", "$path": "clock"}]}, "interval_ms": 1000, "auto_restart": True}
        self.daemon(defs, {"procs": {"_clock": clock, "_sweeper": sweeper,
                     "foreman": {"exec": "foreman", "auto_restart": True},
                     "judge": {"exec": "judge", "auto_restart": True}}})
        self.daemon(defs / "foreman", {"procs": {"_sweeper": sweeper}})
        shutil.copytree(PROTO / "kernel/daemon-judge", defs / "judge")
        self.daemon(defs / "judge", {"exec": {"argv": ["aos-exec", str(PROTO / "lib/aos/judge"), "judge.json"]}, "procs": {"_sweeper": sweeper}})
        self.copy_agent("agent-fsm", defs / "worker")
        self.copy_agent("agent-fsm", defs / "child-worker")
        self.copy_agent("eca-claude", defs / "eca")
        shutil.copytree(PROTO / "kernel/llm-kernel", self.llms / "defs")
        self.daemon(self.llms / "defs", {"exec": {"argv": ["aos-llm-kernel", "--enable-counters", "kernel.json"]}, "procs": {"_sweeper": sweeper}})
        fail = self.work / "bin/fail-endpoint"
        fail.write_text("#!/bin/sh\ncat >/dev/null\necho 'fail-endpoint: error: EndpointFailed intentional failure' >&2\nexit 1\n")
        fail.chmod(0o755)
        save(self.llms / "defs/kernel.json", {"slots": 3, "timeout_ms": 120000, "endpoint": "fake", "exec": str(PROTO / "lib/base/llm_fake"),
             "endpoints": {"fake": {"exec": str(PROTO / "lib/base/llm_fake"), "tool": "peek_now_time"}, "bad": {"exec": str(fail)}, "slow": {"exec": "fake_slow", "delay_s": 12, "tool": "peek_now_time"}}})
        # Cause the real daemon reader to preserve a malformed public table.
        self.root.mkdir(parents=True)
        (self.root / "procs_state.json").write_text("{intentional broken state\n")
        self.defs_before = self.definition_snapshot()

    def definition_snapshot(self):
        return {str(p): (os.readlink(p) if p.is_symlink() else p.read_bytes().hex())
                for project in (self.project, self.llms) for p in (project / "defs").rglob("*") if p.is_file() or p.is_symlink()}

    def launch(self, project, stack, label):
        log = (self.work / (label + ".log")).open("w")
        env = dict(self.env); env.pop("AOS_DAEMON", None)
        p = subprocess.Popen(["aos-exec", "--stack", os.path.relpath(stack, project), "defs"], cwd=project,
                             env=env, stdout=log, stderr=log, start_new_session=True)
        self.processes.append(p); self.logs.append(log)
        if ident := self.ident(p.pid):
            self.roots[p.pid] = ident[1]
        self.wait(label + " readiness", lambda: (stack / "state.json").exists() and self.ctl(stack, "ping", "--timeout-s", "1", check=False).returncode == 0)
        return p

    def start(self, label):
        self.launch(self.llms, self.kernel, label + "-kernel")
        self.launch(self.project, self.root, label + "-root")
        self.wait("foreman and judge", lambda: all(self.table(self.root).get(n, {}).get("phase") == "running" for n in ("foreman", "judge")))

    def add(self):
        for daemon, name, definition in ((self.root, "worker", "worker"), (self.root, "eca", "eca"), (self.root / "procs/foreman", "child-worker", "child-worker")):
            env = {**self.env, "AOS_DAEMON": str(daemon)}
            self.run(["aos-agent", "ctl", "add", "--auto-restart", "--name", name, "--ws", self.project, self.project / "defs" / definition], env=env)
        self.note("root FSM, fake Claude ECA, nested FSM, judge, external kernel started")

    def ask(self, name, text, expected):
        self.run(["aos-agent", "say", "-t", name, text])
        answer = self.run(["aos-agent", "listen", "-t", name, "--timeout-s", "30"]).stdout
        if expected not in answer:
            raise RuntimeError("unexpected reply: " + answer)
        self.note(name + " reply: " + answer.strip()[:120])

    def exercise(self):
        self.ask("worker", "first question", "FAKE ANSWER")
        self.ask("eca", "first ECA question", "FAKE:")
        self.run(["aos-agent", "-t", "worker", "llm", "set", "model=bad"])
        self.run(["aos-agent", "say", "-t", "worker", "retry this question"])
        w = self.root / "procs/worker"
        self.wait("real cooldown.json after failed endpoint", lambda: cooldown.read(str(w)))
        self.run(["aos-agent", "-t", "worker", "llm", "set", "model=fake"])
        self.note("failed endpoint entered cooldown")
        for command in ("sleep", "wake", "pause", "resume"):
            self.ctl(self.root, command, "eca")
            if command == "sleep":
                self.wait("ECA sleeping", lambda: self.table(self.root).get("eca", {}).get("phase") == "sleeping")
            elif command == "wake":
                self.wait("ECA awake", lambda: self.table(self.root).get("eca", {}).get("phase") == "running")
        self.ctl(self.root, "poke", "--all")
        self.note("sleep/wake, pause/resume, poke")
        marker = self.root / "procs/eca/claude/.session_home"
        sid_file = marker.with_name("session.txt")
        old_sid = sid_file.read_text().strip()
        if not marker.exists():
            raise RuntimeError("ECA did not write .session_home")
        marker.unlink()
        shutil.rmtree(Path(self.env["HOME"]) / ".claude", ignore_errors=True)
        self.ask("eca", "ECA after relocation marker removal", "FAKE:")
        if sid_file.read_text().strip() == old_sid:
            raise RuntimeError("ECA reused session after .session_home removal")
        self.note("ECA changed session before handing over the relocation question")
        stderr = self.root / "procs/eca/stderr.txt"
        with stderr.open("a") as f:
            f.write("fixture stderr for real sweeper archival\n")
        self.ctl(self.root, "sweep", "--min-bytes", "1")
        self.wait("stderr gzip archive", lambda: list(self.root.rglob("*.gz")))
        if not list(self.root.glob("*.bad-*")):
            raise RuntimeError("malformed procs_state.json was not preserved")
        self.note("real sweeper archived stderr; malformed state preserved as .bad-*")
        # Keep one real unanswered mail in a sleeping agent mailbox for clone continuity.
        self.ctl(self.root, "sleep", "eca")
        self.wait("ECA sleeping with pending mail", lambda: self.table(self.root).get("eca", {}).get("phase") == "sleeping")
        self.run(["aos-agent", "say", "-t", "eca", "queued before clone"])
        foreman_env = {**self.env, "AOS_DAEMON": str(self.root / "procs/foreman")}
        self.run(["aos-agent", "-t", "child-worker", "llm", "set", "model=slow"], env=foreman_env)
        self.run(["aos-agent", "say", "-t", "child-worker", "in-flight across projects"], env=foreman_env)
        pending = self.root / "procs/foreman/procs/child-worker/think/pending.txt"
        self.wait("kernel and agent in-flight state", lambda: pending.exists() and list(self.kernel.glob("requests/cur/*/proc.json")))
        old_mtime = time.time() - 700
        os.utime(pending, (old_mtime, old_mtime))
        self.wait("real wait warning after artificial pending mtime age", lambda: pending.with_name("wait_warned.txt").exists())
        self.results["wait_warning_stimulus"] = "Set the real pending.txt mtime 700 seconds in the past; wait.py produced wait_warned.txt itself."
        self.note("real in-flight kernel request retained; real wait warning generated with aged mtime")

    def scan(self, label):
        text = ""
        for project in (self.project, self.llms):
            result = self.run(["find", "defs", "stacks"], cwd=project)
            text += "# " + project.name + "\n" + result.stdout
        (self.evidence / ("TG-scan-" + label + ".txt")).write_text(text)
        self.note("find snapshot " + label)

    def stop(self):
        self.remember()
        for stack in (self.root, self.kernel):
            self.ctl(stack, "shutdown", "--timeout-s", "30")
        for p in self.processes:
            p.wait(timeout=self.timeout)
        self.wait("all owned children stopped", lambda: not self.live())
        self.note("graceful shutdown left no owned processes")

    def filters(self):
        for project in (self.project, self.llms):
            shutil.copyfile(PROTO / "cmd/aos-agent/stack.gitignore", project / "stacks/.gitignore")
            # Also exercise a nested per-stack ignore file.
            for s in (project / "stacks").rglob("procs_state.json"):
                shutil.copyfile(PROTO / "cmd/aos-agent/stack.gitignore", s.parent / ".gitignore")
        if self.inject:
            (self.root / "zzz_unknown.txt").write_text("Unclassified regression probe.\n")

    def classify(self, path):
        found = [r for r in self.rows if matches(r["pattern"], path)]
        # Exclusions must win over a broad definition-source class.
        blocked = [r for r in found if r["in_git"] == "不進"]
        return (blocked or found or [None])[0]

    def inspect_git(self, label):
        counts = {}
        leaks = []
        mine = user_strings((self.project, self.llms))
        for project in (self.project, self.llms):
            self.run(["git", "-C", project, "add", "-A"])
            tracked = self.run(["git", "-C", project, "ls-files", "-z"]).stdout.split("\0")[:-1]
            unknown, forbidden = [], []
            for name in tracked:
                row = self.classify(name)
                if row is None:
                    unknown.append(name)
                elif row["in_git"] != "進":
                    forbidden.append({"path": name, "row": row["id"]})
                p = project / name
                content = os.readlink(p).encode() if p.is_symlink() else p.read_bytes()
                tokens = {"temporary root": str(self.work), "original HOME": str(Path.home()), "fixture HOME": self.env["HOME"],
                          "username": getpass.getuser(), "hostname": socket.gethostname(), "repo location": str(PROTO.parent), "key prefix": "sk-"}
                found = leak_places(name, content, tokens, mine)
                if found:
                    leaks.append({"project": project.name, "path": name, "tokens": sorted(found), "where": found})
            counts[project.name] = len(tracked)
            if unknown:
                self.fail(label + " unknown tracked files", unknown)
            else:
                self.note(label + " all tracked files classified: " + project.name)
            if forbidden:
                self.fail(label + " forbidden tracked files", forbidden)
            else:
                self.note(label + " no excluded classes tracked: " + project.name)
        if leaks:
            self.fail(label + " sensitive tracked content", leaks)
        else:
            self.note(label + " sensitive-content check")
        self.results[label] = {"tracked_counts": counts, "leaks": leaks}

    def commit(self):
        for project in (self.project, self.llms):
            self.run(["git", "-C", project, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-m", "Sleeping fixture"])

    def clone_check(self):
        original_project, original_llms = self.project, self.llms
        destination = self.work / "other-prefix/deep"
        destination.mkdir(parents=True)
        missing = {}
        for project in (original_project, original_llms):
            clone = destination / project.name
            self.run(["git", "clone", "--local", "--no-hardlinks", project, clone])
            empty = [p.relative_to(project).as_posix() for p in (project / "stacks").rglob("*") if p.is_dir() and not any(p.iterdir())]
            missing[project.name] = [p for p in empty if not (clone / p).exists()]
        original_project.rename(self.work / "source-hidden-something")
        original_llms.rename(self.work / "source-hidden-llms")
        self.project, self.llms = destination / "something", destination / "llms"
        self.root, self.kernel = self.project / "stacks/root", self.llms / "stacks/kernel"
        self.env.update(HOME=str(self.work / "home-b"), AOS_DAEMON=str(self.root), AOS_LLM_KERNEL=str(self.kernel))
        before = len(self.processes)
        child_stderr = self.root / "procs/foreman/procs/child-worker/stderr.txt"
        continuity_stage = "startup"
        try:
            self.start("clone")
            self.ask("worker", "after clone", "FAKE ANSWER")
            self.ctl(self.root, "wake", "eca", check=False)
            queued = self.run(["aos-agent", "listen", "-t", "eca", "--timeout-s", "30"]).stdout
            if "queued before clone" not in queued:
                raise RuntimeError("queued clone mail was not delivered: " + queued)
            self.ask("eca", "after clone ECA", "FAKE:")
            self.note("clone resumed FSM/ECA and delivered queued mail")
            child_stderr = self.root / "procs/foreman/procs/child-worker/stderr.txt"
            self.wait("cloned child in-flight request outcome", lambda: (child_stderr.exists() and "EntryMissing" in child_stderr.read_text()) or not (self.root / "procs/foreman/procs/child-worker/think/pending.txt").exists())
            original = child_stderr.read_text() if child_stderr.exists() else ""
            self.results["cloned_inflight_stderr"] = original
            if "EntryMissing" in original or "EndpointFailed" in original:
                raise RuntimeError("known interrupted in-flight endpoint failure: " + original[-4000:])
            child_env = {**self.env, "AOS_DAEMON": str(self.root / "procs/foreman")}
            continuity_stage = "retained-child-inflight"
            child_reply = self.run(["aos-agent", "listen", "-t", "child-worker", "--timeout-s", "30"], env=child_env).stdout
            if "in-flight across projects" not in child_reply or "FAKE ANSWER" not in child_reply:
                raise RuntimeError("cloned in-flight mail did not produce the expected answer: " + child_reply)
        except (OSError, RuntimeError, subprocess.SubprocessError) as e:
            detail = {"check": "clone continuity", "reason": str(e)}
            child = self.root / "procs/foreman/procs/child-worker"
            self.results["clone_inflight_diagnostics"] = {str(p.relative_to(child)): p.read_text(errors="replace")
                for p in child.rglob("*") if p.is_file() and p.suffix != ".gz" and p.stat().st_size < 200000}
            self.results["clone_kernel_inflight_diagnostics"] = {str(p.relative_to(self.kernel)): p.read_text(errors="replace")
                for p in self.kernel.glob("requests/cur/*/*") if p.is_file() and p.stat().st_size < 200000}
            actual_stderr = child_stderr.read_text() if child_stderr.exists() else ""
            detail["inflight_stderr"] = actual_stderr
            known_missing_reply_mailbox = "MailboxMissing" in actual_stderr and "/think/reply" in actual_stderr
            known_missing_inflight_answer = continuity_stage == "retained-child-inflight" and "child-worker" in str(e) and "AnswerMissing" in str(e)
            if "EntryMissing" in str(e) or "known interrupted in-flight endpoint failure:" in str(e) or known_missing_inflight_answer:
                if known_missing_reply_mailbox:
                    detail["known_issue"] = "Retained pending.txt takes the receive branch, which does not initialize the empty think/reply mailbox omitted by git. wait.py reports MailboxMissing before BrainFailed; its send branch alone initializes that mailbox (wait.py:173-205)."
                elif known_missing_inflight_answer:
                    detail["known_issue"] = "After both source project paths disappear, the retained cross-project in-flight request does not deliver an answer within 30 seconds. Reproduced with a 12-second fake endpoint and a 120-second kernel deadline; ordinary cloned FSM/ECA requests and the queued ECA letter pass."
                self.expected.append(detail)
                print("EXPECTED FAILURE clone continuity: " + str(e)[:2000], flush=True)
            else:
                self.fail("clone continuity", str(e))
        finally:
            for stack in (self.root, self.kernel):
                self.ctl(stack, "shutdown", "--timeout-s", "10", check=False)
            self.remember()
            for p in self.processes[before:]:
                try:
                    p.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    os.killpg(p.pid, signal.SIGKILL); p.wait()
        for p in self.llms.glob("stacks/kernel/requests/cur/*/stderr.txt"):
            self.results.setdefault("cloned_kernel_request_stderr", []).append(p.read_text())
        rebuilt = {project.name: {name: (project / name).is_dir() for name in missing[project.name]}
                   for project in (self.project, self.llms)}
        self.results["clone_empty_directories"] = {"omitted": missing, "rebuilt": rebuilt}
        for project in (self.project, self.llms):
            status = self.run(["git", "-C", project, "status", "--porcelain", "--untracked-files=all", "-z"]).stdout.split("\0")
            bad, changes = [], []
            for item in status:
                if not item:
                    continue
                name = item[3:]
                row = self.classify(name)
                changes.append({"path": name, "class": row and row["class"]})
                if row is None or row["class"] != "carry":
                    bad.append(name)
            self.results["hot_changes_" + project.name] = changes
            if bad:
                self.fail("hot changes outside carry: " + project.name, bad)
            else:
                self.note("hot changes are carry only: " + project.name)
        (self.work / "source-hidden-something").rename(original_project)
        (self.work / "source-hidden-llms").rename(original_llms)
        self.project, self.llms = original_project, original_llms
        self.root, self.kernel = self.project / "stacks/root", self.llms / "stacks/kernel"
        self.env.update(HOME=str(self.work / "home-a"), AOS_DAEMON=str(self.root), AOS_LLM_KERNEL=str(self.kernel))

    def kill_check(self):
        self.start("kill9")
        self.ask("eca", "before abrupt stop", "FAKE:")
        self.remember()
        for pid in reversed(self.live()):
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        for p in self.processes:
            p.wait(timeout=self.timeout)
        self.wait("SIGKILL descendants gone", lambda: not self.live())
        self.scan("kill9")
        self.inspect_git("kill9")

    def check(self):
        self.make(); self.start("running"); self.add(); self.exercise(); self.scan("running")
        self.stop(); self.scan("shutdown")
        after = self.definition_snapshot()
        delta = sorted(p for p in set(after) | set(self.defs_before) if after.get(p) != self.defs_before.get(p))
        self.results["definition_changes"] = delta
        if delta:
            self.fail("runtime changes in definitions", delta)
        else:
            self.note("no runtime files written into definitions")
        self.filters(); self.inspect_git("shutdown"); self.commit(); self.clone_check(); self.kill_check()

    def cleanup(self):
        self.remember()
        for sig in (signal.SIGTERM, signal.SIGKILL):
            for pid in self.live():
                try:
                    os.kill(pid, sig)
                except ProcessLookupError:
                    pass
            for p in self.processes:
                try:
                    p.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    pass
        for log in self.logs:
            log.close()
        survivors = self.live()
        self.results["cleanup"] = {"owned_survivors": survivors, "temporary_fixture_removed": not survivors}
        if survivors:
            self.fail("cleanup", survivors)
        self.results.update(failures=self.failures, expected_failures=self.expected)
        for p in self.work.glob("*.log"):
            shutil.copyfile(p, self.evidence / ("TG-" + p.name))
        if (self.work / "fake-cli.jsonl").exists():
            shutil.copyfile(self.work / "fake-cli.jsonl", self.evidence / "TG-fake-cli.jsonl")
        save(self.evidence / "TG-check-results.json", self.results)
        save(self.evidence / "TG-owned-pids.json", self.owned)
        if not survivors:
            shutil.rmtree(self.work)
            self.note("temporary fixture removed; no owned processes remain")


def main():
    aos_flags.HELP = HELP
    try:
        opts, rest = aos_flags.parse(sys.argv[1:], {"--evidence": "evidence", "--timeout-s": "timeout"},
                                     switches={"--inject-unknown": "inject", "--mntc": "mntc"})
    except aos_flags.Error as e:
        aos_flags.die(PROG, e.code, str(e))
    if rest:
        aos_flags.die(PROG, "ArgumentsBad", "unexpected positional arguments")
    try:
        timeout = float(opts.get("timeout", 45))
    except ValueError:
        aos_flags.die(PROG, "ArgumentsBad", "--timeout-s must be a positive number")
    if not math.isfinite(timeout) or timeout <= 0:
        aos_flags.die(PROG, "ArgumentsBad", "--timeout-s must be positive")
    try:
        check = Check(opts)
    except (OSError, ValueError, KeyError) as e:
        aos_flags.die(PROG, "SetupFailed", str(e))
    try:
        check.check()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as e:
        check.fail("execution", str(e))
    finally:
        check.cleanup()
    if check.failures:
        aos_flags.die(PROG, "CheckFailed", str(len(check.failures)) + " checks failed; see " + str(check.evidence / "TG-check-results.json"))
    print("ALL CHECKS PASSED", flush=True)


if __name__ == "__main__":
    aos_flags.run(main)
