"""測試用子工作：child.py <名字> <產物|-> [閘門|-] [退出碼]

每跑一次往 `$AOS7_NODE/ran-<名字>.txt` 加一行 $AOS7_RUN（數得出真的執行幾次）；先寫產物（有給的話），
閘門檔存在就一直等到它被刪（給「產物寫了、結果還沒寫」的探針），最後照退出碼結束。"""
import os
import sys
import time

name, art = sys.argv[1], sys.argv[2]
gate = sys.argv[3] if len(sys.argv) > 3 else "-"
code = int(sys.argv[4]) if len(sys.argv) > 4 else 0
with open(os.path.join(os.environ["AOS7_NODE"], "ran-%s.txt" % name), "a") as f:
    f.write(os.environ.get("AOS7_RUN", "?") + "\n")
if art != "-":
    os.makedirs(os.path.dirname(art) or ".", exist_ok=True)
    with open(art, "w") as f:
        f.write("%s %s\n" % (name, os.environ.get("AOS7_RUN")))
if gate != "-":
    with open(gate + ".entered", "w"):
        pass
    while os.path.exists(gate):
        time.sleep(0.03)
sys.exit(code)
