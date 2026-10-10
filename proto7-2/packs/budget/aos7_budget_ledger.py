"""budget 帳服務端：開帳、轉移、收請求、回條回收與主迴圈。"""
import fcntl
import os
import time

from aos7_fs import (
    BAD, N, OK, U, fact, is_int, locked, now, sweep_tmp, write_json,
)

from aos7_budget_common import (
    ID_RE, POLL, ORPHAN_ROUNDS, sha, kid_of, digest_of, test_crash, completed_tock, grant_issue, is_child,
    load_grant, judge,
)

# ---------- 帳（spec §3） ----------

def ledger_issue(L):
    if not isinstance(L, dict):
        return "ledger.json 不是物件"
    for k in ("initial", "available", "inflight", "used", "seq"):
        if not is_int(L.get(k)):
            return "ledger.%s 不是整數" % k
    if not isinstance(L.get("ops"), dict) or not isinstance(L.get("log"), list):
        return "ledger.json 缺 ops／log"
    return None


def read_ledger(bud):
    """回 (帳 或 None, 說明)。不存在、讀不到、壞都是 None：不受理（不當空帳）。"""
    st, L = fact(bud.p("ledger.json"))
    if st != OK:
        return None, "ledger.json %s" % ("不存在（要先 init）" if st == N else L)
    issue = ledger_issue(L)
    return (None, issue) if issue else (L, None)


def init(bud):
    """開帳（spec §3）：回 (ok, 說明)。帳已存在、grant 不合、子 grant＝拒絕。"""
    g, gs, why = load_grant(bud)
    if g is None:
        return False, why
    issue = grant_issue(g, bud.id) if ID_RE.match(bud.id) else "預算名要是英數、_、-，最多 32 字"
    if issue:
        return False, issue
    if is_child(g):
        return False, "子 grant（parent／delegate）v1 不支援，拒絕開帳"
    with locked(bud.p("ledger.json")):
        if fact(bud.p("ledger.json"))[0] != N:
            return False, "ledger.json 已存在（或讀不到），不重開"
        write_json(bud.p("ledger.json"), {
            "v": 1, "budget": bud.id, "grant": g["grant"], "grant_sha": gs, "initial": g["amount"],
            "available": g["amount"], "inflight": 0, "used": 0, "clock_hw": None, "seq": 0, "ops": {}, "log": [],
            "at": now()})
    return True, None


def receipt_from(op, rec):
    """帳上 K 的紀錄 → 這個操作的回條（重播與首次都走這裡，所以同 K 同操作的回條一樣）。"""
    if op == "reserve":
        return {"result": rec["stage"], "kid": kid_of(rec["key"]), "amount": rec["amount"],
                "reserve": rec["reserve"], "settle": rec.get("settle")}
    if rec["stage"] != "settled":
        return {"result": "unknown", "why": "還沒結算"}
    return {"result": "settled", "kid": kid_of(rec["key"]), "amount": rec["amount"], "settle": rec["settle"]}


def transition(L, op, kid, amount, used, c, overrun=None):
    """改餘額並記一筆 log（呼叫的人接著一次寫入整份帳）。"""
    if op == "reserve":
        L["available"] -= amount
        L["inflight"] += amount
    else:
        L["inflight"] -= amount
        L["used"] += used
        L["available"] += amount - used
    L["seq"] += 1
    L["log"].append({"seq": L["seq"], "op": op, "kid": kid, "amount": amount, "used": used,
                     "available": L["available"], "inflight": L["inflight"], "used_total": L["used"],
                     "tock": c, "at": now()})
    if overrun is not None:
        L["log"][-1]["overrun"] = overrun
    return L["seq"]


def gateway_terminal(bud, kid):
    """帳自己讀入口紀錄（settle 的證據）：回 (終局回條 或 None, 雜湊 或 說明)。"""
    st, r = fact(bud.p("gateway", kid + ".json"))
    if st != OK:
        return None, "入口沒有 K 的紀錄" if st == N else "入口紀錄讀不到：%s" % r
    if not isinstance(r, dict) or r.get("stage") != "done":
        return None, "入口紀錄不是終局（stage %r）" % (r.get("stage") if isinstance(r, dict) else None)
    if "billing" in r and r["billing"] not in ("final", "overrun"):
        return None, "入口紀錄 billing pending（%r）" % r["billing"]
    if not is_int(r.get("used")):
        return None, "入口紀錄的 used 不是整數"
    return r, sha(r)


def handle(bud, req):
    """處理一件請求，回回條內容；需要時一次寫入帳（spec §3）。帳讀不到丟 LedgerDown（請求留著）。"""
    op, key = req.get("op"), req.get("key")
    if op not in ("reserve", "settle") or not isinstance(key, dict) \
            or not all(isinstance(key.get(k), str) for k in ("budget", "holder", "request")):
        return {"result": "bad", "why": "請求格式不對"}
    if key["budget"] != bud.id:
        return {"result": "denied", "why": "預算不符"}
    kid = kid_of(key)
    with locked(bud.p("ledger.json")):
        L, why = read_ledger(bud)
        if L is None:
            raise LedgerDown(why)
        c = completed_tock(bud.node)    # 時鐘水位：每次讀到合法 c 就推高（含拒絕與重播），只動 clock_hw
        if is_int(c) and not (is_int(L.get("clock_hw")) and c <= L["clock_hw"]):
            L["clock_hw"] = c
            write_json(bud.p("ledger.json"), L)
        rec = L["ops"].get(kid)
        if op == "reserve":
            content = req.get("content")
            if not isinstance(content, dict) or not is_int(content.get("amount")) or content["amount"] <= 0:
                return {"result": "bad", "why": "content.amount 要是正整數"}
            digest = digest_of(key, content)
            if rec is not None:
                if rec["digest"] != digest:
                    return {"result": "conflict", "why": "同一個 K 已用不同內容預留"}
                return receipt_from(op, rec)
            st, r = fact(bud.p("retired.json"))           # 退役（spec「保存與退役」）：新 K 一律不收
            if st != N:
                return {"result": "denied" if st == OK else "unknown", "why": "預算已退役" if st == OK else
                        "retired.json 讀不到：%s" % r}
            verdict, why, c = judge(bud, key["holder"], content.get("resource"), content.get("gateway"), L)
            if verdict != "ok":
                return {"result": verdict, "why": why}
            amount = content["amount"]
            if L["available"] < amount:
                return {"result": "denied", "why": "額度不足（可用 %d < %d）" % (L["available"], amount)}
            test_crash(bud, "reserve-before-commit")
            rec = {"key": key, "digest": digest, "content": content, "amount": amount, "stage": "reserved"}
            L["clock_hw"] = max(c, L["clock_hw"]) if is_int(L.get("clock_hw")) else c
            rec["reserve"] = {"seq": transition(L, "reserve", kid, amount, None, c), "tock": c, "at": now()}
            L["ops"][kid] = rec
            write_json(bud.p("ledger.json"), L)
            test_crash(bud, "reserve-after-commit")
            return receipt_from(op, rec)
        # settle
        if rec is None:
            return {"result": "unknown", "why": "帳上沒有這個 K 的預留"}
        if rec["stage"] == "settled":
            return receipt_from(op, rec)
        g, ev = gateway_terminal(bud, kid)
        if g is None:
            return {"result": "unknown", "why": ev + "；預留留著"}
        if g.get("key") != rec["key"]:
            return {"result": "unknown", "why": "入口回條的 key 跟預留不同"}
        if g.get("digest") != rec["digest"] and not (
                g.get("outcome") == "cancelled" and g["used"] == 0 and "digest" in g and g["digest"] is None):
            return {"result": "unknown", "why": "入口回條的 digest 跟預留不同"}
        used = g["used"]
        if not 0 <= used <= rec["amount"]:
            return {"result": "unknown", "why": "入口回條的 used %r 跟預留 %r 對不上" % (used, rec["amount"])}
        overrun = g.get("overrun", 0)
        if not is_int(overrun) or overrun < 0:
            return {"result": "unknown", "why": "入口回條的 overrun 要是非負整數"}
        test_crash(bud, "settle-before-commit")
        rec["stage"] = "settled"
        rec["settle"] = {"seq": transition(L, "settle", kid, rec["amount"], used, None, overrun),
                         "used": used, "overrun": overrun,
                         "outcome": g.get("outcome"), "evidence": ev, "at": now()}
        L["overrun"] = L.get("overrun", 0) + overrun
        write_json(bud.p("ledger.json"), L)
        test_crash(bud, "settle-after-commit")
        return receipt_from(op, rec)


class LedgerDown(Exception):
    """帳讀不到或壞掉：這一件不處理、請求留著。"""


def process_inbox(bud):
    """帳任務的一輪：逐件處理 inbox/，先寫回條再刪請求。回處理了幾件；帳讀不到就記 error.json、停在這輪。"""
    inbox = bud.p("inbox")
    try:
        names = sorted(n for n in os.listdir(inbox) if n.endswith(".json") and not n.startswith("."))
    except OSError:
        return 0
    n = 0
    for name in names:
        path = os.path.join(inbox, name)
        st, req = fact(path)
        if st == N:
            continue
        if st == U:
            continue                       # 讀不到：留著，下輪再看
        try:
            rcpt = {"result": "bad", "why": "請求不是 JSON"} if st == BAD or not isinstance(req, dict) \
                else handle(bud, req)
        except LedgerDown as e:
            write_json(bud.p("error.json"), {"kind": "ledger", "where": name, "why": str(e), "at": now()})
            return n
        rcpt.update(op=(req or {}).get("op") if isinstance(req, dict) else None, at=now())
        write_json(bud.p("receipts", name), rcpt)
        os.unlink(path)
        n += 1
    return n


def sweep_receipts(bud, seen, c):
    """掃孤兒回條（spec §9）：K 已結算、inbox/ 沒有同名請求、帳看到它之後本 node 又完成 ORPHAN_ROUNDS 回合仍在＝等的人已不在，刪。
    seen＝{回條名: 第一次看到時的 c}（帳任務記憶體裡，重開從頭算）。重播由帳上 ops 重建同一回條，所以刪了也不丟東西。"""
    try:
        names = [n for n in os.listdir(bud.p("receipts")) if n.endswith(".json") and not n.startswith(".")]
    except OSError:
        return 0
    L = read_ledger(bud)[0]
    gone = 0
    for name in set(seen) - set(names):
        del seen[name]
    for name in names:
        rec = L and L["ops"].get(name.split(".", 1)[0])
        if c is None or not rec or rec["stage"] != "settled" or os.path.exists(bud.p("inbox", name)):
            seen.pop(name, None)
        elif c - seen.setdefault(name, c) >= ORPHAN_ROUNDS:
            try:
                os.unlink(bud.p("receipts", name))
                gone += 1
            except OSError:
                pass
    return gone


def serve(bud):
    """帳任務本體：拿 `ledger.lock`（防舊代殘留雙寫；拿不到就等），之後每 POLL 秒處理一次 inbox/；本 node 回合變了就掃一次孤兒回條。"""
    os.makedirs(bud.p("inbox"), exist_ok=True)
    with open(bud.p("ledger.lock"), "a") as lk:
        while True:
            try:
                fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                time.sleep(0.2)
        for d in (bud.dir, bud.p("inbox"), bud.p("receipts"), bud.p("gateway")):
            sweep_tmp(d)
        seen, last = {}, False
        while True:
            process_inbox(bud)
            c = completed_tock(bud.node)
            if c != last:
                last = c
                sweep_receipts(bud, seen, c)
            time.sleep(POLL)


