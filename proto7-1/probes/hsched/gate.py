"""hsched 的帳本／閘門（keep 任務，node `bank`）：四組策略共用，worker 每筆工作開始前都要過它。不打 LLM。

沿用 probes/ledger 的思路、簡化：唯一寫帳的人、事件流只加不改、request_id 去重、回條寫好才刪請求。
收 `bank/io/requests/*.json`，寫 `bank/io/receipts/<request_id>.json`；帳在 `bank/ledger/events.jsonl`、`summary.json`。

  grant  {ticket, project, job, tokens, worker}  開工前：票要是 kernel 發的（`mnt/pub/tickets/<ticket>.json`，
         欄位一致）、沒用過、沒過期（TICKET_TTL 回合）；envelope 沒凍結這個專案；專案在途 < envelope 上限、
         全域在途 < 根上限；已花＋保留＋這筆 ≤ 專案額度。過了才記一筆保留（reserve）。
  settle {ticket, used}                           做完：用量 ≤ 保留額，在途 −1。
控制回合讀 `mnt/clk/round.json`（ctl node 的回合，daemon 寫的，不靠 kernel）。
"""
import fcntl
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "lib"))
sys.path.insert(0, HERE)
import aos7_fs as fs  # noqa: E402
import sim  # noqa: E402
import time  # noqa: E402

E = fs.task_env()
NODE = E["node"]
LED = os.path.join(NODE, "ledger")
EV = os.path.join(LED, "events.jsonl")
IO = os.path.join(NODE, "io")
PUB = os.path.join(E["task"], "mnt", "pub")
CLK = os.path.join(E["task"], "mnt", "clk", "round.json")
os.makedirs(LED, exist_ok=True)
lock = open(os.path.join(LED, "writer.lock"), "a")
fcntl.flock(lock, fcntl.LOCK_EX)

acct = {p: {"limit": sim.BUDGET[p], "reserved": 0, "spent": 0, "inflight": 0} for p in sim.PROJECTS}
held = {}           # ticket → {project, tokens}
used_tickets = set()
by_rid = {}
events = []


def apply(ev):
    k = ev["kind"]
    if k == "grant":
        a = acct[ev["project"]]
        a["reserved"] += ev["tokens"]
        a["inflight"] += 1
        held[ev["ticket"]] = {"project": ev["project"], "tokens": ev["tokens"]}
        used_tickets.add(ev["ticket"])
    elif k == "settle":
        h = held.pop(ev["ticket"])
        a = acct[h["project"]]
        a["reserved"] -= h["tokens"]
        a["spent"] += ev["used"]
        a["inflight"] -= 1
    by_rid[ev["request_id"]] = ev
    events.append(ev)


def clock():
    return (fs.read_json(CLK, {}) or {}).get("round", 0)


def record(ev):
    ev = dict(ev, seq=len(events) + 1, at=fs.now())
    fs.append_jsonl(EV, ev)
    apply(ev)
    fs.write_json(os.path.join(LED, "summary.json"), {"revision": len(events), "accounts": acct,
                                                       "global_inflight": sum(a["inflight"] for a in acct.values())})
    return ev


def handle(req, rid):
    op = req.get("op")
    now = clock()
    t = req.get("ticket")
    if op == "grant":
        tk = fs.read_json(os.path.join(PUB, "tickets", "%s.json" % t)) if isinstance(t, str) else None
        if not isinstance(tk, dict):
            return {"ok": False, "why": "沒有這張派工票 %r（不是 kernel 發的）" % t, "reason": "no_ticket"}
        for k in ("project", "job", "tokens", "worker"):
            if tk.get(k) != req.get(k):
                return {"ok": False, "why": "票上的 %s 是 %r，請求寫 %r" % (k, tk.get(k), req.get(k)), "reason": "mismatch"}
        if t in used_tickets:
            return {"ok": False, "why": "票 %s 已用過" % t, "reason": "replay"}
        if now > tk["round"] + sim.TICKET_TTL:
            return {"ok": False, "why": "票是第 %d 回合發的，現在第 %d 回合：過期不補發" % (tk["round"], now), "reason": "expired"}
        env = fs.read_json(os.path.join(PUB, "envelope.json"), {}) or {}
        p = tk["project"]
        pe = (env.get("projects") or {}).get(p) or {}
        if pe.get("frozen"):
            return {"ok": False, "why": "根凍結了 %s 的新 grant" % p, "reason": "frozen"}
        a = acct[p]
        if a["inflight"] >= min(sim.PROJECT_CAP, pe.get("max_inflight", sim.PROJECT_CAP)):
            return {"ok": False, "why": "%s 在途 %d 已達 envelope 上限" % (p, a["inflight"]), "reason": "cap"}
        if sum(x["inflight"] for x in acct.values()) >= sim.GLOBAL_CAP:
            return {"ok": False, "why": "全域在途已達根上限 %d" % sim.GLOBAL_CAP, "reason": "cap"}
        if a["spent"] + a["reserved"] + tk["tokens"] > a["limit"]:
            return {"ok": False, "why": "%s 額度不足" % p, "reason": "budget"}
        ev = record({"kind": "grant", "request_id": rid, "ticket": t, "project": p, "job": tk["job"],
                     "tokens": tk["tokens"], "worker": tk["worker"], "by": tk.get("by"), "round": now})
        return {"ok": True, "round": now, "event_seq": ev["seq"]}
    if op == "settle":
        if t not in held:
            return {"ok": False, "why": "票 %r 沒有保留額" % t, "reason": "no_hold"}
        used = req.get("used")
        if not isinstance(used, int) or used < 0:
            return {"ok": False, "why": "used 要是非負整數", "reason": "schema"}
        ev = record({"kind": "settle", "request_id": rid, "ticket": t, "used": min(used, held[t]["tokens"]),
                     "round": now})
        return {"ok": True, "round": now, "used": ev["used"]}
    return {"ok": False, "why": "不認得的 op %r" % op, "reason": "schema"}


for ev in fs.read_jsonl(EV):
    apply(ev)
RQ = os.path.join(IO, "requests")
RC = os.path.join(IO, "receipts")
os.makedirs(RQ, exist_ok=True)
os.makedirs(RC, exist_ok=True)
print("up: %d events" % len(events), flush=True)
while True:
    for f in sorted(x for x in os.listdir(RQ) if x.endswith(".json") and not x.startswith(".")):
        req = fs.read_json(os.path.join(RQ, f))
        rid = (req.get("request_id") if isinstance(req, dict) else None) or f[:-5]
        rp = os.path.join(RC, rid + ".json")
        if not os.path.exists(rp):
            if rid in by_rid:
                out = {"ok": True, "replayed": True, "round": by_rid[rid].get("round")}
            elif not isinstance(req, dict):
                out = {"ok": False, "why": "讀不懂的請求", "reason": "schema"}
            else:
                out = handle(req, rid)
            out.update(request_id=rid, at=fs.now())
            fs.write_json(rp, out)
        try:
            os.remove(os.path.join(RQ, f))
        except OSError:
            pass
    time.sleep(0.01)
