"""chaos 的任務：照 argv[1] 亂來（立刻死、睡、不理 SIGTERM、留孫程序、雙 fork 脫離、刪自己的 taskdir、等幾個 tock、亂請加掛）。

    python3 task.py <行為> [參數]
"""
import json
import os
import random
import shutil
import signal
import sys
import time


def wait_tocks(n, timeout=30):
    """等 n 次 tock（輪詢 $AOS7_TASK/tock.json）；任務資料夾不見了就算了。"""
    p = os.path.join(os.environ.get("AOS7_TASK", "."), "tock.json")
    last, seen, end = None, 0, time.monotonic() + timeout
    while seen < n and time.monotonic() < end:
        try:
            with open(p) as f:
                r = json.load(f).get("round")
        except (OSError, ValueError, AttributeError):
            r = None
        if r is not None and r != last:
            if last is not None:
                seen += 1
            last = r
        time.sleep(0.02)


def main():
    how = sys.argv[1] if len(sys.argv) > 1 else "die"
    arg = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
    rng = random.Random(os.getpid())
    if how == "die":
        sys.exit(rng.choice([0, 0, 1, 3]))
    if how == "sleep":
        time.sleep(arg)
    elif how == "stubborn":                    # 不理 SIGTERM，只有 SIGKILL 收得掉
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        time.sleep(arg)
    elif how == "forker":                      # 留一個同群組的孫程序，自己先走
        if os.fork() == 0:
            time.sleep(arg)
            os._exit(0)
    elif how == "dfork":                       # 雙 fork＋setsid 脫離（環境變數還在）
        if os.fork() == 0:
            os.setsid()
            if os.fork() == 0:
                time.sleep(arg)
                os._exit(0)
            os._exit(0)
        time.sleep(0.05)
    elif how == "selfdel":                     # 刪掉自己的 taskdir 再睡
        shutil.rmtree(os.environ.get("AOS7_TASK", "/nonexistent"), ignore_errors=True)
        time.sleep(arg)
    elif how == "poller":                      # 等幾個 tock 才走
        wait_tocks(int(arg))
    elif how == "mreq":                        # 亂請加掛（合法、跑出根、不是物件、名字壞）
        d = os.path.join(os.environ["AOS7_TASK"], "mount-req")
        os.makedirs(d, exist_ok=True)
        reqs = [{"path": "n0/inbox"}, {"path": "../../etc"}, [1, 2], {"name": ".x", "path": "n1"},
                {"name": 5, "path": "n2"}, {"path": ".aosd"}]
        for k, q in enumerate(rng.sample(reqs, 3)):
            with open(os.path.join(d, ".r%d.tmp" % k), "w") as f:
                json.dump(q, f)
            os.replace(os.path.join(d, ".r%d.tmp" % k), os.path.join(d, "r%d.json" % k))
        wait_tocks(int(arg))
    return 0


if __name__ == "__main__":
    sys.exit(main())
