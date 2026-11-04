#!/usr/bin/env python3
"""user inbox 與 agent outbox。"""

import json
import os
from pathlib import Path

from common import atomic_json, now_iso, read_json, timestamp_name


def _next_outbox_n(agent_dir, state):
    highest = int(state.get("outbox_n", 0))
    for path in (agent_dir / "outbox").glob("*.json"):
        try:
            highest = max(highest, int(path.stem))
        except ValueError:
            pass
    return highest + 1


def write_outbox(agent_dir, state, content):
    number = _next_outbox_n(agent_dir, state)
    state["outbox_n"] = number
    atomic_json(agent_dir / "outbox" / f"{number:04d}.json", {
        "time": now_iso(), "content": str(content),
    })
    return number


def _move_read(path, read_dir):
    read_dir.mkdir(parents=True, exist_ok=True)
    target = read_dir / path.name
    if target.exists():
        target = read_dir / f"{path.stem}-{timestamp_name()}{path.suffix}"
    os.replace(path, target)


def collect_user_mail(agent_dir, state):
    """搬走最舊的一封信，回傳可接進 messages 的 user 訊息。"""
    inbox = agent_dir / "inbox" / "user"
    read_dir = inbox / "read"
    messages = []
    paths = sorted(inbox.glob("*.json"))[:1]
    for path in paths:
        try:
            payload = read_json(path)
            letters = payload if isinstance(payload, list) else [payload]
            if not letters or not all(isinstance(x, dict) and "content" in x for x in letters):
                raise ValueError("信件格式不對")
            for letter in letters:
                content = letter["content"]
                if not isinstance(content, str):
                    content = json.dumps(content, ensure_ascii=False)
                messages.append({"role": "user", "content": f"[user] {content}"})
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError):
            write_outbox(agent_dir, state, "有一封信讀不懂")
        finally:
            if path.exists():
                _move_read(path, read_dir)
    return messages, bool(paths)


def send_user_mail(agent_dir, content):
    inbox = Path(agent_dir) / "inbox" / "user"
    inbox.mkdir(parents=True, exist_ok=True)
    while True:
        path = inbox / f"{timestamp_name()}.json"
        if not path.exists():
            break
    atomic_json(path, {"from": "user", "time": now_iso(), "content": content})
    return path


def unread_count(agent_dir):
    return sum(1 for _ in (Path(agent_dir) / "inbox" / "user").glob("*.json"))
