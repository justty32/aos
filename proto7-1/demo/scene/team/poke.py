"""示範用（路二，S-21）：team 每回合起一次的小任務，在固定回合寫子 daemon 的控制檔。"""
import json
import os
import time

r = json.load(open(".aos/round.json"))["round"]
op = {4: "pause", 8: "resume"}.get(r)
if op:
    ctl = os.path.join("sub", ".aosd", "ctl")
    os.makedirs(ctl, exist_ok=True)
    name = os.path.join(ctl, "poke-r%d.json" % r)
    with open(name + ".tmp", "w") as f:
        json.dump({"op": op, "node": "w", "by": "team:" + os.environ.get("AOS7_TID", "?")}, f)
    os.replace(name + ".tmp", name)
    print("第 %d 回合：寫子 daemon 控制檔 %s w" % (r, op))
