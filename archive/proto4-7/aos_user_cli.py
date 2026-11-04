#!/usr/bin/env python3
"""人和 proto4-7 agent 往來的 CLI。"""

import argparse
import json
import os
from pathlib import Path
import sys
import threading
import time

from common import atomic_json
from mailbox import send_user_mail, unread_count
from state_machine import AgentError, load_agent, load_state


HERE = Path(__file__).resolve().parent


ECHO_TOOL = {
    "description": "原樣回你給的東西",
    "parameters": {"type": "object", "properties": {"text": {"type": "string", "description": "要回的東西"}},
                   "required": ["text"]},
}
SH_TOOL = {
    "description": "在 agent 資料夾執行一句 shell 指令",
    "parameters": {
        "type": "object", "properties": {"cmd": {"type": "string"}},
        "required": ["cmd"], "additionalProperties": False,
    },
}
ECHO_RUN = """#!/bin/sh
cat
"""
SH_RUN = """#!/bin/sh
set -eu
AGENT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
CMD="$(python3 -c 'import json,sys; x=json.load(sys.stdin); assert isinstance(x.get("cmd"),str); print(x["cmd"])')"
cd "$AGENT_DIR"
timeout 60 sh -c "$CMD"
"""


def _write_executable(path, content):
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.chmod(tmp, 0o755)
    os.replace(tmp, path)


def create_agent(agent_dir, name, system, kernel):
    agent_dir = Path(agent_dir).resolve()
    if agent_dir.exists() and any(agent_dir.iterdir()):
        raise ValueError(f"資料夾不是空的：{agent_dir}")
    agent_dir.mkdir(parents=True, exist_ok=True)
    for folder in (agent_dir / "inbox" / "user" / "read", agent_dir / "outbox",
                   agent_dir / "tools" / "echo", agent_dir / "tools" / "sh"):
        folder.mkdir(parents=True, exist_ok=True)
    atomic_json(agent_dir / "agent.json", {
        "name": name, "system": system, "K": str(Path(kernel).resolve()),
        "max_steps_per_question": 60, "tool_output_limit": 8000,
    })
    atomic_json(agent_dir / "messages.json", [])
    atomic_json(agent_dir / "tools" / "echo" / "tool.json", ECHO_TOOL)
    atomic_json(agent_dir / "tools" / "sh" / "tool.json", SH_TOOL)
    _write_executable(agent_dir / "tools" / "echo" / "run", ECHO_RUN)
    _write_executable(agent_dir / "tools" / "sh" / "run", SH_RUN)
    atomic_json(agent_dir / "inst.json", {
        "argv": [str(HERE / "aos-agent"), "."], "cwd": str(agent_dir),
        "stderr": "err.txt",
    })
    print(f'aos-kernel add {Path(kernel).resolve()} {agent_dir / "inst.json"} --name {name}')
    print(f'aos-user {agent_dir} say "…"')
    print(f"aos-user {agent_dir} listen")


def say(agent_dir, words):
    content = words if words is not None else sys.stdin.read()
    if not content:
        raise ValueError("沒有訊息")
    print(send_user_mail(agent_dir, content))


def _outbox_files(agent_dir):
    return sorted((Path(agent_dir) / "outbox").glob("*.json"))


def _listen_seen_path(agent_dir):
    return Path(agent_dir) / ".listen-seen"


def _load_listen_seen(agent_dir):
    try:
        return int(_listen_seen_path(agent_dir).read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return 0


def _save_listen_seen(agent_dir, paths):
    numbers = [int(path.stem) for path in paths if path.stem.isdigit()]
    if not numbers:
        return
    path = _listen_seen_path(agent_dir)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(str(max(numbers)) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def listen(agent_dir, new=False, once=False, label=None):
    current = _outbox_files(agent_dir)
    seen = set(current)
    if not new and once:
        last = _load_listen_seen(agent_dir)
        fresh = [path for path in current if path.stem.isdigit() and int(path.stem) > last]
        for path in fresh:
            _show_outbox(path, label)
        if fresh:
            _save_listen_seen(agent_dir, fresh)
        else:
            print("（沒有新回話）")
        return
    if not new:
        for path in current:
            _show_outbox(path, label)
        _save_listen_seen(agent_dir, current)
    while True:
        fresh = [path for path in _outbox_files(agent_dir) if path not in seen]
        for path in fresh:
            seen.add(path)
            _show_outbox(path, label)
        _save_listen_seen(agent_dir, fresh)
        if once and fresh:
            return
        time.sleep(0.2)


def _show_outbox(path, label):
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        content = payload.get("content", "")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, AttributeError):
        content = "（這則 outbox 讀不懂）"
    if label is None:
        print(f"--- {path.stem} ---")
        print(content, flush=True)
    else:
        print(f"\n{label}{content}", flush=True)


def status(agent_dir):
    state = load_state(agent_dir)
    request = state.get("request") or "-"
    print(
        f"state={state['state']} question={state['question']} step={state['step']} "
        f"request={request} checks={state['checks']} errors={state['errors']} "
        f"stuck={'yes' if state['stuck'] else 'no'} unread={unread_count(agent_dir)} "
        f"last_error={state.get('last_error') or '-'}"
    )


def talk(agent_dir):
    config = load_agent(agent_dir)
    watcher = threading.Thread(
        target=listen, args=(agent_dir,), kwargs={"new": True, "label": f"{config['name']}> "},
        daemon=True,
    )
    watcher.start()
    while True:
        try:
            words = input("你> ")
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if words:
            send_user_mail(agent_dir, words)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="aos-user")
    parser.add_argument("agent")
    subs = parser.add_subparsers(dest="command", required=True)
    say_p = subs.add_parser("say")
    say_p.add_argument("words", nargs="?")
    listen_p = subs.add_parser("listen")
    listen_p.add_argument("--new", action="store_true")
    listen_p.add_argument("--once", action="store_true")
    subs.add_parser("talk")
    subs.add_parser("status")
    new_p = subs.add_parser("new")
    new_p.add_argument("--name", required=True)
    new_p.add_argument("--system", required=True)
    new_p.add_argument("--K", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "new":
            create_agent(args.agent, args.name, args.system, args.K)
        elif args.command == "say":
            say(args.agent, args.words)
        elif args.command == "listen":
            listen(args.agent, args.new, args.once)
        elif args.command == "talk":
            talk(args.agent)
        else:
            status(args.agent)
        return 0
    except (AgentError, OSError, ValueError) as exc:
        print(f"aos-user: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
