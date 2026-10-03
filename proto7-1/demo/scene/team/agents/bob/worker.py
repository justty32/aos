"""示範用：bob 的常駐小工人。每收到 tock 就把進度 +1 寫進 progress.json；
第一輩子做到第 3 次 tock 後「卡住」（不再更新進度，也不結束），讓 kernel 來 restart。"""
import json
import os
import time

task = os.environ["AOS7_TASK"]
first_life = not os.path.exists("worker-was-stuck")
n, last = 0, 0
while True:
    try:
        with open(os.path.join(task, "tock.json")) as f:
            r = json.load(f)["round"]
    except (OSError, ValueError, KeyError):
        r = 0
    if r > last:
        last = r
        if first_life and n >= 3:
            with open("worker-was-stuck", "w") as f:
                f.write("卡在第 %d 回合\n" % r)
            while True:  # 卡住：活著但沒進度
                time.sleep(1)
        n += 1
        tmp = os.path.join(task, "progress.json.tmp")
        with open(tmp, "w") as f:
            json.dump({"n": n, "round": r}, f)
        os.replace(tmp, os.path.join(task, "progress.json"))
    time.sleep(0.02)
