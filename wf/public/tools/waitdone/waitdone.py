#!/usr/bin/env python3
# waitdone.py - wait until agent-fsm agents have answered (read-only; looks at <procs>/<name>/history.jsonl).
# Based on wf/temp/ok-llmk2/waitdone.py (ok-llmk2, 2026-11-14); generalized by repo-aos curation (no fixed home path, flags).
import argparse
import json
import os
import sys
import time


def procs_default():
    home = os.environ.get("AOS_HOME") or os.path.expanduser("~/aos-home")
    return os.path.join(home, "ws", ".stack", "procs")


def lines_of(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().strip().splitlines()
    except OSError:
        return None


def done(path, start_count):
    lines = lines_of(path)
    if not lines or len(lines) <= 2:
        return False
    if start_count is not None and len(lines) <= start_count:
        return False
    try:
        m = json.loads(lines[-1])
    except ValueError:
        return False
    m = m.get("message", m) if isinstance(m, dict) else {}
    return m.get("role") == "assistant" and not m.get("tool_calls")


def main():
    p = argparse.ArgumentParser(description="Wait until each named agent-fsm agent's history.jsonl ends with "
                                            "an assistant message without tool calls (= it answered and stopped).")
    p.add_argument("names", nargs="+", help="agent names (folders under --procs)")
    p.add_argument("--procs", default=procs_default(),
                   help="folder holding the agents' stacks (default: $AOS_HOME/ws/.stack/procs, else ~/aos-home/ws/.stack/procs)")
    p.add_argument("--timeout", type=int, default=1700, help="give up after this many seconds (default 1700)")
    p.add_argument("--every", type=int, default=15, help="seconds between checks (default 15)")
    p.add_argument("--new", action="store_true",
                   help="only count an answer written after this script started (history must grow first)")
    a = p.parse_args()
    paths = {n: os.path.join(a.procs, n, "history.jsonl") for n in a.names}
    start = {}
    for n, path in paths.items():
        ls = lines_of(path)
        start[n] = (len(ls) if ls else 0) if a.new else None
    t0 = time.time()
    while True:
        left = [n for n in a.names if not done(paths[n], start[n])]
        if not left:
            print("all done")
            return 0
        if time.time() - t0 >= a.timeout:
            print("timeout, not done: " + " ".join(left))
            return 1
        time.sleep(a.every)


if __name__ == "__main__":
    sys.exit(main())
