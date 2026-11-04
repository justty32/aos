"""supervisor 探針的子工作（被監督的那些）。用法：python3 child.py <名字> <行為> [參數...]

行為：
  stable <ready_s> [依賴...]      起來 ready_s 秒後寫 ready/<名字>（內容＝自己的 tid），之後一直跑
  crash_each <K> [依賴...]        每一代都在收到第 K 個 tock 後 exit 1（crash loop）
  crash_once <K> [依賴...]        每一代都 0.1 秒後 ready；只有第一代在第 K 個 tock 後 exit 1（node 的 crashed-<名字> 當標記）
  temp <K>                        收到第 K 個 tock 後 exit 0（做完一件事就走；Erlang 的 temporary）

每一代起來與結束都寫一行到 <node>/events.jsonl：
  {"ev": "start", "name", "tid", "round"（birth round）, "spawn"（birth.json 的 spawn，沒有＝keep 起的）, "deps_ready"}
  {"ev": "exit", "name", "tid", "code", "round"（node 現在的回合）}
"""
import os
import signal
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))
import aos7_fs as fs  # noqa: E402

E = fs.task_env()
NODE, TASK, TID = E["node"], E["task"], E["tid"]
NAME, BEH = sys.argv[1], sys.argv[2]
ARGS = sys.argv[3:]
EV = os.path.join(NODE, "events.jsonl")
READY = os.path.join(NODE, "ready")


def node_round():
    return (fs.read_json(os.path.join(NODE, ".aos", "round.json"), {}) or {}).get("round")


def alive_ready(dep):
    """依賴的 ready 檔在、而且寫它的那一代還沒結束。"""
    tid = None
    try:
        with open(os.path.join(READY, dep)) as f:
            tid = f.read().strip()
    except OSError:
        return False
    return bool(tid) and not os.path.exists(os.path.join(NODE, ".aos", "tasks", tid, "exit.json"))


def clear_ready():
    try:
        with open(os.path.join(READY, NAME)) as f:
            mine = f.read().strip() == TID
        if mine:
            os.remove(os.path.join(READY, NAME))
    except OSError:
        pass


def bye(code):
    clear_ready()
    fs.append_jsonl(EV, {"ev": "exit", "name": NAME, "tid": TID, "code": code, "round": node_round(), "t": time.time()})
    sys.exit(code)


signal.signal(signal.SIGTERM, lambda *_: bye(0))
birth = fs.read_json(os.path.join(TASK, "birth.json"), {}) or {}
deps = ARGS[1:]
fs.append_jsonl(EV, {"ev": "start", "name": NAME, "tid": TID, "round": birth.get("round"), "spawn": birth.get("spawn"),
                     "deps_ready": {d: alive_ready(d) for d in deps}, "t": time.time()})



def mark_ready():
    os.makedirs(READY, exist_ok=True)
    tmp = os.path.join(READY, ".%s.%s" % (NAME, TID))
    with open(tmp, "w") as f:
        f.write(TID)
    os.replace(tmp, os.path.join(READY, NAME))


last = (birth.get("round") or 1) - 1
if BEH == "crash_once":
    time.sleep(0.1)
    mark_ready()
if BEH in ("crash_each", "temp") or (BEH == "crash_once" and not os.path.exists(os.path.join(NODE, "crashed-" + NAME))):
    k = int(ARGS[0])
    seen = 0
    while seen < k:
        last = fs.wait_tock(TASK, last)
        seen += 1
    if BEH == "crash_once":
        open(os.path.join(NODE, "crashed-" + NAME), "w").close()
    bye(0 if BEH == "temp" else 1)

if BEH == "stable":
    time.sleep(float(ARGS[0]))
    mark_ready()
while True:
    time.sleep(0.2)
