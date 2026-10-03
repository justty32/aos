"""llmkernel 的成員任務（keep）：每收到一次 tock，`$AOS7_TASK/usage.json` 的 tokens 加 RATE，並在 `<node>/work.jsonl` 記一行。

    python3 worker.py RATE
pause 的 node 收不到 tock，所以用量只在「輪到它」時長。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))
import aos7_fs as fs  # noqa: E402

rate = int(sys.argv[1])
e = fs.task_env()
up = os.path.join(e["task"], "usage.json")
tokens = (fs.read_json(up, {}) or {}).get("tokens", 0)
fs.write_json(up, {"tokens": tokens, "calls": 0})
last = 0
while True:
    r = fs.wait_tock(e["task"], last)
    last = r
    tokens += rate
    fs.write_json(up, {"tokens": tokens, "calls": last})
    fs.append_jsonl(os.path.join(e["node"], "work.jsonl"), {"round": r, "at": fs.now(), "tokens": tokens})
