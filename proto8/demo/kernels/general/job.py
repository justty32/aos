"""demo 用的三種活（被閘門包住、由通用 kernel 排）：

    python3 job.py llm 秒     假腦：睡幾秒，回 {"role": "assistant", "content": ...}
    python3 job.py cpu 秒     假 cpu 活：睡幾秒，回 {"done": ...}
    python3 job.py human      問人：在 $DEMO_HUMAN/<pid>.q 寫問題，等 <pid>.a 出現（假人寫的），回那個答案

stdin＝閘門轉來的請求（原樣），拿第一行當「誰」。
"""
import json
import os
import sys
import time

kind = sys.argv[1]
who = sys.stdin.read().strip()
if kind == "human":
    d = os.environ["DEMO_HUMAN"]
    q, a = os.path.join(d, "%d.q" % os.getpid()), os.path.join(d, "%d.a" % os.getpid())
    with open(q + ".tmp", "w", encoding="utf-8") as f:
        f.write(who)
    os.replace(q + ".tmp", q)
    while not os.path.exists(a):
        time.sleep(0.05)
    with open(a, encoding="utf-8") as f:
        print(json.dumps({"answer": f.read()}, ensure_ascii=False))
else:
    time.sleep(float(sys.argv[2]))
    key = "content" if kind == "llm" else "done"
    print(json.dumps({"role": "assistant", key: who} if kind == "llm" else {key: who}, ensure_ascii=False))
