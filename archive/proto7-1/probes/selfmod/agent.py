"""會改自己任務表的假 agent：讀自己 node 的 orders/*.json，照單改 tasks.json／timeline.json／.aos 裡的東西，結果寫 results/。"""
import time
from common import NODE, TASKS, edit_tasks, fs, os

ORDERS, RESULTS = os.path.join(NODE, "orders"), os.path.join(NODE, "results")
TL = os.path.join(NODE, ".aos", "timeline.json")


def op_set_interval(o):
    fs.write_json(TL, {"interval_ms": o["ms"]})


def op_write_timeline_raw(o):
    with open(TL, "w") as f:
        f.write(o["text"])


def op_bounce_timeline(o):
    """拿掉 timeline.json 一下再寫回（讓 daemon 看到 node 消失又出現）。"""
    os.rename(TL, TL + ".off")
    time.sleep(o.get("gap_ms", 150) / 1000.0)
    fs.write_json(TL, o["timeline"])
    os.remove(TL + ".off")


def op_add_task(o):
    edit_tasks(lambda ts: ts + [o["item"]])


def op_remove_task(o):
    edit_tasks(lambda ts: [t for t in ts if t.get("name") != o.get("name")])


def op_set_field(o):
    def f(ts):
        for t in ts:
            if t.get("name") == o["name"]:
                t[o["key"]] = o["value"]
        return ts
    edit_tasks(f)


def op_half_write(o):
    """不原子地寫 tasks.json：先寫一半、停 gap_ms、再寫完。"""
    text = open(TASKS).read()
    with open(TASKS, "w") as f:
        f.write(text[:len(text) // 2])
        f.flush()
        time.sleep(o["gap_ms"] / 1000.0)
        f.write(text[len(text) // 2:])


def op_forge_round(o):
    p = os.path.join(NODE, ".aos", "round.json")
    r = fs.read_json(p, {}) or {}
    r["round"] = o["round"]
    fs.write_json(p, r)


def op_forge_exit(o):
    fs.write_json(os.path.join(NODE, ".aos", "tasks", o["tid"], "exit.json"), {"code": 0, "forged": True})


def op_task_ctl(o):
    fs.write_json(os.path.join(NODE, ".aos", "tasks", o["tid"], "ctl.json"), {"op": o["ctl"], "by": "agent"})


OPS = {k[3:]: v for k, v in dict(globals()).items() if k.startswith("op_")}

while True:
    try:
        names = sorted(n for n in os.listdir(ORDERS) if n.endswith(".json"))
    except OSError:
        names = []
    for n in names:
        o = fs.read_json(os.path.join(ORDERS, n))
        os.remove(os.path.join(ORDERS, n))
        t0 = time.time()
        try:
            OPS[o["op"]](o)
            res = {"ok": True}
        except Exception as e:
            res = {"ok": False, "err": "%s: %s" % (type(e).__name__, e)}
        res.update(t0=t0, t1=time.time())
        fs.write_json(os.path.join(RESULTS, n), res)
    time.sleep(0.01)
