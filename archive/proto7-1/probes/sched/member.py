"""sched 探針的成員任務（mode each）：每回合做一點事，記一行到 <node>/work.jsonl。

<node>/member.json：{"work_ms": 20, "queue": false}
queue=true：從 <node>/queue/ 拿一個工作（檔名排序第一個，拿了就刪）；沒工作就記 idle、馬上結束。
"""
import json
import os
import time

node = os.environ["AOS7_NODE"]
task = os.environ["AOS7_TASK"]
t0 = time.time()
try:
    with open(os.path.join(node, "member.json")) as f:
        cfg = json.load(f)
except (OSError, ValueError):
    cfg = {}
try:
    with open(os.path.join(task, "birth.json")) as f:
        rnd = json.load(f).get("round")
except (OSError, ValueError):
    rnd = None
job = None
if cfg.get("queue"):
    q = os.path.join(node, "queue")
    try:
        names = sorted(n for n in os.listdir(q) if n.endswith(".json"))
    except OSError:
        names = []
    for n in names:
        try:
            os.remove(os.path.join(q, n))     # 拿到就是我的（刪成功的那個才算）
            job = n
            break
        except OSError:
            continue
if not cfg.get("queue") or job:
    time.sleep(cfg.get("work_ms", 20) / 1000.0)
line = {"tid": os.environ["AOS7_TID"], "round": rnd, "t0": t0, "t1": time.time(), "job": job,
        "idle": bool(cfg.get("queue")) and job is None}
with open(os.path.join(node, "work.jsonl"), "a") as f:
    f.write(json.dumps(line) + "\n")
