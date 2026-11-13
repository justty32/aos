# 問腦的逐封帳 ledger.jsonl：只留成本與時間，不存請求內容。
import json
import os
import time

import tool_io


def append(stack, name, proc, reply):
    """追加一列；寫不了只提醒，不影響回信與收信。"""
    path = os.path.join(stack, "ledger.jsonl")
    proc = proc if isinstance(proc, dict) else {}
    finished = time.time()
    mounted = proc.get("mounted_at")
    elapsed = None
    if isinstance(mounted, (int, float)) and not isinstance(mounted, bool):
        elapsed = max(0, int((finished - mounted) * 1000.0))
    entry = {"id": name, "endpoint": proc.get("endpoint"), "sender": proc.get("sender"),
             "model": reply.get("model"), "seen_at": proc.get("seen_at"), "mounted_at": mounted,
             "finished_at": finished, "elapsed_ms": elapsed, "usage": reply.get("usage"),
             "code": reply["error"]["code"] if "error" in reply else None,
             "child": reply.get("child"), "switched": proc.get("switched", False)}
    try:
        line = json.dumps(entry, ensure_ascii=False) + "\n"
        with open(path, "a", encoding="utf-8") as stream:
            stream.write(line)
    except (OSError, ValueError, TypeError) as error:
        tool_io.warn("cannot append ledger: %s (%s)" % (path, error))
