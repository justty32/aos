"""llmops 的 relay：每收到一次 tock，往掛載點 mnt/out/ 寫一封信；成敗記到 node 的 relay.log（一行一個 JSON）。"""
import json
import os
import time

task = os.environ["AOS7_TASK"]
tid = os.environ["AOS7_TID"]
last = None
while True:
    try:
        with open(os.path.join(task, "tock.json")) as f:
            r = json.load(f).get("round")
    except (OSError, ValueError):
        r = None
    if r is not None and r != last:
        last = r
        rec = {"round": r, "tid": tid}
        try:
            with open(os.path.join(task, "mnt", "out", "letter-r%d-%s.json" % (r, tid)), "w") as f:
                json.dump({"from": "hub", "round": r}, f)
            rec["ok"] = True
        except OSError as e:
            rec["ok"], rec["err"] = False, str(e)
        with open("relay.log", "a") as f:
            f.write(json.dumps(rec) + "\n")
    time.sleep(0.05)
