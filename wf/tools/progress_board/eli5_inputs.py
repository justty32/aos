"""Gather bounded evidence and change fingerprints for everyday progress explanations."""

import datetime as dt
import glob
import hashlib
import json
from pathlib import Path

from answers import asks_state, read_answers, read_asks
from codex_api import codex_processes
from collect import handoff_path, parse_ts, read_jsonl
from safe_files import ApiError, safe_read


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def text(path, limit=None):
    try:
        with Path(path).open(encoding="utf-8", errors="replace") as stream:
            return stream.read(limit)
    except OSError:
        return ""


def json_file(path):
    try:
        value = json.loads(text(path))
        return value if isinstance(value, dict) else {}
    except ValueError:
        return {}


def events_by_line(board):
    grouped = {}
    for event in read_jsonl(Path(board) / "data/progress.jsonl"):
        if (isinstance(event, dict) and isinstance(event.get("line"), str)
                and parse_ts(event.get("ts")) and isinstance(event.get("text"), str)):
            grouped.setdefault(event["line"], []).append(event)
    for events in grouped.values():
        events.sort(key=lambda event: parse_ts(event["ts"]))
    return grouped


def _handoff(cfg, line, limit):
    if not line.get("handoff"):
        return None, ""
    try:
        result = safe_read(cfg, handoff_path(cfg, line["handoff"]), limit * 4)
        return result["mtime"], result["text"][:limit]
    except ApiError:
        return None, ""


def main_input(board, cfg):
    grouped = events_by_line(board)
    raw = read_asks(board)
    asks = asks_state(raw, read_answers(board), dt.datetime.now().astimezone())
    provided = {ask["id"]: ask.get("eli5") for ask in raw}
    opened = [{key: ask[key] for key in ("id", "line", "text", "options", "recommend")}
              | {"eli5": provided.get(ask["id"])}
              for ask in asks if ask["answer"] is None]
    lines = [{"id": line["id"], "title": line.get("title", line["id"]),
              "events": grouped.get(line["id"], [])[-10:],
              "handoff": _handoff(cfg, line, 3000)[1]}
             for line in cfg.get("lines", [])]
    latest = text(Path(board) / "summary/latest.md")
    latest_events = {key: events[-1]["ts"] for key, events in grouped.items()}
    fingerprint = digest([latest, sorted(ask["id"] for ask in opened), latest_events])
    return fingerprint, {"summary": latest, "lines": lines, "open_asks": opened}


def detail_input(board, cfg):
    grouped, blocks, fingerprints = events_by_line(board), {}, {}
    for line in cfg.get("lines", []):
        events = grouped.get(line["id"], [])
        key = f"lines.{line['id']}.timeline"
        blocks[key] = {"title": line.get("title", line["id"]), "events": events[-30:]}
        fingerprints[key] = digest(events[-1]["ts"] if events else None)
        key = f"lines.{line['id']}.handoff"
        mtime, content = _handoff(cfg, line, 6000)
        blocks[key] = {"title": line.get("title", line["id"]), "handoff": content}
        fingerprints[key] = digest(mtime)
    processes, process_keys = [], []
    for process in codex_processes(cfg):
        size = 0
        log = process.get("log_file")
        tail = process.get("log_tail") or ""
        if log:
            try:
                value = safe_read(cfg, log, 256 * 1024, tail=True)
                size, tail = value["size"], value["text"]
            except ApiError:
                tail = ""
        process_keys.append((process["pid"], process.get("goal") or "", size // 65536))
        processes.append({"goal": process.get("goal"), "log": "\n".join(tail.splitlines()[-40:])})
    blocks["codex"], fingerprints["codex"] = processes, digest(sorted(process_keys))
    found = {}
    for pattern in cfg.get("report_globs", []):
        for path in glob.iglob(str(Path(pattern).expanduser())):
            try:
                value = safe_read(cfg, path, 6000)
                found[value["path"]] = value
            except ApiError:
                continue
    reports = sorted(found.values(), key=lambda value: value["mtime"], reverse=True)
    blocks["reports"] = [{"name": Path(value["path"]).name, "text": value["text"][:1500]}
                         for value in reports[:5]]
    fingerprints["reports"] = digest(sorted((value["path"], value["mtime"]) for value in reports))
    return fingerprints, blocks
