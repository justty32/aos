#!/usr/bin/env python3
"""aos-agent CLI。"""

import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "proto4-6"))
import aos_py  # noqa: E402

from agent_tools import ToolConfigError  # noqa: E402
from common import atomic_json  # noqa: E402
from state_machine import AgentError, DEFAULT_STATE, load_state, step  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(prog="aos-agent")
    parser.add_argument("agent")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--status", action="store_true")
    group.add_argument("--reset", action="store_true")
    args = parser.parse_args(argv)
    agent_dir = Path(args.agent).resolve()
    if args.reset:
        try:
            previous = load_state(agent_dir)
            reset_state = dict(DEFAULT_STATE)
            reset_state["epoch"] = previous["epoch"] + 1
            atomic_json(agent_dir / "state.json", reset_state)
            return 0
        except (AgentError, OSError) as exc:
            print(f"aos-agent: {exc}", file=sys.stderr)
            return 1
    if args.status:
        try:
            print(json.dumps(load_state(agent_dir), ensure_ascii=False, separators=(",", ":")))
            return 0
        except AgentError as exc:
            print(f"aos-agent: {exc}", file=sys.stderr)
            return 1
    try:
        return step(agent_dir, aos_py)
    except (AgentError, ToolConfigError, OSError) as exc:
        print(f"aos-agent: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
