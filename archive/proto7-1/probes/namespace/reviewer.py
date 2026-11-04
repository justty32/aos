"""namespace 探針的 reviewer（keep 任務）：兩個專案跑同一份程式、同一個 argv，只認自己任務資料夾裡的掛載點。

    mnt/mail     收工作信（`*.json`＝{"work_id", "charge_context", "body"}），做完搬到 mail/done/
    mnt/model    模型服務：先讀 service.json（服務卡），照卡上的 submit／receipt 送件、查回條
    mnt/context  專案脈絡：checkpoint.json（在途請求）、results/、reviewer.jsonl（流水）、reviewer-status.json
    mnt/model-prev（可選）  換服務時舊服務的位置：只用來收舊請求的尾，不送新件

規則：只會 `llm-submit.v1`；卡上的介面不合就寫可讀的拒絕、不送件。請求先記進 checkpoint 再送；
重起後在途的請求**不重送**（同一個 request_id 只在請求檔不見時補寫同一份），等回條。
在途請求送去的服務現在看不到（掛載換了）＝unknown：不重送、不當沒做，記進 status。
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))
import aos7_fs as fs  # noqa: E402

IFACE = "llm-submit.v1"
E = fs.task_env()
M = os.path.join(E["task"], "mnt")
MAIL, MODEL, CTX, PREV = (os.path.join(M, x) for x in ("mail", "model", "context", "model-prev"))
CP = os.path.join(CTX, "checkpoint.json")
ME = "%s:%s" % (E["node_id"], E["tid"])


def log(ev, **kw):
    kw.update(ev=ev, by=ME, at=fs.now(), t=time.time())
    fs.append_jsonl(os.path.join(CTX, "reviewer.jsonl"), kw)


def status(**kw):
    kw.update(by=ME, at=fs.now())
    old = fs.read_json(os.path.join(CTX, "reviewer-status.json"), {}) or {}
    if {k: v for k, v in old.items() if k != "at"} != {k: v for k, v in kw.items() if k != "at"}:
        fs.write_json(os.path.join(CTX, "reviewer-status.json"), kw)


cp = fs.read_json(CP, {}) or {}
cp.setdefault("pending", {})
cp.setdefault("done", {})
log("start", pending=sorted(cp["pending"]), restart_of=(fs.read_json(os.path.join(E["task"], "birth.json"), {}) or {}).get("restart_of"))
seen_card = None
said_unknown = set()

while True:
    time.sleep(0.03)
    card = fs.read_json(os.path.join(MODEL, "service.json"))
    if not isinstance(card, dict):
        status(state="waiting", why="mnt/model/service.json 還沒有服務卡")
        continue
    key = (card.get("service_id"), card.get("instance_epoch"), card.get("interface"))
    if key != seen_card:
        log("card", service_id=key[0], epoch=key[1], interface=key[2], prev=seen_card and list(seen_card))
        seen_card = key
    if card.get("interface") != IFACE:
        status(state="rejected", service_id=card.get("service_id"), interface=card.get("interface"),
               why="mnt/model 的服務介面是 %r，我只會 %s；不送件，等掛載換回相容的服務" % (card.get("interface"), IFACE))
        continue
    prev = fs.read_json(os.path.join(PREV, "service.json"))
    where = {card["service_id"]: MODEL}
    if isinstance(prev, dict) and prev.get("service_id") and prev.get("service_id") not in where:
        where[prev["service_id"]] = PREV
    unknown = []
    for rid, p in sorted(cp["pending"].items()):
        base = where.get(p["service_id"])
        if base is None:
            unknown.append(rid)
            if rid not in said_unknown:
                said_unknown.add(rid)
                log("unknown", request_id=rid, service_id=p["service_id"],
                    why="送去的服務現在沒掛著，看不到回條；不重送、不當沒做")
            continue
        rec = fs.read_json(os.path.join(base, "receipts", rid + ".json"))
        if isinstance(rec, dict) and rec.get("state") in ("settled", "rejected"):
            job = p["job"]
            if rec["state"] == "settled":
                fs.write_json(os.path.join(CTX, "results", job + ".json"),
                              {"work_id": p["work_id"], "request_id": rid, "result": rec.get("result"),
                               "service_id": rec.get("service_id"), "executed_epoch": rec.get("executed_epoch"),
                               "recovered": rec.get("recovered"), "by": ME})
                try:
                    os.makedirs(os.path.join(MAIL, "done"), exist_ok=True)
                    os.replace(os.path.join(MAIL, job + ".json"), os.path.join(MAIL, "done", job + ".json"))
                except OSError:
                    pass
            cp["done"][job] = {"request_id": rid, "state": rec["state"]}
            del cp["pending"][rid]
            fs.write_json(CP, cp)
            log("receipt", request_id=rid, state=rec["state"], via="model" if base == MODEL else "model-prev",
                recovered=rec.get("recovered"), executed_epoch=rec.get("executed_epoch"))
        elif not os.path.exists(os.path.join(base, "requests", rid + ".json")):
            fs.write_json(os.path.join(base, "requests", rid + ".json"), p["request"])   # 同一份、同一個 id
            log("resend-same-id", request_id=rid)
    try:
        letters = sorted(x for x in os.listdir(MAIL) if x.endswith(".json") and not x.startswith("."))
    except OSError:
        letters = []
    busy = {p["job"] for p in cp["pending"].values()}
    for f in letters:
        job = f[:-5]
        if job in cp["done"] or job in busy:
            continue
        mail = fs.read_json(os.path.join(MAIL, f))
        if not isinstance(mail, dict) or not mail.get("work_id"):
            continue
        rid = mail["work_id"] + "-call-1"
        req = {"schema": "aos.service-request.v1", "request_id": rid, "interface": IFACE, "operation": "submit",
               "expected_service_epoch": card.get("instance_epoch"), "charge_context": mail.get("charge_context"),
               "work_id": mail["work_id"], "input": mail.get("body", ""), "reply_key": rid}
        cp["pending"][rid] = {"job": job, "work_id": mail["work_id"], "service_id": card["service_id"],
                              "epoch": card.get("instance_epoch"), "request": req}
        fs.write_json(CP, cp)                                    # 先記在途，再送件
        fs.write_json(os.path.join(MODEL, "requests", rid + ".json"), req)
        log("submit", request_id=rid, service_id=card["service_id"], epoch=card.get("instance_epoch"))
    if unknown:
        status(state="blocked", unknown=unknown, service_id=card["service_id"],
               why="這些請求送去的服務現在看不到（掛載換了），不知道做了沒：不重送；要收尾請把舊服務掛到 mnt/model-prev")
    else:
        status(state="ok", service_id=card["service_id"], epoch=card.get("instance_epoch"),
               pending=sorted(cp["pending"]))
