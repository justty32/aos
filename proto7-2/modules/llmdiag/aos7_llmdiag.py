"""讀取既有 node 檔案協定；不修改 node。"""
import json
import re
import sys
from pathlib import Path


JOB_SUFFIX = re.compile(r"(.+)_[0-9a-fA-F]{8}")


def _reject_constant(value):
    raise ValueError("invalid JSON constant: " + value)


def _object_at(path):
    try:
        with path.open(encoding="utf-8") as stream:
            value = json.load(stream, parse_constant=_reject_constant)
    except (OSError, UnicodeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _dirs(path):
    try:
        return [child for child in path.iterdir() if child.is_dir()]
    except OSError:
        return []


def diagnose(node):
    pending = []
    for budget in _dirs(node / "llmcall"):
        for call in _dirs(budget):
            if _object_at(call / "request.json") is None:
                continue
            if (call / "receipt.json").exists():
                continue
            stage = "raw" if (call / "raw.json").exists() else "request"
            pending.append({"budget": budget.name, "call_id": call.name, "stage": stage})
    pending.sort(key=lambda item: (item["budget"], item["call_id"], item["stage"]))

    halted = []
    for job in _dirs(node / "jobs"):
        match = JOB_SUFFIX.fullmatch(job.name)
        if match is None:
            continue
        rid = match.group(1)
        frame = _object_at(job / "frame.json")
        if frame is None or frame.get("phase") != "halted":
            continue
        if not (node / "author" / "req" / rid).is_dir():
            continue
        halt = frame.get("halt")
        if not isinstance(halt, dict):
            halt = {}
        halted.append({"job": job.name, "rid": rid,
                       "kind": halt.get("kind"), "why": halt.get("why")})
    halted.sort(key=lambda item: item["job"])

    inflight = []
    for budget in _dirs(node / "budget"):
        ledger = _object_at(budget / "ledger.json")
        if ledger is None:
            continue
        count = ledger.get("inflight")
        if type(count) is int and count > 0:
            inflight.append({"budget": budget.name, "inflight": count})
    inflight.sort(key=lambda item: item["budget"])

    return {"v": 1, "llmcall_pending": pending, "author_halted": halted,
            "budget_inflight": inflight}


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1 or not Path(args[0]).is_dir():
        print("usage: aos7-llmdiag <node> (node must be a directory)", file=sys.stderr)
        return 2
    print(json.dumps(diagnose(Path(args[0])), ensure_ascii=False, separators=(",", ":")))
    return 0
