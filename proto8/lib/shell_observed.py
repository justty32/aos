"""Reserve a writable shell ledger before execution and record the completed command."""
import json
import os
import time

import observed
import tool_io


def prepare():
    """Open the ledger before any command side effect; no stack means no ledger."""
    stack = os.environ.get("AOS_STACK")
    if not stack:
        return None
    try:
        return observed.prepare_strict(stack)
    except (OSError, ValueError, TypeError) as error:
        tool_io.die("LogFailed", "cannot prepare command log: %s" % error)


def finish(stream, command, timeout_s, returncode, started, out_bytes):
    """Append the actual inner result to the reserved file, then close it."""
    if stream is None:
        return
    record = {"kind": "cmd", "command": command, "timeout_s": timeout_s,
              "exit": 128 - returncode if returncode < 0 else returncode,
              "elapsed_ms": (time.monotonic() - started) * 1000,
              "out_bytes": out_bytes}
    try:
        with stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
            stream.flush()
    except (OSError, ValueError, TypeError) as error:
        tool_io.die("LogFailed", "cannot write command log: %s" % error)
