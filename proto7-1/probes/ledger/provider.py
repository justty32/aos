"""ledger 探針的 mock 模型服務（keep 任務，node `provider`）：P、Q 共用。不打任何 LLM。

收 `provider/io/requests/*.json`＝{attempt_id, res_id, executor, work_id, want}，寫 `provider/io/receipts/<attempt_id>.json`。
執行前查帳本發布的 `mnt/bank/reservations/<res_id>.json`：要是 reserved、而且 claim 它的 attempt 就是這一筆，否則不做。
付錢的是帳本上那筆保留額的 root（不看請求自己寫的）。用量＝min(want, 保留額)。
副作用記在 `provider/executed.jsonl`（跟程序分開）：重起後已在帳上的照帳補回條，不再執行。

故障鈕 `provider/fault.json`：{"hold": [attempt_id...]}＝這些先不做（外部延遲）；{"crash_after_exec": attempt_id}＝做完、回條前卡住。
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))
import aos7_fs as fs  # noqa: E402

E = fs.task_env()
NODE = E["node"]
IO = os.path.join(NODE, "io")
EXEC = os.path.join(NODE, "executed.jsonl")
BANK = os.path.join(E["task"], "mnt", "bank")
RQ = os.path.join(IO, "requests")
os.makedirs(RQ, exist_ok=True)
os.makedirs(os.path.join(IO, "receipts"), exist_ok=True)
print("up", E["tid"], flush=True)

while True:
    fault = fs.read_json(os.path.join(NODE, "fault.json"), {}) or {}
    done = {e["attempt_id"]: e for e in fs.read_jsonl(EXEC)}
    for f in sorted(x for x in os.listdir(RQ) if x.endswith(".json") and not x.startswith(".")):
        req = fs.read_json(os.path.join(RQ, f))
        if not isinstance(req, dict) or not req.get("attempt_id"):
            continue
        aid = req["attempt_id"]
        rpath = os.path.join(IO, "receipts", aid + ".json")
        if os.path.exists(rpath):
            continue
        if aid in done:
            ex = done[aid]
            fs.write_json(rpath, {"attempt_id": aid, "state": "done", "used": ex["used"], "payer": ex["payer"],
                                  "recovered": True, "at": fs.now()})
            continue
        if aid in (fault.get("hold") or []):
            continue
        rv = fs.read_json(os.path.join(BANK, "reservations", "%s.json" % req.get("res_id")))
        if not isinstance(rv, dict) or rv.get("state") != "reserved" or rv.get("attempt_id") != aid:
            fs.write_json(rpath, {"attempt_id": aid, "state": "not_executed", "used": 0, "at": fs.now(),
                                  "why": "帳本上 %s 不是被這個 attempt claim 的保留額（%s）；沒執行"
                                         % (req.get("res_id"), (rv or {}).get("attempt_id"))})
            continue
        used = min(int(req.get("want", 0)), rv["tokens"])
        fs.append_jsonl(EXEC, {"attempt_id": aid, "res_id": rv["res_id"], "payer": rv["root"], "context": rv["cid"],
                               "executor": req.get("executor"), "claimed_by": rv.get("executor"),
                               "work_id": req.get("work_id"), "used": used, "at": fs.now()})
        if fault.get("crash_after_exec") == aid:
            print("hang after exec", aid, flush=True)
            while True:
                time.sleep(1)
        fs.write_json(rpath, {"attempt_id": aid, "state": "done", "used": used, "payer": rv["root"],
                              "recovered": False, "at": fs.now()})
    time.sleep(0.02)
