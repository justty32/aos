#!/bin/sh
# Append one validated progress event to the board using a locked JSON line.
exec python3 - "$@" <<'PY'
import datetime
import fcntl
import json
import os
import re
import sys
from pathlib import Path

USAGE = "progress_post.sh <line> <status> '<text>' [link-or-path ...]"
STATUSES = "start|progress|done|blocked|decision|handoff"


def fail(code, reason):
    print(f"progress_post: error: {code} {reason} (usage: {USAGE})", file=sys.stderr)
    sys.exit(1)


args = sys.argv[1:]
if args and args[0] in ("--help", "-h"):
    print(f"Usage: {USAGE}\nStatuses: {STATUSES}\n"
          "Example: progress_post.sh progress-board progress 'Built the snapshot' README.md")
    sys.exit(0)
if args and args[0].startswith("-"):
    fail("FlagUnknown", args[0])
if len(args) < 3:
    fail("ArgumentsBad", "at least three arguments are required")
line, status, text, *links = args
if not re.fullmatch(r"[A-Za-z0-9._-]+", line):
    fail("LineBad", "line must be non-empty and contain only A-Z, a-z, 0-9, dot, underscore or hyphen")
if status not in STATUSES.split("|"):
    fail("StatusBad", f"{status} not one of {STATUSES}")
if not text:
    fail("TextBad", "text must be non-empty")
event = {"ts": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
         "line": line, "status": status, "text": text, "links": links}
try:
    target = Path(os.environ.get("AOS_PROGRESS_DIR", "~/Desktop/aos-進度")).expanduser()
    (target / "data").mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8")
    with (target / "data/progress.jsonl").open("ab", buffering=0) as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        stream.write(payload)
except OSError as exc:
    fail("WriteFailed", str(exc).replace("\n", " "))
print(f"progress_post: posted {line} {status}")
PY
