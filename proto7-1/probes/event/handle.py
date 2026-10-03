"""處理 `<node>/inbox/*.json` 的事件：搬到 inbox/done/，記一行到 `<node>/handled.jsonl`。

    python3 handle.py once    處理一次就結束（each 任務：每回合起一個）
    python3 handle.py watch   常駐，自己每 10 ms 看一次 inbox（不靠 tock）
    python3 handle.py tock    常駐，每收到一個 tock 才看一次 inbox（靠 tock）

事件檔＝{"n", "t_drop"（丟檔時的 time.time()）}；handled.jsonl 一行＝{"n", "t_drop", "t_done", "by", "round", "how"}。
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "lib"))
import aos7_fs as fs  # noqa: E402

how = sys.argv[1]
node, task, tid = os.environ["AOS7_NODE"], os.environ["AOS7_TASK"], os.environ["AOS7_TID"]
inbox = os.path.join(node, "inbox")
done = os.path.join(inbox, "done")
os.makedirs(done, exist_ok=True)


def node_round():
    return (fs.read_json(os.path.join(node, ".aos", "round.json"), {}) or {}).get("round")


def drain():
    try:
        names = sorted(f for f in os.listdir(inbox) if f.endswith(".json"))
    except OSError:
        return
    for f in names:
        evt = fs.read_json(os.path.join(inbox, f))
        if not isinstance(evt, dict):
            continue
        os.replace(os.path.join(inbox, f), os.path.join(done, f))
        fs.append_jsonl(os.path.join(node, "handled.jsonl"),
                        {"n": evt.get("n"), "t_drop": evt.get("t_drop"), "t_done": time.time(),
                         "by": tid, "round": node_round(), "how": how})


if how == "once":
    drain()
elif how == "watch":
    while True:
        drain()
        time.sleep(0.01)
else:
    last = (fs.read_json(os.path.join(task, "birth.json")) or {}).get("round", 0) - 1
    while True:
        last = fs.wait_tock(task, last, poll=0.005)
        drain()
