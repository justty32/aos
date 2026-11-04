"""子時間線上的常駐任務：每 50 ms 在自己 node 的 work/hb.txt 寫心跳（照一般 agent 的寫法：先 makedirs）。"""
import os
import time

node = os.environ["AOS7_NODE"]
n = 0
while True:
    n += 1
    try:
        os.makedirs(os.path.join(node, "work"), exist_ok=True)
        with open(os.path.join(node, "work", "hb.txt"), "w") as f:
            f.write("%d\n" % n)
    except OSError:
        pass
    time.sleep(0.05)
