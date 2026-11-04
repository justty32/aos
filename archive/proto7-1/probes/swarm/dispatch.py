"""常駐的調度任務：每收到一個 tock，若上一批全結束，就寫下一批 N 個 `spawn/*.json`（下個 tick 起）。

    python3 dispatch.py <N> <批數> [每檔間隔秒]
每檔間隔：寫每個 spawn 之間 sleep（模擬慢一點的調度，看一批會不會被下個 tick 拆開）。
每批記一行到 `$AOS7_TASK/batches.jsonl`：{"batch","written_round","n","done_seen_round","failed","waited_tocks"}。
「上一批全結束」沒有訊號，只能自己掃任務資料夾（birth.json 的 name＝dmap、argv 帶批名）。
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "lib"))
import aos7_fs as fs  # noqa: E402
import aos7_task  # noqa: E402

n, nbatch = int(sys.argv[1]), int(sys.argv[2])
gap = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
node, task = os.environ["AOS7_NODE"], os.environ["AOS7_TASK"]
here = os.path.dirname(os.path.abspath(__file__))
cur = None          # {"batch", "written_round", "tocks"}
done = 0
last = (fs.read_json(os.path.join(task, "birth.json")) or {}).get("round", 0) - 1


def batch_tids(b):
    out = []
    for t in aos7_task.list_tasks(node):
        bi = fs.read_json(os.path.join(aos7_task.task_dir(node, t), "birth.json"), {}) or {}
        if bi.get("name") == "dmap" and (bi.get("argv") or [None])[-1] == b:
            out.append(t)
    return out


def write_batch(rnd):
    b = "b%d" % (done + 1)
    for i in range(n):
        aos7_task.write_spawn(node, "%s-%03d" % (b, i),
                              {"name": "dmap", "argv": [sys.executable, os.path.join(here, "map.py"), str(i), b]})
        if gap:
            time.sleep(gap)
    return {"batch": b, "written_round": rnd, "written_at": time.time(), "tocks": 0}


while done < nbatch:
    rnd = fs.wait_tock(task, last, poll=0.01, timeout=20)
    if rnd is None:
        break
    last = rnd
    if cur is None:
        cur = write_batch(rnd)
        continue
    cur["tocks"] += 1
    tids = batch_tids(cur["batch"])
    states = [aos7_task.task_state(aos7_task.task_dir(node, t)) for t in tids]
    if len(tids) < n or any(aos7_task.is_live(s) for s in states):
        continue
    failed = []
    for t in tids:
        c = (fs.read_json(os.path.join(aos7_task.task_dir(node, t), "exit.json"), {}) or {}).get("code")
        if c != 0:
            failed.append([t, c])
    rounds_of = sorted({(fs.read_json(os.path.join(aos7_task.task_dir(node, t), "birth.json"), {}) or {}).get("round")
                        for t in tids})
    fs.append_jsonl(os.path.join(task, "batches.jsonl"),
                    {"batch": cur["batch"], "written_round": cur["written_round"], "started_rounds": rounds_of,
                     "n": len(tids), "done_seen_round": rnd, "waited_tocks": cur["tocks"],
                     "failed": failed, "write_to_done_ms": round((time.time() - cur["written_at"]) * 1000)})
    done += 1
    cur = write_batch(rnd) if done < nbatch else None
