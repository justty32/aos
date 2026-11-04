#!/usr/bin/env python3
"""Bounded A/B queue; standard library only, no calls to AI in --offline mode.

Usage: python3 -B queue.py JOBS [--jobs 3] [--token-cap 2700000]
       [--offline] [--model M] [--review R] [--tag T] [--root PATH]
JOBS contains GROUP TASK REP lines; blank lines and # comments are ignored.
Default root: <MN3>.ab; node: ROOT/node; outputs: ROOT/runs/A1-gap etc.
Queue log: ROOT/queue.log (JSON lines); final counts: ROOT/queue-summary.json.
The live budget uses holder author, gateway llm.litellm and grant 8,000,000.
Before EVERY launch, `aos7-budget status budget/llm` supplies settled `used`.
If used > cap, stop admitting work and drain active jobs. This is an admission
limit, not a hard cap: active reservations and their eventual tokens can exceed
it. Status failure also stops admission. Existing grant/round/ledger are reused,
never reset. This queue owns and stops the ledger that it starts.
Offline skips budget entirely and sums available output summary.total_tokens;
--offline-used N supplies a simulated baseline for testing the same stop path.
Return 0: all started jobs exited 0; 1: job failure; 2: input/setup failure;
3: stopped admitting jobs (token cap, bad status, dead ledger, signal).
"""

import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


PROTO = next(p for p in Path(__file__).resolve().parents if p.name == "proto7-2")
DEFAULT_ROOT = Path(str(PROTO.parent) + ".ab")
BUDGET_TOOL = PROTO / "packs/budget/bin/aos7-budget"
DRIVER = Path(__file__).resolve().with_name("driveab.py")


def integer(value):
    n = int(value)
    if n < 0:
        raise argparse.ArgumentTypeError("must be nonnegative")
    return n


def read_jobs(path):
    jobs, seen = [], set()
    for lineno, line in enumerate(path.read_text().splitlines(), 1):
        words = line.split("#", 1)[0].split()
        if not words:
            continue
        if len(words) != 3 or words[0] not in ("A", "B") or words[1] not in (
                "gap", "runs", "audit", "mailcount"):
            raise ValueError(f"{path}:{lineno}: expected GROUP TASK REP")
        rep = int(words[2])
        if rep < 1:
            raise ValueError(f"{path}:{lineno}: REP must be positive")
        job = (words[0], words[1], rep)
        if job in seen:
            raise ValueError(f"{path}:{lineno}: duplicate job {job}")
        seen.add(job)
        jobs.append(job)
    return jobs


def ledger_running(path):
    try:
        with path.open("r") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
            except BlockingIOError:
                return True
            fcntl.flock(lock, fcntl.LOCK_UN)
    except FileNotFoundError:
        pass
    return False


def create_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x") as stream:
            json.dump(value, stream, ensure_ascii=False)
            stream.write("\n")
    except FileExistsError:
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("list", type=Path)
    parser.add_argument("--jobs", "-j", type=integer, default=3)
    parser.add_argument("--token-cap", type=integer, default=2700000)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--model", default="chatgpt-gpt-6-luna")
    parser.add_argument("--review", default="chatgpt-gpt-6-astra-high")
    parser.add_argument("--tag", default="")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--offline-used", type=integer, default=0)
    args = parser.parse_args()
    if not args.jobs:
        parser.error("--jobs must be positive")
    if args.offline_used and not args.offline:
        parser.error("--offline-used requires --offline")
    jobs = read_jobs(args.list)
    if not DRIVER.is_file():
        raise ValueError(f"driver missing: {DRIVER}")
    root = args.root.expanduser().resolve()
    node = root / "node"
    node.mkdir(parents=True, exist_ok=True)
    queue_lock = (root / "queue.lock").open("a")
    try:
        fcntl.flock(queue_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise ValueError(f"another queue is running: {root}")
    create_json(node / ".aos/round.json", {"round": 5, "open": False})
    (root / "runs").mkdir(exist_ok=True)
    log_stream = (root / "queue.log").open("a", buffering=1)
    ledger = None
    ledger_streams = []
    active, completed = [], []
    index, peak, stop, last_used = 0, 0, None, None

    def log(event, **data):
        row = {"at": time.time(), "event": event, **data}
        log_stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(json.dumps(row, ensure_ascii=False), flush=True)

    def on_signal(number, _frame):
        nonlocal stop
        stop = stop or f"signal-{number}"

    old_handlers = {sig: signal.signal(sig, on_signal)
                    for sig in (signal.SIGINT, signal.SIGTERM)}

    def status_used():
        if args.offline:
            total = args.offline_used
            # Includes completed runs from previous invocations in this root.
            for path in (root / "runs").glob("*/summary.json"):
                value = json.loads(path.read_text()).get("total_tokens", 0)
                if not isinstance(value, (int, float)) or value < 0:
                    raise ValueError(f"invalid total_tokens: {path}")
                total += value
            return total
        if ledger.poll() is not None:
            raise ValueError(f"ledger exited {ledger.returncode}")
        result = subprocess.run([sys.executable, "-B", str(BUDGET_TOOL),
                                 "status", "budget/llm"], cwd=node,
                                capture_output=True, text=True, timeout=15)
        if result.returncode:
            raise ValueError(f"budget status rc={result.returncode}: {result.stderr[:500]}")
        used = json.loads(result.stdout)["used"]
        if type(used) is not int or used < 0:
            raise ValueError("budget status has invalid used")
        return used

    try:
        log("start", offline=args.offline, jobs=len(jobs), concurrency=args.jobs,
            token_cap=args.token_cap, node=str(node))
        if not args.offline:
            bud = node / "budget/llm"
            grant = {"v": 1, "grant": "menu-ab", "budget": "llm", "holder": "author",
                     "resource": "llm.tokens", "gateway": "llm.litellm", "amount": 8000000,
                     "clock": "completed_tock", "from": 0, "until": 1000000, "delegate": False}
            create_json(bud / "grant.json", grant)
            existing = json.loads((bud / "grant.json").read_text())
            for key in ("v", "budget", "holder", "resource", "gateway", "amount", "clock", "delegate"):
                if existing.get(key) != grant[key]:
                    raise ValueError(f"existing grant incompatible: {key}")
            if not (bud / "ledger.json").exists():
                initialized = subprocess.run([sys.executable, "-B", str(BUDGET_TOOL),
                                              "init", "budget/llm"], cwd=node,
                                             capture_output=True, text=True)
                log("budget-init", exit=initialized.returncode,
                    stdout=initialized.stdout, stderr=initialized.stderr)
                if initialized.returncode:
                    raise ValueError("budget init failed")
            if ledger_running(bud / "ledger.lock"):
                raise ValueError("ledger already running; queue must own its ledger")
            ledger_streams = [(root / "ledger.stdout").open("a"),
                              (root / "ledger.stderr").open("a")]
            ledger = subprocess.Popen([sys.executable, "-B", str(BUDGET_TOOL),
                                       "ledger", "budget/llm"], cwd=node,
                                      stdout=ledger_streams[0], stderr=ledger_streams[1])
            deadline = time.monotonic() + 5
            while not ledger_running(bud / "ledger.lock"):
                if ledger.poll() is not None or time.monotonic() > deadline:
                    raise ValueError("ledger did not become ready")
                time.sleep(0.05)
            log("ledger-start", pid=ledger.pid)
        while active or (index < len(jobs) and stop is None):
            for entry in active[:]:
                rc = entry["process"].poll()
                if rc is None:
                    continue
                entry["stdout"].close()
                entry["stderr"].close()
                result = {"group": entry["group"], "task": entry["task"],
                          "rep": entry["rep"], "exit": rc,
                          "outdir": str(entry["outdir"])}
                completed.append(result)
                active.remove(entry)
                log("finish", **result, active=len(active))
            while stop is None and index < len(jobs) and len(active) < args.jobs:
                try:
                    last_used = status_used()
                except (OSError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
                    stop = "budget-status-unavailable"
                    log("admission-stop", reason=stop, error=str(error))
                    break
                log("budget-check", used=last_used, cap=args.token_cap)
                if last_used > args.token_cap:
                    stop = "token-cap"
                    log("admission-stop", reason=stop, used=last_used, cap=args.token_cap)
                    break
                group, task, rep = jobs[index]
                outdir = root / "runs" / f"{group}{rep}-{task}"
                outdir.mkdir(exist_ok=True)
                command = [sys.executable, "-B", str(DRIVER), group, task, str(rep),
                           str(outdir), "--model", args.model, "--review", args.review]
                if args.tag:
                    command += ["--tag", args.tag]
                if args.offline:
                    command += ["--offline"]
                stdout = (outdir / "queue.stdout").open("a")
                stderr = (outdir / "queue.stderr").open("a")
                try:
                    process = subprocess.Popen(command, cwd=node, stdout=stdout, stderr=stderr)
                except OSError:
                    stdout.close()
                    stderr.close()
                    raise
                active.append({"group": group, "task": task, "rep": rep, "process": process,
                               "outdir": outdir, "stdout": stdout, "stderr": stderr})
                index += 1
                peak = max(peak, len(active))
                log("launch", group=group, task=task, rep=rep, pid=process.pid,
                    active=len(active), command=command)
            if active:
                time.sleep(0.1)
        result = {"offline": args.offline, "queued": len(jobs), "started": index,
                  "completed": completed, "remaining": len(jobs) - index,
                  "peak_active": peak, "stop": stop, "last_used": last_used}
        (root / "queue-summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        log("done", **result)
        return 3 if stop else (1 if any(r["exit"] != 0 for r in completed) else 0)
    finally:
        # Setup exceptions do not abandon already admitted work.
        for entry in active:
            entry["process"].wait()
            entry["stdout"].close()
            entry["stderr"].close()
        if ledger is not None:
            ledger.terminate()
            try:
                ledger.wait(timeout=5)
            except subprocess.TimeoutExpired:
                ledger.kill()
                ledger.wait()
            log("ledger-stop", exit=ledger.returncode)
        for stream in ledger_streams:
            stream.close()
        for sig, handler in old_handlers.items():
            signal.signal(sig, handler)
        log_stream.close()
        queue_lock.close()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print(f"queue.py: {exc}", file=sys.stderr)
        sys.exit(2)
