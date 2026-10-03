"""sched 探針的排程 kernel（keep 任務）：每收到自己 node 的 tock 跑一次策略，用 daemon ctl pause／resume 成員。

設定 <node>/sched.json：
  {"strategy": "rr",   "members": [...], "n": 2, "k": 3, "safe": false}
  {"strategy": "prio", "highs": [...], "lows": [...]}
  {"strategy": "cron", "jobs": [{"node", "every", "how": "fast"|"naive"|"batch"}]}
掛載（tasks.json 宣告）：aosd → .aosd；m_<成員> → <成員>/.aos；q_<成員> → <成員>/queue（prio 的高優先）。
每件事記一行到 $AOS7_TASK/sched.jsonl（t＝time.time()，給探針算延遲）。
"""
import json
import os
import time

T = os.environ["AOS7_TASK"]
NODE = os.environ["AOS7_NODE"]
MNT = os.path.join(T, "mnt")
LOG = os.path.join(T, "sched.jsonl")


def rj(p, d=None):
    try:
        with open(p) as f:
            return json.load(f)
    except (OSError, ValueError):
        return d


def wj(p, o):
    tmp = "%s.tmp%d" % (p, os.getpid())
    with open(tmp, "w") as f:
        json.dump(o, f)
    os.replace(tmp, p)


def log(ev, **kw):
    kw.update(ev=ev, t=time.time())
    with open(LOG, "a") as f:
        f.write(json.dumps(kw) + "\n")


cfg = rj(os.path.join(NODE, "sched.json"), {})
seq = [0]
watch = []          # 等回條／等生效的 ctl


def round_of(node):
    return (rj(os.path.join(MNT, "m_" + node, "round.json"), {}) or {}).get("round", 0)


def status():
    return rj(os.path.join(MNT, "aosd", "status.json"), {}) or {}


def ctl(op, node, why, kr):
    seq[0] += 1
    name = "k-%05d-%s-%s.json" % (seq[0], op, node)
    r0 = round_of(node)
    t = time.time()
    wj(os.path.join(MNT, "aosd", "ctl", name), {"op": op, "node": node, "by": "sched", "why": why})
    log("ctl", file=name, op=op, node=node, kr=kr, mround=r0, why=why, tw=t)
    watch.append({"file": name, "op": op, "node": node, "t": t, "r0": r0, "done": False, "eff": False})
    return name


def poll_watch():
    st = None
    keep = []
    for w in watch:
        now = time.time()
        if not w["done"]:
            res = rj(os.path.join(MNT, "aosd", "ctl-done", w["file"]))
            if res is not None:
                w["done"] = True
                log("done", file=w["file"], dt=now - w["t"], ok=(res.get("result") or {}).get("ok"))
        if w["done"] and not w["eff"]:
            if w["op"] == "pause":
                st = st or status()
                n = st.get("nodes", {}).get(w["node"], {})
                if n.get("paused") and n.get("phase") == "paused":
                    w["eff"] = True
            elif round_of(w["node"]) > w["r0"]:
                w["eff"] = True
            if w["eff"]:
                log("eff", file=w["file"], op=w["op"], node=w["node"], dt=now - w["t"],
                    extra=round_of(w["node"]) - w["r0"])
        if not (w["done"] and w["eff"]):
            if now - w["t"] > 1.5:
                log("noeff", file=w["file"], done=w["done"])
            else:
                keep.append(w)
    watch[:] = keep


# ---------- (a) round-robin ----------
rr = {"active": None, "pending": None}


def rr_tock(kr):
    ms, n, k = cfg["members"], cfg.get("n", 2), cfg.get("k", 3)
    idx = (kr - 1) // k
    new = {ms[(idx * n + j) % len(ms)] for j in range(n)}
    if new == rr["active"]:
        return
    if rr["pending"]:                 # 上一次安全輪替還沒放行：先放行（記一下）
        log("safe_late", inc=sorted(rr["pending"]["inc"]))
        for m in sorted(rr["pending"]["inc"]):
            ctl("resume", m, "rr late", kr)
        rr["pending"] = None
    old = rr["active"]
    out = (set(ms) if old is None else old) - new
    for m in sorted(out):
        ctl("pause", m, "rr out", kr)
    inc = set() if old is None else new - old
    if cfg.get("safe") and inc:
        rr["pending"] = {"inc": inc, "out": out, "t": time.time(), "kr": kr}
    else:
        for m in sorted(inc):
            ctl("resume", m, "rr in", kr)
    rr["active"] = new
    log("rotate", kr=kr, active=sorted(new), safe=bool(cfg.get("safe")))


def rr_poll():
    p = rr["pending"]
    if not p:
        return
    nodes = status().get("nodes", {})
    if all(nodes.get(o, {}).get("phase") == "paused" for o in p["out"]):
        log("safe_go", wait=time.time() - p["t"], kr=p["kr"])
        for m in sorted(p["inc"]):
            ctl("resume", m, "rr in (safe)", p["kr"])
        rr["pending"] = None


# ---------- (b) 優先序 ----------
prio = {}


def prio_tock(kr):
    highs, lows = cfg["highs"], cfg["lows"]
    work = [h for h in highs if any(x.endswith(".json") for x in (os.listdir(os.path.join(MNT, "q_" + h))
                                                                  if os.path.isdir(os.path.join(MNT, "q_" + h)) else []))]
    want = set(work) if work else set(lows)
    for m in highs + lows:
        d = m in want
        if prio.get(m) != d:
            ctl("resume" if d else "pause", m, "prio work=%s" % work, kr)
            prio[m] = d


# ---------- (c) 類 cron ----------
jobs = [dict(j, pending=None, pause_kr=None, step=None) for j in cfg.get("jobs", [])]


def cron_tock(kr):
    for j in jobs:
        if j["pause_kr"] == kr:
            ctl("pause", j["node"], "cron naive", kr)
            j["pause_kr"] = None
            j["step"]["paused"] = True
        if kr % j["every"] or j["step"]:
            continue
        r0 = round_of(j["node"])
        j["step"] = {"r0": r0, "kr": kr, "paused": False}
        log("step", node=j["node"], how=j["how"], kr=kr, r0=r0)
        ctl("resume", j["node"], "cron step", kr)
        if j["how"] == "fast":
            j["pending"] = r0
        elif j["how"] == "naive":
            j["pause_kr"] = kr + 1
        else:                                      # batch：resume 跟 pause 一起寫
            ctl("pause", j["node"], "cron batch", kr)
            j["step"]["paused"] = True


def cron_poll():
    st = None
    for j in jobs:
        if j["pending"] is not None and round_of(j["node"]) > j["pending"]:
            ctl("pause", j["node"], "cron fast", j["step"]["kr"])
            j["pending"] = None
            j["step"]["paused"] = True
        s = j["step"]
        if s and s["paused"] and not any(w["node"] == j["node"] for w in watch):
            st = st or status()
            if st.get("nodes", {}).get(j["node"], {}).get("phase") == "paused":
                log("settled", node=j["node"], how=j["how"], kr=s["kr"], ran=round_of(j["node"]) - s["r0"])
                j["step"] = None


TOCK = {"rr": rr_tock, "prio": prio_tock, "cron": cron_tock}[cfg["strategy"]]
POLL = {"rr": rr_poll, "prio": lambda: None, "cron": cron_poll}[cfg["strategy"]]

last = 0
while True:
    tk = rj(os.path.join(T, "tock.json"))
    if isinstance(tk, dict) and tk.get("round", 0) > last:
        last = tk["round"]
        log("tock", kr=last)
        TOCK(last)
    poll_watch()
    POLL()
    time.sleep(0.005)
