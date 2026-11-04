"""會生子時間線的假 agent：讀自己 node 的 orders/*.json，照單建／刪 node，結果寫 results/<同名>。

目標寫法 {"via": "own"|"mount"|"raw", "path": ...}：
- own：相對自己 node（例如 sub/a）
- mount：空間路徑，經過掛載點（宣告的或執行中加掛的）
- raw：空間路徑，直接寫（不經掛載，違反「只碰給的資料夾」，給寫入紀錄抓）
"""
import json
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))
import aos7_fs as fs  # noqa: E402
import aos7_mount  # noqa: E402

E = fs.task_env()
NODE, TASK, ROOT = E["node"], E["task"], E["root"]
ORDERS, RESULTS = os.path.join(NODE, "orders"), os.path.join(NODE, "results")


def where(t):
    via, p = t["via"], t["path"]
    if via == "own":
        return os.path.join(NODE, p)
    if via == "mount":
        r = aos7_mount.resolver(TASK)(p)
        if r is None:
            raise RuntimeError("沒掛到 %s" % p)
        return r
    return os.path.join(ROOT, p)


def op_create(o):
    base = where(o["target"])
    tl = os.path.join(base, ".aos", "timeline.json")
    tk = os.path.join(base, ".aos", "tasks.json")
    tasks = {"tasks": o.get("tasks", [])}
    timeline = {"interval_ms": o.get("interval_ms", 100)}
    if o.get("order") == "timeline_first":
        fs.write_json(tl, timeline)
        t_tl = time.time()
        time.sleep(o.get("gap_ms", 0) / 1000.0)
        fs.write_json(tk, tasks)
    else:
        fs.write_json(tk, tasks)
        fs.write_json(tl, timeline)
        t_tl = time.time()
    return {"t_timeline": t_tl, "base": base}


def op_rmtree(o):
    base = where(o["target"])
    shutil.rmtree(base)
    return {"t": time.time()}


def op_rm_timeline(o):
    os.remove(os.path.join(where(o["target"]), ".aos", "timeline.json"))
    return {"t": time.time()}


def op_write_timeline(o):
    fs.write_json(os.path.join(where(o["target"]), ".aos", "timeline.json"), {"interval_ms": o.get("interval_ms", 100)})
    return {"t": time.time()}


def op_peek(o):
    """父看子的結果：直接讀子 node 的 round.json 與 rounds.jsonl 尾巴（讀不受「只碰給的資料夾」管）。"""
    a = os.path.join(where(o["target"]), ".aos")
    return {"round": fs.read_json(os.path.join(a, "round.json"), {}),
            "last": fs.tail_jsonl(os.path.join(a, "rounds.jsonl"), 1)}


def op_edit_tasks(o):
    p = os.path.join(where(o["target"]), ".aos", "tasks.json")
    t = fs.read_json(p, {}) or {}
    t.setdefault("tasks", []).append(o["add"])
    fs.write_json(p, t)
    return {"t": time.time()}


def op_mount(o):
    end = time.time() + 5
    st = None
    while time.time() < end:
        st = aos7_mount.request(TASK, o["path"], why="管理子時間線")
        if st == "mounted" or st.startswith("refused"):
            break
        time.sleep(0.02)
    return {"status": st}


OPS = {k[3:]: v for k, v in globals().items() if k.startswith("op_")}


def main():
    while True:
        try:
            names = sorted(n for n in os.listdir(ORDERS) if n.endswith(".json"))
        except OSError:
            names = []
        for n in names:
            o = fs.read_json(os.path.join(ORDERS, n))
            os.remove(os.path.join(ORDERS, n))
            try:
                res = {"ok": True, **OPS[o["op"]](o)}
            except Exception as e:
                res = {"ok": False, "err": "%s: %s" % (type(e).__name__, e)}
            fs.write_json(os.path.join(RESULTS, n), res)
        time.sleep(0.02)


main()
