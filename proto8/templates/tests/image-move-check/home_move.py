#!/usr/bin/env python3
"""Verify a subagent survives renaming the whole tree folder (A/ to B/): still listed, its notices reach the parent's mailbox, no old path in the files that travel."""
import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from check import Check  # noqa: E402

# One body for parent and kid: make my mailbox, write where my notices go (into the workspace, not the stack), send one notice there, then idle.
BODY = """#!/bin/sh
aos-post init "$AOS_STACK/mailbox" >/dev/null 2>&1
printf '%s\\n' "$AOS_NOTIFY_BOX" > "$AOS_WS/$(basename "$AOS_STACK").notify_box"
if [ -n "$AOS_NOTIFY_BOX" ]; then
    printf '{"from": "kid", "box": "%s"}' "$AOS_NOTIFY_BOX" | aos-post send "$AOS_NOTIFY_BOX" >/dev/null
fi
exec sleep 600
"""


class HomeMove(Check):
    def __init__(self, timeout, work_prefix):
        super().__init__(timeout, work_prefix)
        self.env["AOS_HOME"] = str(self.repo)

    def make(self, image):
        defs = image / "defs"
        for name in ("root", "body"):
            (defs / name).mkdir(parents=True)
        (defs / "root/_entry").write_text('["aos-daemon", "--enable-logs", "daemon.json"]\n')
        (defs / "root/daemon.json").write_text(json.dumps({"interval_ms": 100, "procs": {}}) + "\n")
        (defs / "body/_entry").write_text(BODY)
        (defs / "body/_entry").chmod(0o755)
        (image / "ws").mkdir()

    def at(self, image):
        self.image, self.stack = image, image / "stack"
        self.parent, self.kid = self.stack / "procs/parent", self.stack / "procs/kid"
        self.box = self.parent / "mailbox"

    def start(self, label):
        self.log = (self.work / f"{label}.log").open("w")
        self.process = subprocess.Popen(["aos-exec", "--stack", str(self.stack), str(self.image / "defs/root")],
                                        env=self.env, stdout=self.log, stderr=self.log, start_new_session=True)
        self.wait(f"root daemon up in {label}", lambda: self.quiet(["aos-daemon-ctl", "--daemon", str(self.stack), "ping"]))

    def quiet(self, args):
        return subprocess.run(args, env=self.env, capture_output=True, timeout=self.timeout).returncode == 0

    def stop(self):
        self.remember()
        self.process.send_signal(signal.SIGINT)
        self.process.wait(timeout=self.timeout)
        self.log.close()
        deadline = time.monotonic() + self.timeout
        while self.live_owned() and time.monotonic() < deadline:
            time.sleep(0.1)
        if self.live_owned():
            raise RuntimeError(f"owned processes survived root shutdown: {self.live_owned()}")
        self.process = None

    def subagent(self, args):
        # What the parent agent's subagent tool call does: its tool cell as AOS_STACK, its daemon and workspace.
        env = dict(self.env, AOS_DAEMON=str(self.stack) + "/", AOS_STACK=str(self.parent / "tools/subagent"),
                   AOS_WS=str(self.image / "ws"))
        return self.run([str(self.repo / "lib/tools/agent/subagent/_entry")], input=json.dumps(args),
                        env=env, cwd=str(self.image / "ws"))

    def run(self, args, env=None, **kwargs):
        if env is None:
            return super().run(args, **kwargs)
        saved, self.env = self.env, env
        try:
            return super().run(args, **kwargs)
        finally:
            self.env = saved

    def notices(self):
        out = []
        for letter in sorted(self.box.glob("*/*/letter.json")):
            try:
                out.append(json.loads(letter.read_text()))
            except (OSError, ValueError):
                pass
        return out

    def told(self, label):
        want, seen = str(self.box), self.image / "ws/kid.notify_box"
        self.wait(f"kid notice to {want} ({label})", lambda: seen.is_file() and seen.read_text().strip() == want
                  and any(n.get("body", {}).get("box") == want for n in self.notices()))
        print(f"PASS notice ({label}): the kid's AOS_NOTIFY_BOX is {want} and its letter is there", flush=True)
        for letter in self.box.glob("*/*/letter.json"):   # the parent has read it (a waiting letter keeps its sender's absolute path)
            shutil.rmtree(letter.parent)

    def travelling(self):
        # The files a git image would carry: the stack filter applied without writing a .gitignore into the stack.
        probe = self.work / "probe.git"
        if not probe.exists():
            self.run(["git", "init", "-q", "--bare", str(probe)])
        listed = self.run(["git", "--git-dir", str(probe), "--work-tree", str(self.stack), "ls-files", "-o",
                           "--exclude-from", str(self.repo / "py/aos/apps/agent/stack.gitignore")])
        return [line for line in listed.splitlines() if line]

    def old_path_hits(self, old):
        needle = old.encode()
        carried = set(self.travelling())
        hits = {"carried": [], "not_carried": []}
        for path in sorted(p for p in self.stack.rglob("*") if p.is_file()):
            rel = str(path.relative_to(self.stack))
            try:
                if needle in path.read_bytes():
                    hits["carried" if rel in carried else "not_carried"].append(rel)
            except OSError:
                pass
        (self.work / "old-path-hits.json").write_text(json.dumps({"old": old, "carried_files": len(carried), **hits}, indent=2) + "\n")
        return hits

    def check(self):
        a, b = self.work / "A", self.work / "B"
        self.make(a)
        self.at(a)
        self.start("A")
        self.run(["aos-agent", "--daemon", str(self.stack), "ctl", "add", "--name", "parent", "--ws", "ws", "defs/body"], cwd=str(a))
        self.wait("parent mailbox", lambda: (self.box / "new").is_dir())
        added = self.subagent({"op": "add", "def": "../defs/body", "name": "kid"})
        if "subagents 1/" not in added:
            raise RuntimeError(f"unexpected add answer: {added!r}")
        book = self.read(self.parent / "tools/subagent/subagents.json")
        if book != [{"name": "kid", "stack": "procs/kid"}]:
            raise RuntimeError(f"the book does not keep the kid relative to the daemon stack: {book!r}")
        self.told("A")
        self.stop()
        os.rename(a, b)
        self.at(b)
        hits = self.old_path_hits(str(a))
        if hits["carried"]:
            raise RuntimeError(f"files that travel still name {a}: {hits['carried']}")
        print(f"PASS no {a} in the files that travel (only in {len(hits['not_carried'])} runtime files)", flush=True)
        self.start("B")
        listed = self.subagent({"op": "ls"})
        rows = [line.split("\t") for line in listed.splitlines()]
        if not any(r[0] == "kid" and len(r) > 1 and r[1] != "queued" for r in rows) or "subagents 1/" not in listed:
            raise RuntimeError(f"subagent ls forgot the kid after the move: {listed!r}")
        print("PASS subagent ls still lists kid after A/ -> B/", flush=True)
        self.told("B")
        who = json.loads(self.run(["aos-agent", "--daemon", str(self.stack), "ctl", "who", "--json", "--stack", str(self.kid)]))
        if (who.get("notify_box"), who.get("parent")) != (str(self.box), str(self.parent)):
            raise RuntimeError(f"ctl who shows old or missing registrations: {who!r}")
        print("PASS ctl who: notify_box and parent point into B/", flush=True)
        (self.work / "result.json").write_text(json.dumps({"book": book, "ls": listed, "who": who}, indent=2) + "\n")
        self.stop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout-s", type=float, default=40, help="deadline for each readiness/command/shutdown step")
    parser.add_argument("--work-prefix", default="aos-home-move-", help="temporary evidence directory prefix")
    args = parser.parse_args()
    if args.timeout_s <= 0:
        parser.error("--timeout-s must be positive")
    check = HomeMove(args.timeout_s, args.work_prefix)
    started = time.monotonic()
    status = 0
    try:
        check.check()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"home-move-check: error: CheckFailed {error}", file=sys.stderr)
        status = 1
    finally:
        try:
            check.cleanup()
        except (OSError, RuntimeError, subprocess.SubprocessError) as error:
            print(f"home-move-check: error: CleanupFailed {error}", file=sys.stderr)
            status = 1
    print(f"Elapsed: {time.monotonic() - started:.2f} s; evidence retained: {check.work}")
    return status


if __name__ == "__main__":
    sys.exit(main())
