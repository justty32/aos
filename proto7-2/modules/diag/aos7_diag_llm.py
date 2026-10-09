"""讀取既有 node 檔案協定；不修改 node。"""
import json
import re
import os
import stat


ABSENT = (FileNotFoundError, NotADirectoryError, IsADirectoryError)


JOB_SUFFIX = re.compile(r"(.+)_[0-9a-fA-F]{8}")


def _reject_constant(value):
    raise ValueError("invalid JSON constant: " + value)


def _object_at(path):
    try:
        with path.open(encoding="utf-8") as stream:
            value = json.load(stream, parse_constant=_reject_constant)
    except (*ABSENT, UnicodeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _stat(path):
    try:
        return os.stat(path)
    except ABSENT:
        return None


def is_directory(path):
    info = _stat(path)
    return info is not None and stat.S_ISDIR(info.st_mode)


def _dirs(path):
    try:
        return [child for child in path.iterdir() if is_directory(child)]
    except ABSENT:
        return []


def diagnose(node):
    pending = []
    for budget in _dirs(node / "llmcall"):
        for call in _dirs(budget):
            if _object_at(call / "request.json") is None:
                continue
            if _stat(call / "receipt.json") is not None:
                continue
            stage = "raw" if _stat(call / "raw.json") is not None else "request"
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
        if not is_directory(node / "author" / "req" / rid):
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

