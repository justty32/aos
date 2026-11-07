"""Gather bounded evidence and change fingerprints for everyday progress explanations."""

import datetime as dt
import glob
import json
from pathlib import Path

from answers import asks_state, read_answers, read_asks
from codex_api import codex_processes
from collect import handoff_path, parse_ts, read_jsonl
from safe_files import ApiError, safe_read


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
        return {"mtime": result["mtime"], "size": result["size"]}, result["text"][:limit]
    except ApiError:
        return None, ""


def main_input(board, cfg, context=None):
    from eli5 import fingerprint_main
    from details_api import line_commits
    context = context if context is not None else {}
    if "events" not in context:
        context["events"] = events_by_line(board)
    grouped = context["events"]
    raw = read_asks(board)
    asks = asks_state(raw, read_answers(board), dt.datetime.now().astimezone())
    opened = [{key: ask[key] for key in ("id", "line", "text", "options", "recommend")}
              for ask in asks if ask["answer"] is None and not ask.get("eli5")]
    blocks, sources = {}, {}
    latest = text(Path(board) / "summary/latest.md")
    blocks["summary"], sources["summary"] = latest, latest
    cache = context.setdefault("git", {})
    for line in cfg.get("lines", []):
        metadata, handoff = _handoff(cfg, line, 3000)
        commits = line_commits(cfg, line, cache)
        events = grouped.get(line["id"], [])[-10:]
        key = "lines." + line["id"]
        blocks[key] = {"title": line.get("title", line["id"]), "events": events,
                       "handoff": handoff, "newest_commit": commits[:1]}
        sources[key] = [events, metadata["mtime"] if metadata else None,
                        commits[0]["hash"] if commits else None]
    for ask in opened:
        key = "asks." + ask["id"]
        blocks[key] = ask
        sources[key] = {name: ask[name] for name in ("text", "options", "recommend")}
    return fingerprint_main(sources), blocks


def detail_input(board, cfg, context=None):
    from eli5 import fingerprint_detail
    grouped = (context or {}).get("events")
    if grouped is None:
        grouped = events_by_line(board)
    blocks, sources = {}, {}
    for line in cfg.get("lines", []):
        events = grouped.get(line["id"], [])
        key = f"lines.{line['id']}.timeline"
        blocks[key] = {"title": line.get("title", line["id"]), "events": events[-30:]}
        sources[key] = events[-30:]
        key = f"lines.{line['id']}.handoff"
        metadata, content = _handoff(cfg, line, 6000)
        if metadata is None:
            continue
        blocks[key] = {"title": line.get("title", line["id"]), "handoff": content}
        sources[key] = metadata
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
        process_keys.append((process["pid"], process.get("goal") or "", size // 16384))
        processes.append({"goal": process.get("goal"), "log": "\n".join(tail.splitlines()[-40:])})
    blocks["codex"], sources["codex"] = processes, sorted(process_keys)
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
    sources["reports"] = sorted((value["path"], value["mtime"]) for value in reports)
    return fingerprint_detail(sources), blocks
