"""gang 探針的成員任務：用法 python3 member.py <角色> <naive|proto> [crash_after]

成組資料夾經掛載點 `$AOS7_TASK/mnt/cohort`（同組的成員可能在不同 node）。每件事寫一行到 cohort/gang.jsonl：
  {"ev": "start"|"work"|"exit"|"dup-exit"|"abort-exit", "role", "tid", "node", "t", ...}

naive：一起來就每個 tock 做一步「付費工作」（work）。
proto（合作式 prepare／commit）：
  1. 用 O_EXCL 建 cohort/claims/<角色>（內容＝node 與 tid）；已經有人佔了＝重複起的，直接走（dup-exit）
  2. 寫 cohort/ready/<角色>，等 cohort/commit.json；看到 abort.json 就走（abort-exit）
  3. commit 之後才每個 tock 做 work；期間每 20 ms 看 abort.json，有就走
crash_after：做了這麼多步 work、再過 0.1 秒後 exit 1（模擬一個成員在兩個 tock 之間掛掉）。
"""
import json
import os
import signal
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))
import aos7_fs as fs  # noqa: E402

E = fs.task_env()
TASK, TID, NID = E["task"], E["tid"], E["node_id"]
ROLE, MODE = sys.argv[1], sys.argv[2]
CRASH = int(sys.argv[3]) if len(sys.argv) > 3 else None
CO = os.path.join(TASK, "mnt", "cohort")


def log(ev, **kw):
    kw.update(ev=ev, role=ROLE, tid=TID, node=NID, t=time.time())
    fs.append_jsonl(os.path.join(CO, "gang.jsonl"), kw)


def bye(ev, code, **kw):
    log(ev, code=code, **kw)
    sys.exit(code)


def aborted():
    return os.path.exists(os.path.join(CO, "abort.json"))


signal.signal(signal.SIGTERM, lambda *_: bye("exit", 0, why="SIGTERM"))
log("start", round=(fs.read_json(os.path.join(TASK, "birth.json"), {}) or {}).get("round"))
if MODE == "proto":
    os.makedirs(os.path.join(CO, "claims"), exist_ok=True)
    try:
        fd = os.open(os.path.join(CO, "claims", ROLE), os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except FileExistsError:
        bye("dup-exit", 0, why="角色已經有人佔了")
    os.write(fd, json.dumps({"node": NID, "tid": TID}).encode())
    os.close(fd)
    os.makedirs(os.path.join(CO, "ready"), exist_ok=True)
    open(os.path.join(CO, "ready", ROLE), "w").close()
    while not os.path.exists(os.path.join(CO, "commit.json")):
        if aborted():
            bye("abort-exit", 0, why="prepare 時就 abort")
        time.sleep(0.02)

last = (fs.read_json(os.path.join(TASK, "birth.json"), {}) or {}).get("round", 1) - 1
works = 0
while True:
    nxt = fs.wait_tock(TASK, last, timeout=0.02)
    if MODE == "proto" and aborted():
        bye("abort-exit", 0, why="commit 後 abort")
    if nxt is None:
        continue
    last = nxt
    works += 1
    log("work", round=nxt, n=works)
    if CRASH is not None and works >= CRASH:
        time.sleep(0.1)              # 掛在兩個 tock 之間（不跟夥伴的同一步 work 搶先後）
        bye("exit", 1, why="crash")
