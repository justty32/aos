#!/usr/bin/env python3
import argparse
import json
import os
import signal
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

def now():
    return datetime.now(timezone.utc).isoformat()


def atomic_write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":")) if not isinstance(value, str) else value
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def agents(aos):
    mirrored = {}
    for path in sorted((aos / "agents").glob("*/status.json")):
        try:
            mirrored[path.parent.name] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return mirrored

def write_state(aos, turn, phase, running):
    atomic_write(aos / "state.json", {
        "turn": turn, "phase": phase, "running": running, "agents": agents(aos)
    })

def wait_for(item):
    proc, inst = item["proc"], item["inst"]
    timeout = inst.get("timeout_ms", 0) / 1000 or None
    try:
        stdout, stderr = proc.communicate(input=inst.get("stdin"), timeout=timeout)
        code = proc.returncode
        exit_code, sig = (code, None) if code >= 0 else (None, -code)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        stdout, stderr = proc.communicate()
        exit_code, sig = None, 9
    return {
        "id": item["id"], "exit": exit_code, "signal": sig,
        "stdout": stdout, "stderr": stderr,
        "started_at": item["started_at"], "ended_at": now(),
    }


def one_turn(folder):
    aos = folder / ".aos"
    aos.mkdir(parents=True, exist_ok=True)
    turn_path = aos / "turn"
    turn = int(turn_path.read_text(encoding="utf-8")) if turn_path.exists() else 1
    inbox = aos / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    queued = []
    for source in sorted(inbox.glob("*.json")):
        inst = json.loads(source.read_text(encoding="utf-8"))
        ident = str(inst.get("id", source.stem))
        target = aos / "batch" / str(turn) / "insts" / (ident + ".json")
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(source, target)
        queued.append((ident, inst))

    items = []
    for ident, inst in queued:
        env = os.environ.copy()
        env.update(inst.get("env", {}))
        env.update(AOS_FOLDER=str(folder), AOS_TURN=str(turn))
        started = now()
        proc = subprocess.Popen(
            inst["argv"], cwd=folder / inst.get("cwd", "."), env=env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, start_new_session=True,
        )
        items.append({"id": ident, "inst": inst, "proc": proc, "started_at": started})

    running = [{
        "id": x["id"], "argv0": x["inst"]["argv"][0], "pid": x["proc"].pid,
        "started_at": x["started_at"], "status": "running", "exit": None,
    } for x in items]
    write_state(aos, turn, "running" if items else "idle", running)
    with ThreadPoolExecutor(max_workers=max(1, len(items))) as pool:
        results = list(pool.map(wait_for, items)) if items else []
    for result in results:
        atomic_write(aos / "batch" / str(turn) / "out" / (result["id"] + ".json"), result)
    for record, result in zip(running, results):
        record.update(status="done", exit=result["exit"])
    write_state(aos, turn, "idle", running)
    atomic_write(turn_path, str(turn + 1) + "\n")
    return turn, len(items)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("folder")
    parser.add_argument("--step", type=int, default=1)
    parser.add_argument("--interval", type=int, default=100, metavar="MS")
    args = parser.parse_args()
    folder, completed = Path(args.folder).resolve(), 0
    while args.step == 0 or completed < args.step:
        turn, count = one_turn(folder)
        print(f"turn {turn}: {count} command(s)", flush=True)
        completed += 1
        if args.step == 0 or completed < args.step:
            time.sleep(args.interval / 1000)


if __name__ == "__main__":
    main()
