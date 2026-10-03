"""ledger 探針的 worker（spawn 起的一次性任務）：照 `<node>/jobs/<job>.json` 做一筆付費呼叫。

    python3 worker.py <job>
工作單：{"job", "context", "tokens", "want", "res_id"?（拿到的 grant，就不自己 reserve）, "attempt",
        "executor"?（不寫＝自己的 node:tid）, "hang_at"?（"after_settle_sent"：送出 settle 後卡住，給探針 kill）}
步驟：reserve → claim → 呼叫 provider → 等 provider 回條 → settle。每步的 request_id 固定（<job>-reserve…），
進度存 `<node>/jobs/<job>.state.json`；被 kill 後新 worker 從那裡接著做，**重送同一個 request_id**，不開新帳。
經 mnt/bank（帳本 io）、mnt/prov（provider io）。
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))
import aos7_fs as fs  # noqa: E402

E = fs.task_env()
JOB = sys.argv[1]
JD = os.path.join(E["node"], "jobs")
spec = fs.read_json(os.path.join(JD, JOB + ".json"), {}) or {}
SP = os.path.join(JD, JOB + ".state.json")
st = fs.read_json(SP, {}) or {}
BANK = os.path.join(E["task"], "mnt", "bank")
PROV = os.path.join(E["task"], "mnt", "prov")
ME = spec.get("executor") or "%s:%s" % (E["node_id"], E["tid"])


def log(ev, **kw):
    kw.update(ev=ev, by="%s:%s" % (E["node_id"], E["tid"]), at=fs.now())
    fs.append_jsonl(os.path.join(JD, JOB + ".log.jsonl"), kw)


def save(**kw):
    st.update(kw)
    fs.write_json(SP, st)


def wait(path):
    while True:
        o = fs.read_json(path)
        if isinstance(o, dict):
            return o
        time.sleep(0.02)


def bank(op, **kw):
    """送帳本請求（同一 request_id；已有回條就直接用），等回條。"""
    rid = "%s-%s" % (JOB, op)
    rp = os.path.join(BANK, "receipts", rid + ".json")
    rec = fs.read_json(rp)
    if not isinstance(rec, dict):
        fs.write_json(os.path.join(BANK, "requests", rid + ".json"), dict(kw, op=op, request_id=rid))
        log("send", op=op, request_id=rid, resend=bool(st.get("sent_" + op)))
        save(**{"sent_" + op: True})
        if op == "settle" and spec.get("hang_at") == "after_settle_sent":
            log("hang", at_step="after_settle_sent")
            while True:
                time.sleep(1)
        rec = wait(rp)
    log("receipt", op=op, request_id=rid, ok=rec.get("ok"), why=rec.get("why"))
    if not rec.get("ok"):
        save(step="rejected", why=rec.get("why"), op=op)
        sys.exit(0)
    return rec


log("start", state=st.get("step"))
if st.get("step") in ("done", "rejected"):
    sys.exit(0)
res_id = spec.get("res_id") or st.get("res_id")
if not res_id:
    res_id = bank("reserve", context=spec["context"], tokens=spec["tokens"])["res_id"]
save(res_id=res_id, step="reserved")
bank("claim", res_id=res_id, attempt_id=spec["attempt"], executor=ME)
save(step="claimed")
pr = os.path.join(PROV, "receipts", spec["attempt"] + ".json")
if not os.path.exists(pr):
    fs.write_json(os.path.join(PROV, "requests", spec["attempt"] + ".json"),
                  {"attempt_id": spec["attempt"], "res_id": res_id, "executor": ME, "work_id": spec["job"],
                   "want": spec["want"]})
    log("call", attempt_id=spec["attempt"], resend=bool(st.get("called")))
    save(called=True, step="calling")
prec = wait(pr)
save(step="provider_done", provider=prec.get("state"), used=prec.get("used"))
rec = bank("settle", res_id=res_id, attempt_id=spec["attempt"])
save(step="done", used=rec.get("used"))
log("done", used=rec.get("used"))
