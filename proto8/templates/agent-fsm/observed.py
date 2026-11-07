# observed.py - Append best-effort agent observations without changing cell results.
import json
import os

import aos_flags


def append_observed(stack, record):
    try:
        with open(os.path.join(stack, "observed.jsonl"), "a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as error:
        aos_flags.warn("agent-fsm", "cannot append to observed.jsonl: %s" % error)
