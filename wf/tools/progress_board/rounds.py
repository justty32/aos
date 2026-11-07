"""Infer event rounds and collect complete round history with safe mounted reports."""

from pathlib import Path
import re
from urllib.parse import quote

ROUND_PATTERN = re.compile(r"第[一二三四五六七八九十0-9]+輪|批\s*[0-9]+[a-z]?")


def tag_events(events):
    """Assign effective rounds to chronological events within one line."""
    previous = "未分輪"
    result = []
    for event in events:
        explicit = event.get("round")
        match = ROUND_PATTERN.search(event["text"])
        if isinstance(explicit, str) and explicit.strip():
            previous = explicit
        elif match:
            previous = match[0]
            if previous.startswith("批"):
                previous = "批 " + previous[1:].strip()
        result.append(dict(event, round=previous))
    return result


def report_urls(line, name, cfg):
    """Expose a mapped report only when its real file stays inside a mount."""
    value = line.get("round_pages", {}).get(name)
    if not isinstance(value, str) or "\\" in value:
        return {}
    parts = value.split("/")
    if len(parts) < 2 or any(part in ("", ".", "..") for part in parts):
        return {}
    for site in cfg.get("sites", []):
        if site.get("mount") != parts[0]:
            continue
        try:
            root = Path(site["dir"]).expanduser().resolve()
            target = root.joinpath(*parts[1:]).resolve()
            target.relative_to(root)
            if target.suffix.lower() != ".html" or not target.is_file():
                return {}
        except (KeyError, OSError, ValueError, TypeError):
            return {}
        return {"report_url": quote(value, safe="/"),
                "report_file_url": "../" + quote(root.name + "/" + "/".join(parts[1:]), safe="/")}
    return {}


def rounds_state(line, events, cfg, answers):
    """Group all chronological events and use the latest saved answer per ask."""
    answered = {answer["id"] for answer in answers}
    grouped = {}
    for event in events:
        name = event["round"]
        if name not in grouped:
            grouped[name] = {"name": name, "first_ts": event["ts"], "counts": {},
                             "events": [], "events_count": 0, "decisions_count": 0,
                             "asks_open": 0, **report_urls(line, name, cfg)}
        item = grouped[name]
        item.update(last_ts=event["ts"], status=event["status"],
                    blocked=event["status"] == "blocked")
        item["counts"][event["status"]] = item["counts"].get(event["status"], 0) + 1
        item["events"].append(event)
        item["events_count"] += 1
        item["decisions_count"] += event["status"] == "decision"
        item["asks_open"] += event["status"] == "ask" and event["id"] not in answered
    return list(grouped.values())
