"""ledger 探針的帳本（keep 任務，node `bank`）：唯一寫 ledger 的人。不打任何 LLM。

收 `bank/io/requests/*.json`（掛給客戶的就是 `bank/io`），寫 `bank/io/receipts/<request_id>.json`，回條寫好才刪請求。
帳是事件流 `bank/ledger/events.jsonl`（只加不改），狀態每次起來從事件重播；`bank/ledger/summary.json` 是彙總視圖。
給 provider 驗的 `bank/io/reservations/<res_id>.json`（帳本發布，別人只讀）。
單一寫入者：keep 保證同名只有一個活的；另外拿 `bank/ledger/writer.lock` 的 flock（舊的沒死透不會兩個一起寫）。

請求（都帶 request_id；同一 request_id 已有事件＝照事件補回條，不記第二筆）：
  delegate {parent, children: [{context_id, tokens, holder}], expected_revision?}  非同步 split，全有或全無
  reserve  {context, tokens}               → res_id（未 claim 的保留額＝grant）
  claim    {res_id, attempt_id, executor}  一個 res 只能被一個 attempt claim
  settle   {res_id, attempt_id}            用量取 provider 回條（`mnt/prov/<attempt_id>.json`），不信 client 自報
  release  {res_id}                        未 claim 的才放；已 claim、provider 沒回條＝在途未知，不放
  return   {context_id}                    子 context 的剩額還給父

設定 `bank/accounts.json`：{"P": {"limit": 10000}, ...}。故障鈕 `bank/fault.json`：{"hang_after_event": request_id}。
"""
import fcntl
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))
import aos7_fs as fs  # noqa: E402

E = fs.task_env()
NODE = E["node"]
LED = os.path.join(NODE, "ledger")
EV = os.path.join(LED, "events.jsonl")
IO = os.path.join(NODE, "io")
PROV = os.path.join(E["task"], "mnt", "prov")
os.makedirs(LED, exist_ok=True)
lock = open(os.path.join(LED, "writer.lock"), "a")
fcntl.flock(lock, fcntl.LOCK_EX)

ctx, res, by_rid, events = {}, {}, {}, []


def apply(ev):
    k = ev["kind"]
    if k == "open":
        ctx[ev["cid"]] = {"root": ev["cid"], "parent": None, "free": ev["limit"], "limit": ev["limit"], "open": True}
    elif k == "delegate":
        ctx[ev["parent"]]["free"] -= sum(c["tokens"] for c in ev["children"])
        for c in ev["children"]:
            ctx[c["context_id"]] = {"root": ctx[ev["parent"]]["root"], "parent": ev["parent"], "free": c["tokens"],
                                    "holder": c.get("holder"), "open": True}
    elif k == "reserve":
        ctx[ev["cid"]]["free"] -= ev["tokens"]
        res[ev["res_id"]] = {"res_id": ev["res_id"], "cid": ev["cid"], "root": ctx[ev["cid"]]["root"],
                             "tokens": ev["tokens"], "state": "reserved", "attempt_id": None, "executor": None}
    elif k == "claim":
        res[ev["res_id"]].update(attempt_id=ev["attempt_id"], executor=ev["executor"])
    elif k in ("settle", "release"):
        r = res[ev["res_id"]]
        used = ev.get("used", 0)
        r.update(state="spent" if k == "settle" else "released", used=used)
        back = r["tokens"] - used
        c = r["cid"]
        while not ctx[c]["open"]:          # context 已還給父：剩額一路往上找開著的
            c = ctx[c]["parent"]
        ctx[c]["free"] += back
    elif k == "return":
        c = ctx[ev["cid"]]
        ctx[c["parent"]]["free"] += c["free"]
        c.update(free=0, open=False)
    if ev.get("request_id"):
        by_rid[ev["request_id"]] = ev
    events.append(ev)


def summary():
    roots = {}
    for cid, c in ctx.items():
        if c["parent"] is None:
            roots[cid] = {"limit": c["limit"], "spent": 0, "reserved": 0, "delegated_unspent": 0, "free": c["free"]}
    for cid, c in ctx.items():
        if c["parent"] is not None:
            roots[c["root"]]["delegated_unspent"] += c["free"]
    for r in res.values():
        if r["state"] == "spent":
            roots[r["root"]]["spent"] += r["used"]
        elif r["state"] == "reserved":
            roots[r["root"]]["reserved"] += r["tokens"]
    return {"revision": len(events), "roots": roots,
            "contexts": {k: {"free": v["free"], "open": v["open"], "root": v["root"]} for k, v in ctx.items()},
            "at": fs.now()}


def publish(rid_res):
    r = res[rid_res]
    fs.write_json(os.path.join(IO, "reservations", rid_res + ".json"), r)


def record(ev):
    ev = dict(ev, seq=len(events) + 1, at=fs.now())
    fs.append_jsonl(EV, ev)       # 先落帳（唯一真相），再改記憶體、發布、回條
    apply(ev)
    if ev.get("res_id"):
        publish(ev["res_id"])
    fs.write_json(os.path.join(LED, "summary.json"), summary())
    fault = fs.read_json(os.path.join(NODE, "fault.json"), {}) or {}
    if ev.get("request_id") and fault.get("hang_after_event") == ev["request_id"]:
        print("hang after event", ev["request_id"], flush=True)
        while True:               # 卡在「落帳之後、回條之前」：等探針 kill
            time.sleep(1)
    return ev


def receipt_of(ev):
    out = {"ok": True, "kind": ev["kind"], "event_seq": ev["seq"]}
    for k in ("res_id", "used", "children", "cid"):
        if k in ev:
            out[k] = ev[k]
    return out


def handle(req):
    op = req.get("op")
    if op == "delegate":
        p = ctx.get(req.get("parent"))
        kids = req.get("children") or []
        if not p or not p["open"]:
            return {"ok": False, "why": "父 context %r 不存在或已關" % req.get("parent")}
        if "expected_revision" in req and req["expected_revision"] != len(events):
            return {"ok": False, "why": "版號已變（帳是 %d，請求寫 %d）：重讀再送，不做半套" % (len(events), req["expected_revision"])}
        if any(k.get("context_id") in ctx or not isinstance(k.get("tokens"), int) or k["tokens"] <= 0 for k in kids) or not kids:
            return {"ok": False, "why": "children 不合（context_id 已存在或 tokens 不是正整數）"}
        need = sum(k["tokens"] for k in kids)
        if need > p["free"]:
            return {"ok": False, "why": "額度不足：%s 自由額度 %d，要切 %d；整份不做" % (req["parent"], p["free"], need)}
        return receipt_of(record({"kind": "delegate", "request_id": req["request_id"], "parent": req["parent"],
                                  "children": [{"context_id": k["context_id"], "tokens": k["tokens"],
                                                "holder": k.get("holder")} for k in kids]}))
    if op == "reserve":
        c = ctx.get(req.get("context"))
        t = req.get("tokens")
        if not c or not c["open"]:
            return {"ok": False, "why": "context %r 不存在或已還給父" % req.get("context")}
        if not isinstance(t, int) or t <= 0:
            return {"ok": False, "why": "tokens 要是正整數"}
        if t > c["free"]:
            return {"ok": False, "why": "額度不足：%s 剩 %d，要 %d" % (req["context"], c["free"], t)}
        return receipt_of(record({"kind": "reserve", "request_id": req["request_id"], "cid": req["context"],
                                  "tokens": t, "res_id": "res-%d" % (len(events) + 1)}))
    r = res.get(req.get("res_id"))
    if op in ("claim", "settle", "release") and not r:
        return {"ok": False, "why": "沒有這筆保留額 %r" % req.get("res_id")}
    if op == "claim":
        if r["state"] != "reserved":
            return {"ok": False, "why": "%s 已是 %s" % (r["res_id"], r["state"])}
        if r["attempt_id"] == req.get("attempt_id"):
            return {"ok": True, "kind": "claim", "res_id": r["res_id"], "note": "同一 attempt 已 claim 過"}
        if r["attempt_id"]:
            return {"ok": False, "why": "重複：%s 已被 attempt %s（%s）claim；同一份 grant 不能給兩個 worker"
                    % (r["res_id"], r["attempt_id"], r["executor"])}
        return receipt_of(record({"kind": "claim", "request_id": req["request_id"], "res_id": r["res_id"],
                                  "attempt_id": req.get("attempt_id"), "executor": req.get("executor")}))
    if op == "settle":
        if r["state"] != "reserved":
            return {"ok": False, "why": "%s 已是 %s，不再結算" % (r["res_id"], r["state"])}
        pr = fs.read_json(os.path.join(PROV, "%s.json" % r["attempt_id"])) if r["attempt_id"] else None
        if not isinstance(pr, dict):
            return {"ok": False, "why": "provider 沒有 attempt %s 的回條：在途未知，不結算也不釋放" % r["attempt_id"]}
        used = pr.get("used", 0) if pr.get("state") == "done" else 0
        return receipt_of(record({"kind": "settle", "request_id": req["request_id"], "res_id": r["res_id"],
                                  "used": min(used, r["tokens"]), "provider_state": pr.get("state")}))
    if op == "release":
        if r["state"] != "reserved":
            return {"ok": False, "why": "%s 已是 %s" % (r["res_id"], r["state"])}
        if r["attempt_id"]:
            pr = fs.read_json(os.path.join(PROV, "%s.json" % r["attempt_id"]))
            if not isinstance(pr, dict):
                return {"ok": False, "why": "在途未知：%s 已被 attempt %s claim、provider 沒回條；不釋放（等 provider 確認後 settle）"
                        % (r["res_id"], r["attempt_id"])}
            return {"ok": False, "why": "provider 已回條（%s），用 settle" % pr.get("state")}
        return receipt_of(record({"kind": "release", "request_id": req["request_id"], "res_id": r["res_id"]}))
    if op == "return":
        c = ctx.get(req.get("context_id"))
        if not c or c["parent"] is None or not c["open"]:
            return {"ok": False, "why": "%r 不是開著的子 context" % req.get("context_id")}
        return receipt_of(record({"kind": "return", "request_id": req["request_id"], "cid": req["context_id"]}))
    return {"ok": False, "why": "不認得的 op %r" % op}


for ev in fs.read_jsonl(EV):
    apply(ev)
for name, a in sorted((fs.read_json(os.path.join(NODE, "accounts.json"), {}) or {}).items()):
    if name not in ctx:
        record({"kind": "open", "cid": name, "limit": a["limit"]})
for k in res:
    publish(k)
fs.write_json(os.path.join(LED, "summary.json"), summary())
print("up: %d events" % len(events), flush=True)

RQ = os.path.join(IO, "requests")
os.makedirs(RQ, exist_ok=True)
while True:
    for f in sorted(x for x in os.listdir(RQ) if x.endswith(".json") and not x.startswith(".")):
        req = fs.read_json(os.path.join(RQ, f))
        rid = (req or {}).get("request_id") if isinstance(req, dict) else None
        rid = rid or f[:-5]
        rpath = os.path.join(IO, "receipts", rid + ".json")
        if not os.path.exists(rpath):
            if rid in by_rid:
                out = dict(receipt_of(by_rid[rid]), replayed=True)    # 落帳後、回條前死過：照事件補
            elif not isinstance(req, dict):
                out = {"ok": False, "why": "讀不懂的請求"}
            else:
                out = handle(dict(req, request_id=rid))
            out.update(request_id=rid, op=(req or {}).get("op") if isinstance(req, dict) else None,
                       revision=len(events), at=fs.now())
            fs.write_json(rpath, out)
        try:
            os.remove(os.path.join(RQ, f))        # 回條寫好才刪請求
        except OSError:
            pass
    time.sleep(0.02)
