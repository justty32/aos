"""budget 任務包：grant 判定、時鐘、帳（ledger）與命令列（spec 見同資料夾的 spec.md；契約卡在 ADVANCED.md）。

    aos7-budget init <預算>                         照 grant.json 開帳
    aos7-budget ledger <預算>                       帳任務（普通 keep，max_live 1）：處理 inbox/ 的請求
    aos7-budget call <預算> --holder H --request R  包裝程式：reserve → 入口 run → settle（在 aos7_budget_gate.py）
    aos7-budget cancel|settle|status <預算> ...     人手指令

預算資料夾＝`<node>/budget/<id>/`。只用核心公開的檔：round.json（completed_tock）；核心不知道這個包。
"""
import json
import os
import sys
import time
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
TOP = os.path.dirname(os.path.dirname(HERE))           # proto7-2/
sys.path[:0] = [os.path.join(TOP, "lib")]
from aos7_fs import OK, U, Unknown, fact, now, write_json  # noqa: E402

from aos7_budget_common import (
    ID_RE, CLOCK, GATEWAY, PARTIAL_SETTLE, RESOURCE, GRANT_FIELDS, POLL, ORPHAN_ROUNDS, Bud, not_running, say,
    ArgumentParser, ledger_running, sha, make_key, kid_of, digest_of, test_crash, completed_tock, grant_issue,
    is_child, load_grant, judge,
)  # noqa: F401
from aos7_budget_ledger import (
    ledger_issue, read_ledger, init, receipt_from, transition, gateway_terminal, handle, LedgerDown, process_inbox,
    sweep_receipts, serve,
)  # noqa: F401


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
    ap = ArgumentParser(prog="aos7-budget", description="先預留、再使用、最後結帳，讓每次花費都有紀錄。")
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
        try:
            ok, why = init(bud)
        except (OSError, LedgerDown, Unknown) as e:
            say("不確定：開帳讀寫故障：%s，現有檔案留著。修好讀寫後照原樣再跑一次" % e)
            return 3
        print(json.dumps({"ok": ok, "why": why}, ensure_ascii=False))
        if not ok and fact(bud.p("grant.json"))[0] == U:
            say("不確定：grant.json 讀不到（%s），什麼都沒寫。修好讀寫後照原樣再跑一次" % why)
            return 3
        if not ok:
            say("開帳做不到：%s。檢查 grant.json 與既有帳，再用 aos7-budget status %s 查看" % (why, a.bud))
        return 0 if ok else 1
    if a.cmd == "ledger":
        try:
            serve(bud)
        except OSError as e:
            say("不確定：帳任務讀寫故障停下（%s），帳與請求留著。修好讀寫後再起一次帳任務" % e)
            return 3
        return 0
    key = None
    if a.holder is not None or a.request is not None:
        if not (a.holder and a.request):
            ap.error("--holder 與 --request 要一起給")
        key = make_key(bud.id, a.holder, a.request)
    if a.cmd == "status":
        st = fact(bud.p("ledger.json"))[0]
        obj = status(bud, key)
        print(json.dumps(obj, ensure_ascii=False, indent=1))
        if "error" in obj:
            if U in (st, fact(bud.p("ledger.json"))[0]):
                say("不確定：帳讀不到：%s，現有帳與證據留著。修好讀寫後照原樣再跑一次" % obj["error"])
                return 3
            say("帳還沒開（或壞了）：%s。先 aos7-budget init %s；已有壞帳先檢查原檔" % (obj["error"], a.bud))
            return 1
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
            if r.get("outcome") != "cancelled":
                say("取消不成，已有終局 %s。用 aos7-budget status %s 查看，再按原回條結帳" % (r.get("outcome"), a.bud))
                return 1
            return 0
        return gate.io_boundary(do_cancel, kid, key)

    def do_settle():
        if not ledger_running(bud):
            say(not_running(bud))
            return 1
        r = ask(bud, "settle", key, patience=a.patience)
        print(json.dumps(r, ensure_ascii=False))
        if r.get("result") != "settled":
            say("不確定：帳沒回結算回條，請求與預留留著。用 status 看證據，照原樣再跑一次會接續")
            return 3
        return 0
    return gate.io_boundary(do_settle, kid, key)


if __name__ == "__main__":
    sys.exit(main())
