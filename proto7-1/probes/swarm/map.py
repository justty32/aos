"""map 任務：算一塊（index i 的 1000 個數的和），寫 `<node>/out/<批>/<i>.json`。

    python3 map.py <i> [批名]     批名預設 r<birth 回合>
(round + i) % 23 == 0 時故意失敗（exit 3、不寫結果），給 reduce 看「map 失敗怎麼被看到」。
"""
import json
import os
import sys

i = int(sys.argv[1])
task = os.environ["AOS7_TASK"]
with open(os.path.join(task, "birth.json")) as f:
    rnd = json.load(f)["round"]
batch = sys.argv[2] if len(sys.argv) > 2 else "r%d" % rnd
if (rnd + i) % 23 == 0:
    print("map %d 故意失敗" % i)
    sys.exit(3)
out = os.path.join(os.environ["AOS7_NODE"], "out", batch)
os.makedirs(out, exist_ok=True)
tmp = os.path.join(out, "%d.json.tmp" % i)
with open(tmp, "w") as f:
    json.dump({"i": i, "sum": sum(range(i * 1000, (i + 1) * 1000)), "tid": os.environ["AOS7_TID"]}, f)
os.replace(tmp, os.path.join(out, "%d.json" % i))
