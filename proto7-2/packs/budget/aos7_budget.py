"""budget 任務包：grant 判定、時鐘、帳（ledger）與命令列（spec 見同資料夾的 spec.md；契約卡在 README.md）。

    aos7-budget init <預算>                         照 grant.json 開帳
    aos7-budget ledger <預算>                       帳任務（普通 keep，max_live 1）：處理 inbox/ 的請求
    aos7-budget call <預算> --holder H --request R  包裝程式：reserve → 入口 run → settle（在 aos7_budget_gate.py）
    aos7-budget cancel|settle|status <預算> ...     人手指令

預算資料夾＝`<node>/budget/<id>/`。只用核心公開的檔：round.json（completed_tock）；核心不知道這個包。
"""
import argparse
import hashlib
import json
import os
import re
import signal
import sys
import time
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
TOP = os.path.dirname(os.path.dirname(HERE))           # proto7-2/
sys.path[:0] = [os.path.join(TOP, "lib")]
from aos7_fs import (BAD, N, OK, ROUND_CLOSED, ROUND_OPEN, U, fact, is_int, locked, now,  # noqa: E402
                     read_round, sweep_tmp, write_json)

ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
CLOCK = "completed_tock"
GATEWAY = "fakeapi"                 # call 包裝程式的入口（假 API）
PARTIAL_SETTLE = True
RESOURCE = "fakeapi.calls"
GRANT_FIELDS = ("grant", "budget", "holder", "resource", "gateway", "amount", "clock", "from", "until", "delegate")
POLL = 0.02
ORPHAN_ROUNDS = 3                   # 孤兒回條：帳看到它之後本 node 再完成這麼多回合仍沒人讀走才刪（spec §9）


# ---------- 共用 ----------

class Bud:
    """一個預算資料夾 `<node>/budget/<id>/` 的路徑。"""

    def __init__(self, path):
        self.dir = os.path.abspath(path)
        self.id = os.path.basename(self.dir)
        self.node = os.path.dirname(os.path.dirname(self.dir))

    def p(self, *a):
        return os.path.join(self.dir, *a)


def sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def make_key(budget, holder, request):
    return {"budget": budget, "holder": holder, "request": request}


def kid_of(key):
    """業務鍵 K＝(budget, holder, request) 的檔名用識別。"""
    return sha([key["budget"], key["holder"], key["request"]])[:20]


def digest_of(key, content):
    """同一個 K 的業務內容雜湊：attempt、slot#run 等傳輸資訊不在裡面（藍圖 §3 操作去重）。"""
    return sha({"key": key, "content": content})


def test_crash(bud, point):
    """測試用的 SIGKILL 點（spec §7）：預算資料夾有 `.crash` 寫著這個點就刪檔、殺掉。

    在任務裡（有 AOS7_TASK）殺整個程序群組，模擬槽被收（包裝程式的結果就不會寫）；否則只殺自己。"""
    path = bud.p(".crash")
    try:
        with open(path) as f:
            want = f.read().strip()
    except OSError:
        return
    if want != point:
        return
    os.unlink(path)
    if os.environ.get("AOS7_TASK"):
        os.killpg(os.getpgid(0), signal.SIGKILL)
    os.kill(os.getpid(), signal.SIGKILL)


# ---------- 時鐘與 grant（spec §2） ----------

def completed_tock(node):
    """本 node 的 completed_tock：round.json closed 取 round、open 取 round−1；其餘（不存在、讀不到、壞）＝None 未知。"""
    st, r, _ = read_round(os.path.join(node, ".aos", "round.json"))
    if st == ROUND_CLOSED:
        return r["round"]
    if st == ROUND_OPEN:
        return r["round"] - 1
    return None


def grant_issue(g, budget_id):
    """grant 內容的問題（None＝格式合）。子 grant 另由 judge 判 denied。"""
    if not isinstance(g, dict):
        return "grant 不是物件"
    miss = [k for k in GRANT_FIELDS if k not in g]
    if miss:
        return "grant 缺欄 %s" % miss
    for k in ("amount", "from", "until"):
        if not is_int(g[k]) or g[k] < 0:
            return "grant.%s 要是非負整數" % k
    if g["from"] > g["until"]:
        return "grant.from 大於 until"
    if g["clock"] != CLOCK:
        return "grant.clock 只准 %s（v1 只有本 node 的回合）" % CLOCK
    if g["budget"] != budget_id:
        return "grant.budget %r 跟預算資料夾 %r 不同" % (g["budget"], budget_id)
    return None


def is_child(g):
    """子 grant（v1 不支援再分）：帶 parent，或 delegate 不是 false。"""
    return "parent" in g or g.get("delegate") is not False


def load_grant(bud):
    """回 (grant 或 None, 雜湊 或 None, 說明)。讀不到、壞＝None（未知，不是沒有限制）。"""
    st, g = fact(bud.p("grant.json"))
    if st != OK:
        return None, None, "grant.json %s" % ("不存在" if st == N else g)
    return g, sha(g), None


def judge(bud, holder, resource, gateway, ledger):
    """grant 判定（spec §2）：回 (ok|denied|not_yet|unknown, 說明, c)。ledger 給帳的內容（比 grant 雜湊與 clock_hw）。"""
    g, gs, why = load_grant(bud)
    if g is None:
        return "unknown", why, None
    if gs != ledger.get("grant_sha"):
        return "unknown", "grant.json 跟開帳時不同（發行者給的應是固定內容）", None
    issue = grant_issue(g, bud.id)
    if issue:
        return "unknown", issue, None
    if is_child(g):
        return "denied", "子 grant（parent／delegate）v1 不支援", None
    for k, v in (("holder", holder), ("resource", resource), ("gateway", gateway)):
        if g[k] != v:
            return "denied", "%s 不符：grant 是 %r，請求是 %r" % (k, g[k], v), None
    c = completed_tock(bud.node)
    if c is None:
        return "unknown", "時鐘未知（round.json 沒有合法值）", None
    if is_int(ledger.get("clock_hw")) and c < ledger["clock_hw"]:
        return "unknown", "時鐘倒退（c=%d < 帳看過的 %d）" % (c, ledger["clock_hw"]), c
    if c < g["from"]:
        return "not_yet", "還沒生效（c=%d < from=%d）" % (c, g["from"]), c
    if c >= g["until"]:
        return "denied", "已到期（c=%d ≥ until=%d）" % (c, g["until"]), c
    return "ok", None, c


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
    import fcntl
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


# ---------- 請求端（包裝程式與人手指令共用） ----------

def submit(bud, op, key, content=None):
    """寫一份請求到 inbox/，回回條路徑。"""
    name = "%s.%s.%s.json" % (kid_of(key), op, uuid.uuid4().hex[:12])
    req = {"op": op, "key": key, "at": now()}
    if content is not None:
        req.update(content=content, digest=digest_of(key, content))
    write_json(bud.p("inbox", name), req)
    return bud.p("receipts", name)


def await_receipt(bud, path, patience):
    """等回條：回回條內容；completed_tock 比開始時多 patience 回合還沒有＝None（時鐘未知或 pause 時不到期）。讀完刪回條。"""
    start = completed_tock(bud.node)
    while True:
        st, r = fact(path)
        if st == OK and isinstance(r, dict):
            try:
                os.unlink(path)
            except OSError:
                pass
            return r
        c = completed_tock(bud.node)
        if start is None:
            start = c
        elif c is not None and c - start >= patience:
            return None
        time.sleep(POLL)


def ask(bud, op, key, content=None, patience=5):
    r = await_receipt(bud, submit(bud, op, key, content), patience)
    return r if r is not None else {"result": "unknown", "why": "等了 %d 回合帳沒回條（請求留著，帳之後照樣處理）"
                                    % patience}


def status(bud, key=None):
    """帳的摘要；給了 key 就印那個 K 的階段、預留、入口證據與結算。"""
    L, why = read_ledger(bud)
    if L is None:
        return {"error": why}
    if key is None:
        return {k: L.get(k) for k in ("budget", "grant", "initial", "available", "inflight", "used", "seq",
                                      "clock_hw")} | {"keys": len(L["ops"]), "overrun": L.get("overrun", 0)}
    kid = kid_of(key)
    rec = L["ops"].get(kid)
    gw = fact(bud.p("gateway", kid + ".json"))[1]
    return {"kid": kid, "key": key, "stage": rec and rec["stage"], "ledger": rec, "gateway": gw}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="aos7-budget", description="budget 任務包：grant／帳／入口")
    ap.add_argument("cmd", choices=("init", "ledger", "call", "cancel", "settle", "status"))
    ap.add_argument("bud", help="預算資料夾（<node>/budget/<id>）")
    ap.add_argument("--holder")
    ap.add_argument("--request")
    ap.add_argument("--amount", type=int, default=1)
    ap.add_argument("--resource", default=RESOURCE)
    ap.add_argument("--payload", help="給假後端的 JSON 檔（mode: ok／fail／reject）")
    ap.add_argument("--out", help="call 的結果另存一份（原子寫）")
    ap.add_argument("--patience", type=int, default=5, help="等帳回條最多幾個本 node 回合")
    a = ap.parse_args(argv)
    bud = Bud(a.bud)
    if a.cmd == "init":
        ok, why = init(bud)
        print(json.dumps({"ok": ok, "why": why}, ensure_ascii=False))
        return 0 if ok else 1
    if a.cmd == "ledger":
        serve(bud)
        return 0
    key = None
    if a.holder is not None or a.request is not None:
        if not (a.holder and a.request):
            ap.error("--holder 與 --request 要一起給")
        key = make_key(bud.id, a.holder, a.request)
    if a.cmd == "status":
        print(json.dumps(status(bud, key), ensure_ascii=False, indent=1))
        return 0
    if key is None:
        ap.error("%s 要 --holder 與 --request" % a.cmd)
    import aos7_budget_gate as gate
    if a.cmd == "call":
        return gate.call(bud, key, a.amount, a.resource, a.payload, a.out, a.patience)
    kid = kid_of(key)
    if a.cmd == "cancel":
        def do_cancel():
            r = gate.cancel(bud, key)
            if r.get("stage") != "done":                     # 非終局（入口紀錄或後端讀不到）＝未知
                return gate.pending(kid, key, "cancel", r)
            print(json.dumps(r, ensure_ascii=False))
            return 0 if r.get("outcome") == "cancelled" else 1
        return gate.io_boundary(do_cancel, kid, key)

    def do_settle():
        r = ask(bud, "settle", key, patience=a.patience)
        print(json.dumps(r, ensure_ascii=False))
        return 0 if r.get("result") == "settled" else 3
    return gate.io_boundary(do_settle, kid, key)


if __name__ == "__main__":
    sys.exit(main())
