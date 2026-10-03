"""rename 的 keep 任務（node b）：掛 a 的 inbox（mnt/a_in），每收到一次 tock 寄一封，記成敗到 progress.json。"""
import json
import os
import time

T = os.environ["AOS7_TASK"]


def rnd(path):
    try:
        with open(path) as f:
            return json.load(f).get("round", 0)
    except (OSError, ValueError):
        return 0


def put(path, obj):
    tmp = "%s.tmp.%d" % (path, os.getpid())
    with open(tmp, "w") as f:
        json.dump(obj, f)
    os.replace(tmp, path)


st = {"ok": 0, "err": 0, "last_err": None, "round": 0}
while True:
    r = rnd(os.path.join(T, "tock.json"))
    if r > st["round"]:
        st["round"] = r
        try:
            put(os.path.join(T, "mnt", "a_in", "b-%d.json" % r), {"from": "b", "round": r})
            st["ok"] += 1
        except OSError as e:
            st["err"] += 1
            st["last_err"] = str(e)
        put(os.path.join(T, "progress.json"), st)
    time.sleep(0.02)
