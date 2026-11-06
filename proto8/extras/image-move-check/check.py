#!/usr/bin/env python3
"""Verify a sleeping fake-brain daemon tree survives copying and a local git clone."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time


class Check:
    def __init__(self, timeout, work_prefix="aos-image-move-"):
        self.timeout = timeout
        self.work = Path(tempfile.mkdtemp(prefix=work_prefix))
        self.repo = Path(__file__).resolve().parents[2]
        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith("AOS_")}
        self.env["PATH"] = str(Path.home() / ".local/bin") + os.pathsep + os.environ["PATH"]
        self.owned = {}
        self.process = None
        self.log = None
        print(f"Evidence: {self.work}", flush=True)

    def run(self, args, **kwargs):
        result = subprocess.run(args, env=self.env, text=True, capture_output=True,
                                timeout=self.timeout, **kwargs)
        with (self.work / "commands.log").open("a") as log:
            log.write(f"{args!r}\nexit={result.returncode}\n{result.stdout}{result.stderr}\n")
        if result.returncode:
            raise RuntimeError(f"command failed ({result.returncode}): {args!r}: {result.stderr.strip()}")
        return result.stdout

    @staticmethod
    def read(path):
        try:
            return json.loads(path.read_text())
        except (OSError, ValueError):
            return {}

    def wait(self, label, predicate):
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            self.remember()
            if predicate():
                return
            if self.process and self.process.poll() is not None:
                raise RuntimeError(f"root exited before {label}: {self.process.returncode}")
            time.sleep(0.1)
        raise RuntimeError(f"timed out waiting for {label}")

    @staticmethod
    def identity(pid):
        try:
            fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
            return int(fields[1]), fields[19], fields[0]
        except (OSError, ValueError, IndexError):
            return None

    def remember(self):
        # Record only descendants of this run's root, never processes found by name.
        if not self.process:
            return
        parents = {self.process.pid}
        changed = True
        while changed:
            changed = False
            for item in Path("/proc").iterdir():
                if not item.name.isdigit():
                    continue
                pid = int(item.name)
                ident = self.identity(pid)
                if ident and (pid in parents or ident[0] in parents):
                    self.owned[pid] = ident[1]
                    if pid not in parents:
                        parents.add(pid)
                        changed = True
        (self.work / "owned_pids.json").write_text(json.dumps(self.owned, indent=2) + "\n")

    def live_owned(self):
        return [pid for pid, start in self.owned.items()
                if (ident := self.identity(pid)) and ident[1] == start and ident[2] != "Z"]

    def signal_owned(self, sig):
        for pid in self.live_owned():
            try:
                os.kill(pid, sig)
            except ProcessLookupError:
                pass

    def layout(self, image):
        self.image = image
        self.root = image / "state"
        self.kernel = self.root / "procs/kernel"
        self.foreman = self.root / "procs/foreman"
        self.env["AOS_LLM_KERNEL"] = str(self.kernel)
        self.env["AOS_DAEMON"] = str(self.foreman)

    def make(self):
        image = self.work / "original"
        image.mkdir()
        for name in ("lib", "py", "templates"):
            self.run(["cp", "-a", str(self.repo / name), str(image / name)])
        defs = image / "defs"
        defs.mkdir()
        self.run(["cp", "-a", str(self.repo / "templates/agent-fsm"), str(defs / "agent")])
        configs = {
            "root": {"tick": True, "interval_ms": 100, "procs": {
                "kernel": {"exec": "../kernel", "auto_restart": True},
                "foreman": {"exec": "../foreman", "auto_restart": True}}},
            "foreman": {"tick": True, "interval_ms": 100, "procs": {}},
            "kernel": {"tick": True, "interval_ms": 100,
                       "exec": {"argv": ["aos-llm-kernel", "kernel.json"]}},
        }
        for name, config in configs.items():
            folder = defs / name
            folder.mkdir()
            (folder / "_entry").write_text('["aos-daemon", "--enable-logs", "daemon.json"]\n')
            (folder / "daemon.json").write_text(json.dumps(config) + "\n")
        (defs / "kernel/kernel.json").write_text(json.dumps({
            "slots": 2, "timeout_ms": 10000, "endpoint": "fake",
            "exec": "../../lib/base/llm_fake", "endpoints": {
                "fake": {"exec": "../../lib/base/llm_fake"}}}) + "\n")
        (defs / "agent/tools.json").write_text('{"tools": {}}\n')
        (defs / "agent/llm.json").write_text('{"endpoint": "fake"}\n')
        self.layout(image)

    def start(self, label):
        self.log = (self.work / f"{label}.log").open("w")
        env = dict(self.env)
        env.pop("AOS_DAEMON", None)
        self.process = subprocess.Popen(["aos-exec", "--stack", str(self.root),
                                         str(self.image / "defs/root")],
                                        env=env, stdout=self.log, stderr=self.log,
                                        start_new_session=True)
        for stack in (self.root, self.kernel, self.foreman):
            self.wait(f"ready {stack}", lambda s=stack:
                      self.read(s / "state.json").get("counter_runs", 0) >= 1)
            self.run(["aos-daemon-ctl", "--daemon", str(stack), "ping"])

    def table(self, stack):
        return json.loads(self.run(["aos-daemon-ctl", "--daemon", str(stack), "ls", "--json"]))

    def snapshot(self, label):
        result = {}
        for name, stack in (("root", self.root), ("kernel", self.kernel), ("foreman", self.foreman)):
            result[name] = {"table": self.table(stack), "state": self.read(stack / "state.json")}
        (self.work / f"{label}.json").write_text(json.dumps(result, indent=2) + "\n")
        return result

    def ask(self, message):
        self.run(["aos-agent", "say", "--target", "worker", message])
        answer = self.run(["aos-agent", "listen", "--target", "worker"])
        if message not in answer or "FAKE ANSWER" not in answer:
            raise RuntimeError(f"unexpected fake answer: {answer!r}")
        print(f"PASS reply: {answer.strip()}", flush=True)

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
        snapshot = self.snapshot("sleeping-" + self.image.name)
        for name, item in snapshot.items():
            if any(row["phase"] != "sleeping" for row in item["table"]["procs"].values()):
                raise RuntimeError(f"{name} did not put every child to sleep")
        return snapshot

    def clone_image(self):
        # Apply the documented per-stack filters only after the whole tree sleeps.
        source = self.image
        for stack in (self.root, self.kernel, self.foreman):
            self.run(["cp", str(self.repo / "cmd/aos-agent/stack.gitignore"),
                      str(stack / ".gitignore")])
        self.run(["cp", str(self.repo / "cmd/aos-agent/stack.gitattributes"),
                  str(source / ".gitattributes")])
        (source / ".gitignore").write_text("ws/.trash/\n")
        self.run(["git", "init", "-b", "main", str(source)])
        self.run(["git", "-C", str(source), "config", "gc.auto", "0"])
        self.run(["git", "-C", str(source), "add", "-A"])
        tree = self.run(["git", "-C", str(source), "write-tree"]).strip()
        commit = self.run(["git", "-C", str(source), "-c", "user.name=Image Check",
                           "-c", "user.email=image-check@example.invalid",
                           "commit-tree", tree, "-m", "Frozen image"]).strip()
        self.run(["git", "-C", str(source), "update-ref", "refs/heads/main", commit])
        parents = self.run(["git", "-C", str(source), "rev-list", "--parents", "-n", "1", "main"]).split()[1:]
        tracked = self.run(["git", "-C", str(source), "ls-files"]).splitlines()
        queue_relative = str((self.kernel / "queue.json").relative_to(source))
        if queue_relative in tracked:
            raise RuntimeError("documented stack filter unexpectedly retained queue.json")
        empty = [str(p.relative_to(source)) for p in source.rglob("*")
                 if p.is_dir() and ".git" not in p.parts and not any(p.iterdir())]
        destination = self.work / "cloned"
        self.run(["git", "-c", "protocol.file.allow=always", "clone", "--local",
                  "--no-hardlinks", str(source), str(destination)])
        missing_empty = [p for p in empty if not (destination / p).exists()]
        (self.work / "clone-evidence.json").write_text(json.dumps({
            "commit": commit, "commit_parent_count": len(parents), "tracked_files": len(tracked),
            "queue_excluded": queue_relative not in tracked,
            "empty_directories_omitted": missing_empty,
            "note": "The documented filter drops queue.json; its counter restarts on clone."},
            indent=2) + "\n")
        self.layout(destination)

    def check(self):
        self.make()
        self.start("original")
        self.run(["aos-agent", "ctl", "add", "--name", "worker", str(self.image / "defs/agent")])
        worker = self.foreman / "procs/worker/state.json"
        self.wait("worker ran several times", lambda: self.read(worker).get("counter_runs", 0) >= 3)
        self.ask("before relocation")
        before_queue = self.read(self.kernel / "queue.json")["counter_runs"]
        before = self.stop()
        self.run(["sync"])
        self.run(["cp", "-a", str(self.image), str(self.work / "relocated")])
        self.layout(self.work / "relocated")
        self.start("relocated")
        self.ask("after relocation")
        after = self.snapshot("awake-relocated")
        for name in before:
            if any(row["phase"] != "running" for row in after[name]["table"]["procs"].values()):
                raise RuntimeError(f"{name} has a child that did not wake")
        final = self.stop()
        after_queue = self.read(self.kernel / "queue.json")["counter_runs"]
        if after_queue <= before_queue:
            raise RuntimeError("persistent kernel queue counter did not continue")
        (self.work / "counter-comparison.json").write_text(json.dumps({
            "kernel_queue_before": before_queue, "kernel_queue_after": after_queue,
            "note": "Loop state counters restart at zero; queue counter is persistent."}, indent=2) + "\n")
        print(f"PASS persistent kernel counter: {before_queue} -> {after_queue}", flush=True)
        print("PASS copy relocation: sleeping phases, running phases, fake replies", flush=True)
        self.clone_image()
        self.start("cloned")
        self.ask("after local git clone")
        cloned = self.snapshot("awake-cloned")
        for name, item in cloned.items():
            if any(row["phase"] != "running" for row in item["table"]["procs"].values()):
                raise RuntimeError(f"{name} has a child that did not wake after clone")
        clone_queue = self.read(self.kernel / "queue.json")["counter_runs"]
        self.stop()
        (self.work / "clone-result.json").write_text(json.dumps({
            "queue_before_clone": after_queue, "queue_after_clone": clone_queue,
            "all_children_running": True, "fake_reply_received": True,
            "note": "queue.json is intentionally excluded by the documented git recipe."},
            indent=2) + "\n")
        print("PASS local git clone: third location, running phases, fake reply", flush=True)

    def cleanup(self):
        self.remember()
        self.signal_owned(signal.SIGINT)
        if self.process:
            try:
                self.process.wait(timeout=self.timeout)
            except subprocess.TimeoutExpired:
                self.signal_owned(signal.SIGTERM)
                self.process.wait(timeout=self.timeout)
        self.signal_owned(signal.SIGTERM)
        # Observation only: never signal processes selected by pgrep.
        result = subprocess.run(["pgrep", "-a", "aos-"], text=True, capture_output=True)
        (self.work / "pgrep-final.txt").write_text(result.stdout)
        if self.live_owned():
            raise RuntimeError(f"owned processes remain: {self.live_owned()}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout-s", type=float, default=40, help="deadline for each readiness/command/shutdown step")
    parser.add_argument("--work-prefix", default="aos-image-move-", help="temporary evidence directory prefix")
    args = parser.parse_args()
    if args.timeout_s <= 0:
        parser.error("--timeout-s must be positive")
    check = Check(args.timeout_s, args.work_prefix)
    started = time.monotonic()
    status = 0
    try:
        check.check()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"image-move-check: error: CheckFailed {error}", file=sys.stderr)
        status = 1
    finally:
        try:
            check.cleanup()
        except (OSError, RuntimeError, subprocess.SubprocessError) as error:
            print(f"image-move-check: error: CleanupFailed {error}", file=sys.stderr)
            status = 1
    print(f"Elapsed: {time.monotonic() - started:.2f} s; evidence retained: {check.work}")
    return status


if __name__ == "__main__":
    sys.exit(main())
