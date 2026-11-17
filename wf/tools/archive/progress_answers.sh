#!/bin/sh
# Read progress-board answers and unanswered questions with optional time and line filters.
exec python3 - "$@" <<'PY'
import datetime as dt
import json
import os
from pathlib import Path
import re
import sys

USAGE = "progress_answers.sh [--since TIME] [--line LINE] [--open] [--json]"


def fail(code, reason):
    print(f"progress_answers: error: {code} {reason} (usage: {USAGE})", file=sys.stderr)
    sys.exit(1)


def timestamp(value):
    try:
        return dt.datetime.fromisoformat(value).astimezone()
    except (ValueError, TypeError, OverflowError):
        return None


def since_time(value):
    try:
        if re.fullmatch(r"\d{2}:\d{2}", value):
            return dt.datetime.combine(dt.date.today(), dt.time.fromisoformat(value)).astimezone()
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:[Tt ].+)?", value):
            raise ValueError
        result = timestamp(value)
        if result is None:
            raise ValueError
        return result
    except ValueError:
        fail("TimeBad", "--since requires an ISO date, datetime or HH:MM")


def records(path):
    try:
        with path.open(encoding="utf-8", errors="replace") as source:
            for row in source:
                try:
                    record = json.loads(row)
                    if (isinstance(record, dict) and isinstance(record.get("id"), str)
                            and isinstance(record.get("line"), str) and timestamp(record.get("ts"))):
                        yield record
                except (ValueError, TypeError):
                    continue
    except OSError:
        return


args = sys.argv[1:]
since, line, opened, as_json = None, None, False, False
while args:
    flag = args.pop(0)
    if flag in ("--help", "-h"):
        print(f"Usage: {USAGE}\nRead all answers, oldest first. --open lists unanswered questions.\n"
              "--since accepts an ISO date, datetime or today's local HH:MM.\n"
              "--line filters by line; --json prints one JSON object per line.")
        sys.exit(0)
    if flag in ("--since", "--line"):
        if not args or args[0].startswith("--"):
            fail("ArgumentsBad", f"{flag} requires a value")
        value = args.pop(0)
        if flag == "--since":
            since = since_time(value)
        else:
            line = value
    elif flag == "--open":
        opened = True
    elif flag == "--json":
        as_json = True
    elif flag.startswith("-"):
        fail("FlagUnknown", flag)
    else:
        fail("ArgumentsBad", f"unexpected argument {flag}")

board = Path(os.environ.get("AOS_PROGRESS_DIR", "~/Desktop/aos-進度")).expanduser()
asks = {record["id"]: record for record in records(board / "data/progress.jsonl")
        if record.get("status") == "ask" and isinstance(record.get("text"), str)}
answers = [record for record in records(board / "data/answers.jsonl")
           if (record.get("choice") is None or isinstance(record.get("choice"), str))
           and isinstance(record.get("comment", ""), str)]
latest = {record["id"]: record for record in answers}
if opened:
    selected = [ask for key, ask in asks.items() if key not in latest]
else:
    selected = []
    for answer in answers:
        ask = asks.get(answer["id"], {})
        selected.append(dict(answer, question=ask.get("text", ""),
                             options=ask.get("options", []), recommend=ask.get("recommend")))
selected = sorted((record for record in selected
                   if (line is None or record["line"] == line)
                   and (since is None or timestamp(record["ts"]) >= since)),
                  key=lambda record: timestamp(record["ts"]))
if selected and as_json:
    for record in selected:
        print(json.dumps(record, ensure_ascii=False))
elif selected:
    for record in selected:
        print(f"{record['ts']}  {record['line']}  {record['id']}")
        print(f"  question: {record.get('text' if opened else 'question', '')}")
        options = record.get("options", [])
        options = [option for option in options if isinstance(option, dict)] if isinstance(options, list) else []
        if opened:
            keys = " | ".join(str(option.get("key", "")) for option in options)
            recommend = record.get("recommend")
            suffix = f" (recommend {recommend})" if recommend else ""
            print(f"  options: {keys}{suffix}")
        else:
            choice = record.get("choice")
            label = next((option.get("text", "") for option in options if option.get("key") == choice), "")
            print(f"  choice: {choice} {label}".rstrip() if choice is not None else "  choice: none")
            print(f"  comment: {record.get('comment') or '-'}")
PY
