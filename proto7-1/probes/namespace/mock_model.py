"""namespace 探針的 mock 模型服務（keep 任務，跑在服務自己的 node）：不打任何 LLM，回固定結果。

設定 `<node>/service.cfg.json`：{"service_id", "interface", "clients": ["reviewer", ...]}
每次起來 instance_epoch +1（`<node>/epoch.json`），對每個客戶寫服務卡 `clients/<c>/service.json`。
處理 `clients/<c>/requests/*.json`、寫 `clients/<c>/receipts/<request_id>.json`。
副作用（「模型真的被呼叫」）記在 `<node>/executed.jsonl`：跟程序分開、不會跟著服務一起丟。
重起後先對帳：請求已在 executed.jsonl（做完、回條沒寫就死了）→ 照帳補回條，不再執行一次。

故障鈕 `<node>/fault.json`：{"hold": true}＝不處理新請求（後端很慢）；{"crash_after_exec": request_id}＝執行完那筆、
寫回條前卡住（給探針 kill，模擬死在兩步之間）。
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))
import aos7_fs as fs  # noqa: E402

E = fs.task_env()
NODE = E["node"]
cfg = fs.read_json(os.path.join(NODE, "service.cfg.json"), {}) or {}
SID, IFACE = cfg["service_id"], cfg["interface"]
n = fs.edit_json(os.path.join(NODE, "epoch.json"), lambda o: {"epoch": (o or {}).get("epoch", 0) + 1})["epoch"]
EPOCH = "%s-%d" % (SID, n)
EXEC = os.path.join(NODE, "executed.jsonl")

CARD = {
    "schema": "aos.service-card.v1",
    "service_id": SID,
    "interface": IFACE,
    "instance_epoch": EPOCH,
    "submit": "requests/<request_id>.json",
    "receipt": "receipts/<request_id>.json",
    "request_fields": ["request_id", "interface", "work_id", "charge_context", "expected_service_epoch", "input"],
    "operations": ["submit", "query"],
    "charging": "caller_context",
    "dedup": "request_id：同一個 request_id 只執行一次；重起後照 executed 帳補回條，不重做",
    "completion": "receipt.state == settled（rejected＝沒執行）",
    "why": "提交後查回條；請求檔寫成功不表示模型已回答",
}
for c in cfg.get("clients", []):
    d = os.path.join(NODE, "clients", c)
    os.makedirs(os.path.join(d, "requests"), exist_ok=True)
    os.makedirs(os.path.join(d, "receipts"), exist_ok=True)
    fs.write_json(os.path.join(d, "service.json"), CARD)
print("up", EPOCH, flush=True)


def executed():
    return {e["request_id"]: e for e in fs.read_jsonl(EXEC)}


while True:
    fault = fs.read_json(os.path.join(NODE, "fault.json"), {}) or {}
    done = executed()
    for c in cfg.get("clients", []):
        d = os.path.join(NODE, "clients", c)
        try:
            names = sorted(x for x in os.listdir(os.path.join(d, "requests")) if x.endswith(".json") and not x.startswith("."))
        except OSError:
            continue
        for f in names:
            req = fs.read_json(os.path.join(d, "requests", f))
            if not isinstance(req, dict):
                continue
            rid = req.get("request_id") or f[:-5]
            rpath = os.path.join(d, "receipts", rid + ".json")
            if os.path.exists(rpath):
                continue                                   # 已回條：同一 request_id 再送也不做
            base = {"request_id": rid, "service_id": SID, "receipt_epoch": EPOCH,
                    "charge_context": req.get("charge_context"), "at": fs.now()}
            if rid in done:                                # 做完、回條沒寫就死了：照帳補，不重做
                ex = done[rid]
                fs.write_json(rpath, dict(base, state="settled", result=ex["result"], executed_epoch=ex["epoch"],
                                          recovered=True))
                continue
            if req.get("interface") != IFACE:
                fs.write_json(rpath, dict(base, state="rejected",
                                          why="介面不合：這個服務是 %s，請求寫 %r；沒執行" % (IFACE, req.get("interface"))))
                continue
            if fault.get("hold"):
                continue
            result = "%s 審過 %s：%s" % (SID, req.get("work_id"), (req.get("input") or "")[:40])
            fs.append_jsonl(EXEC, {"request_id": rid, "work_id": req.get("work_id"), "client": c, "epoch": EPOCH,
                                   "expected_epoch": req.get("expected_service_epoch"),
                                   "charge_context": req.get("charge_context"), "result": result, "at": fs.now()})
            done[rid] = {"result": result, "epoch": EPOCH}
            if fault.get("crash_after_exec") == rid:
                print("hang after exec", rid, flush=True)
                while True:                                # 卡在「做完、還沒回條」：等探針 kill
                    time.sleep(1)
            fs.write_json(rpath, dict(base, state="settled", result=result, executed_epoch=EPOCH, recovered=False))
    time.sleep(0.02)
