"""longrun 探針的任務腳本。用法：python3 t.py <long|report|slow> [參數...]

- long N STEP：不看 tock，每 STEP 秒在 $AOS7_TASK/progress.jsonl 寫一行，共 N 行，退出 0。
- report POLL WORK：每 POLL 秒看一次 tock.json；看到新回合 R 先「做事」WORK 秒，再寫 $AOS7_TASK/report-R.json。
  自己也記：看到的回合跳號（gap）、寫報告當下 node 的回合（判斷是不是已經過了下一個 tick）。
- slow S：each 任務，睡 S 秒就退出（比 interval 久）。
"""
import json
import os
import sys
import time


def rj(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def wj(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f)
    os.replace(tmp, path)


def main():
    mode = sys.argv[1]
    task = os.environ["AOS7_TASK"]
    node = os.environ["AOS7_NODE"]
    if mode == "long":
        n, step = int(sys.argv[2]), float(sys.argv[3])
        with open(os.path.join(task, "progress.jsonl"), "a") as f:
            for i in range(n):
                r = rj(os.path.join(node, ".aos", "round.json")) or {}
                f.write(json.dumps({"i": i, "node_round": r.get("round"), "t": time.time()}) + "\n")
                f.flush()
                time.sleep(step)
        return 0
    if mode == "report":
        poll, work = float(sys.argv[2]), float(sys.argv[3])
        last = None
        gaps = []
        while True:
            t = rj(os.path.join(task, "tock.json"))
            r = t.get("round") if isinstance(t, dict) else None
            if isinstance(r, int) and (last is None or r > last):
                if last is not None and r > last + 1:
                    gaps.append([last, r])
                    wj(os.path.join(task, "gaps.json"), gaps)
                time.sleep(work)
                nr = rj(os.path.join(node, ".aos", "round.json")) or {}
                wj(os.path.join(task, "report-%d.json" % r),
                   {"round": r, "node_round_at_write": nr.get("round"), "node_open_at_write": nr.get("open"),
                    "t": time.time()})
                last = r
            time.sleep(poll)
    if mode == "slow":
        time.sleep(float(sys.argv[2]))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
