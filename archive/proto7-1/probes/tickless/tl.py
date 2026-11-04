"""tickless 探針的任務：用法 python3 tl.py <角色>

  idle   n/XXX 的 agent（keep）：每收到一個 tock 處理 inbox/*.json（寫一行 done.jsonl、信搬到 inbox/done/），
         再寫 idle.json＝{"idle_safe": inbox 空了沒, "round", "t"}——宣告「沒信時跳過回合也沒關係」
  cron   n/XXX 的定時工作（keep）：每 3 回合做一次事（cron.jsonl），idle.json 永遠 idle_safe: false（它要回合）
  kern   k 的 kernel（keep）：掛著 .aosd 和 100 個 node。`<k>/mode.json` 的 active 為 true 時每 20 ms 看一圈：
         - node 沒停、idle.json 是這回合寫的而且 idle_safe、inbox 空 → pause
         - node 停著（status.json 的 paused）而且 inbox 有信 → resume rounds 1（跑一回合讓 agent 收信，之後 daemon 自己停回去）；
           mode.json 的 wake 為 true 時緊接著再寫一個 wake（resume 不會打斷「等上一回合 interval 滿」的睡眠）
         每個決定寫一行到 <k>/kern.jsonl。沒有事件來源：信到了沒，只能自己輪詢。
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))
import aos7_fs as fs  # noqa: E402

E = fs.task_env()
NODE, TASK, TID = E["node"], E["task"], E["tid"]
ROLE = sys.argv[1]


def letters(inbox):
    try:
        return sorted(n for n in os.listdir(inbox) if n.endswith(".json") and not n.startswith("."))
    except OSError:
        return []


def agent(cron):
    inbox = os.path.join(NODE, "inbox")
    last = (fs.read_json(os.path.join(TASK, "birth.json"), {}) or {}).get("round", 1) - 1
    while True:
        last = fs.wait_tock(TASK, last, poll=0.01)
        for n in letters(inbox):
            p = os.path.join(inbox, n)
            body = fs.read_json(p, {}) or {}
            fs.append_jsonl(os.path.join(NODE, "done.jsonl"), {"letter": n, "round": last, "t": time.time(),
                                                               "sent_t": body.get("t"), "sent_round": body.get("round")})
            os.makedirs(os.path.join(inbox, "done"), exist_ok=True)
            os.replace(p, os.path.join(inbox, "done", n))
        if cron and last % 3 == 0:
            fs.append_jsonl(os.path.join(NODE, "cron.jsonl"), {"round": last, "t": time.time()})
        fs.write_json(os.path.join(NODE, "idle.json"),
                      {"idle_safe": not cron and not letters(inbox), "round": last, "t": time.time()})


def kern():
    mnt = os.path.join(TASK, "mnt")
    birth = fs.read_json(os.path.join(TASK, "birth.json"), {}) or {}
    nodes = {k: v["to"] for k, v in (birth.get("mounts") or {}).items() if k != "aosd"}   # 掛載名 -> node id
    klog = os.path.join(NODE, "kern.jsonl")
    pending = {}        # node id -> (op, t)：寫了、daemon 還沒反映
    seq = 0
    while True:
        time.sleep(0.02)
        mode = fs.read_json(os.path.join(NODE, "mode.json"), {}) or {}
        if not mode.get("active"):
            continue
        st = (fs.read_json(os.path.join(mnt, "aosd", "status.json"), {}) or {}).get("nodes", {})
        for m, nid in nodes.items():
            s = st.get(nid)
            if not s:
                continue
            paused = s.get("paused")
            p = pending.get(nid)        # (op, t, 寫的時候的回合)
            if p and ((p[0] == "pause" and paused) or (p[0] == "resume" and (not paused or s.get("round", 0) > p[2]))):
                pending.pop(nid)
                p = None
            if p and time.time() - p[1] < 0.5:
                continue
            inbox = letters(os.path.join(mnt, m, "inbox"))
            op = None
            if paused and inbox:
                op = "resume"
            elif not paused and not inbox and s.get("phase") == "idle":
                idle = fs.read_json(os.path.join(mnt, m, "idle.json"), {}) or {}
                if idle.get("idle_safe") is True and idle.get("round") == s.get("round"):
                    op = "pause"
            if op is None:
                continue
            seq += 1
            c = {"op": op, "node": nid, "by": "k:kern", "why": "有信" if op == "resume" else "閒著、宣告 idle_safe"}
            if op == "resume":
                c["rounds"] = 1
            fs.write_json(os.path.join(mnt, "aosd", "ctl", "kern-%s-%06d.json" % (TID, seq)), c)
            if op == "resume" and mode.get("wake"):
                seq += 1          # 同一批、檔名排在 resume 後面：不等上一回合剩下的 interval
                fs.write_json(os.path.join(mnt, "aosd", "ctl", "kern-%s-%06d.json" % (TID, seq)),
                              {"op": "wake", "node": nid, "by": "k:kern", "why": "剛 resume，不等 interval"})
            pending[nid] = (op, time.time(), s.get("round", 0))
            fs.append_jsonl(klog, {"op": op, "node": nid, "t": time.time(), "letters": len(inbox), "round": s.get("round")})


if ROLE == "kern":
    kern()
else:
    agent(ROLE == "cron")
