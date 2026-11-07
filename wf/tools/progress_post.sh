#!/bin/sh
# Append one validated progress event to the board using a locked JSON line.
exec python3 - "$@" <<'PY'
import datetime
import fcntl
import json
import os
import re
import secrets
import sys
from pathlib import Path

USAGE = "progress_post.sh <line> <status> '<text>' [link-or-path ...] [--option 'A: text'] [--recommend A] [--eli5 '<plain text>']"
STATUSES = "start|progress|done|blocked|decision|handoff|ask"


def fail(code, reason):
    print(f"progress_post: error: {code} {reason} (usage: {USAGE})", file=sys.stderr)
    sys.exit(1)


args = sys.argv[1:]
if args and args[0] in ("--help", "-h"):
    print(f"Usage: {USAGE}\nStatuses: {STATUSES}\n"
          "For ask: repeat --option KEY:TEXT; --recommend KEY selects a suggested option; --eli5 adds a plain-language explanation.\n"
          "Example: progress_post.sh progress-board ask 'Which approach?' "
          "--option 'A: Keep it simple' --option 'B: Add detail' --recommend A "
          "--eli5 'Choose a short answer or a longer explanation.'")
    sys.exit(0)
if args and args[0].startswith("-"):
    fail("FlagUnknown", args[0])
if len(args) < 3:
    fail("ArgumentsBad", "at least three arguments are required")
line, status, text, *rest = args
links, options, recommend, eli5 = [], [], None, None
while rest:
    item = rest.pop(0)
    if item in ("--option", "--recommend", "--eli5"):
        if status != "ask":
            fail("FlagBad", f"{item} is only for ask")
        if not rest or rest[0].startswith("--"):
            fail("ArgumentsBad", f"{item} requires a value")
        value = rest.pop(0)
        if item == "--option":
            parts = re.split("[:：]", value, maxsplit=1)
            key = parts[0]
            if (len(parts) != 2 or not re.fullmatch(r"[A-Za-z0-9]{1,8}", key)
                    or any(option["key"] == key for option in options)):
                fail("OptionBad", "options require unique alphanumeric keys of 1 to 8 characters followed by a colon")
            options.append({"key": key, "text": value})
        elif item == "--recommend":
            recommend = value
        else:
            eli5 = value
    elif item.startswith("--"):
        fail("FlagUnknown", item)
    else:
        links.append(item)
if recommend is not None and recommend not in {option["key"] for option in options}:
    fail("RecommendBad", "recommended key must name an option")
if not re.fullmatch(r"[A-Za-z0-9._-]+", line):
    fail("LineBad", "line must be non-empty and contain only A-Z, a-z, 0-9, dot, underscore or hyphen")
if status not in STATUSES.split("|"):
    fail("StatusBad", f"{status} not one of {STATUSES}")
if not text:
    fail("TextBad", "text must be non-empty")
event = {"ts": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
         "line": line, "status": status, "text": text, "links": links}
if status == "ask":
    event.update(id=f"{line}-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(2)}",
                 options=options, recommend=recommend, eli5=eli5)
try:
    target = Path(os.environ.get("AOS_PROGRESS_DIR", "~/Desktop/aos-進度")).expanduser()
    (target / "data").mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8")
    with (target / "data/progress.jsonl").open("ab", buffering=0) as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        stream.write(payload)
except OSError as exc:
    fail("WriteFailed", str(exc).replace("\n", " "))
print(f"progress_post: posted {line} {status}" + (f" id={event['id']}" if status == "ask" else ""))
PY
