#!/usr/bin/env python3
"""評估用：一個程序依序替多條時間線做 tick 或 tock。stdin＝[{"node","early"}]，stdout 每條一行。"""
import json, os, signal, sys, time, traceback
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib"))
import aos7_tick, aos7_tock  # noqa: E402
signal.signal(signal.SIGTERM, lambda *_: None)
prog, root = sys.argv[1], sys.argv[2]
for req in json.load(sys.stdin):
    t = time.monotonic()
    try:
        if prog == "aos7-tick":
            r = aos7_tick.tick(root, req["node"])
            out = {k: r[k] for k in ("round", "started", "gone", "stale") if k in r}
        else:
            e = req.get("early")
            out = aos7_tock.tock(root, req["node"], early=None if e is None else e == "1")
        row = {"node": req["node"], "rc": 0, "out": out}
    except Exception:
        row = {"node": req["node"], "rc": 1, "out": None, "err": traceback.format_exc()[-500:]}
    row["ms"] = round((time.monotonic() - t) * 1000, 3)
    print(json.dumps(row, ensure_ascii=False), flush=True)
