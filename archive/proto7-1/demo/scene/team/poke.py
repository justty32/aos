"""示範用（路二，S-21）：team 每回合起一次的小任務，在固定回合寫子 daemon 的控制檔。
子 daemon 的 .aosd/ctl 由 tick 掛在 $AOS7_TASK/mnt/subctl（tasks.json 的 mounts，S-23），只經過它寫。"""
import json
import os

r = json.load(open(".aos/round.json"))["round"]
op = {4: "pause", 8: "resume"}.get(r)
if op:
    name = os.path.join(os.environ["AOS7_TASK"], "mnt", "subctl", "poke-r%d.json" % r)
    with open(name + ".tmp", "w") as f:
        json.dump({"op": op, "node": "w", "by": "team:" + os.environ.get("AOS7_TID", "?")}, f)
    os.replace(name + ".tmp", name)
    print("第 %d 回合：寫子 daemon 控制檔 %s w" % (r, op))
