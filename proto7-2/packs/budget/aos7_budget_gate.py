"""budget 包的入口（gateway）、假後端與 call 包裝程式（spec.md §4～§6）。

入口在呼叫它的程序裡跑（包裝程式、`cancel`），同一個 K 的准入、恢復、取消都持 `gateway/<kid>.json.lock` 互斥。
假後端是純本機的「假 API 受理次數」：效果＋受理計數同次原子提交、以 K 去重，所以效果完成、回條沒寫也查得回。
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import aos7_budget as bg  # noqa: E402
from aos7_budget import GATEWAY, kid_of  # noqa: E402
from aos7_fs import N, OK, Unknown, edit_json, fact, locked, now, write_json  # noqa: E402

MODES = {"ok": ("accepted", True), "fail": ("failed", True), "reject": ("rejected", False)}


# ---------- 假後端（spec §5） ----------

def backend_accept(bud, kid, key, amount, payload):
    """同 kid 已有效果＝回原效果、不再計數；否則一次寫入效果＋受理計數。回效果。"""
    mode = (payload or {}).get("mode", "ok") if isinstance(payload, dict) else "ok"
    outcome, spent = MODES.get(mode, ("rejected", False))
    got = {}

    def fn(b):
        b = b if isinstance(b, dict) else {"accepted": 0, "effects": {}}
        if kid in b["effects"]:
            got.update(b["effects"][kid])
            return None
        if spent:
            b["accepted"] += 1
        eff = {"key": key, "outcome": outcome, "used": amount if spent else 0, "n": b["accepted"] if spent else None,
               "response": {"ok": outcome == "accepted", "echo": (payload or {}).get("echo")
                            if isinstance(payload, dict) else None}, "at": now()}
        b["effects"][kid] = eff
        got.update(eff)
        return b
    edit_json(bud.p("backend.json"), fn)
    bg.test_crash(bud, "backend-after-effect")
    return got


def backend_query(bud, kid):
    """只讀：K 的效果（None＝確定沒有）。backend.json 讀不到丟 Unknown。"""
    st, b = fact(bud.p("backend.json"))
    if st == N:
        return None
    if st != OK or not isinstance(b, dict):
        raise bg.LedgerDown("backend.json 讀不到：%s" % b)
    return b.get("effects", {}).get(kid)


# ---------- 入口（spec §4） ----------

def done_from(eff, kid, key, digest, extra=None):
    return dict({"stage": "done", "kid": kid, "key": key, "digest": digest, "outcome": eff["outcome"],
                 "used": eff["used"], "response": eff.get("response"), "at": now()}, **(extra or {}))


def run(bud, key, content, payload):
    """入口 run(K)：回入口紀錄（終局 stage=done）或非終局 {"outcome": unknown|not_yet|conflict, "why"}。"""
    kid = kid_of(key)
    path = bud.p("gateway", kid + ".json")
    digest = bg.digest_of(key, content)
    with locked(path):
        st, rec = fact(path)
        if st not in (OK, N) or (st == OK and not isinstance(rec, dict)):
            return {"outcome": "unknown", "why": "入口紀錄讀不到：%s" % rec}
        if st == OK and rec.get("stage") == "done":
            if rec["outcome"] != "cancelled" and rec.get("digest") != digest:
                return {"outcome": "conflict", "why": "同一個 K 已用不同內容准入過"}
            return rec
        if st == OK and rec.get("stage") == "intent":
            if rec.get("digest") != digest:
                return {"outcome": "conflict", "why": "同一個 K 已用不同內容准入過"}
        else:
            # 首次准入：先查帳上的預留與 grant（spec §4 第 2、3 點）；非終局不寫檔
            L, why = bg.read_ledger(bud)
            if L is None:
                return {"outcome": "unknown", "why": why}
            verdict, why, c = bg.judge(bud, key["holder"], content["resource"], content["gateway"], L)
            if verdict == "denied":
                rec = {"stage": "done", "kid": kid, "key": key, "digest": digest, "outcome": "denied", "used": 0,
                       "why": why, "at": now()}
                write_json(path, rec)
                return rec
            if verdict != "ok":
                return {"outcome": verdict, "why": why}
            r = L["ops"].get(kid)
            if r is None or r.get("stage") != "reserved":
                return {"outcome": "unknown", "why": "帳上沒有 K 的在途預留（%s）" % (r and r.get("stage"))}
            if r.get("digest") != digest:
                return {"outcome": "conflict", "why": "預留的內容跟這次不同"}
            write_json(path, {"stage": "intent", "kid": kid, "key": key, "digest": digest, "admitted_tock": c,
                              "at": now()})
            bg.test_crash(bud, "gateway-after-intent")
        # 已准入（剛寫或恢復）：不再查效期，只向後端要 K 的效果（以 K 去重）；後端讀寫不到＝非終局，intent 留著
        try:
            eff = backend_accept(bud, kid, key, content["amount"], payload)
        except (Unknown, bg.LedgerDown) as e:
            return {"outcome": "unknown", "stage": "intent", "why": "後端讀寫不到（intent 留著）：%s" % e}
        rec = done_from(eff, kid, key, digest)
        write_json(path, rec)
        bg.test_crash(bud, "gateway-after-receipt")
        return rec


def cancel(bud, key):
    """取消 K（spec §4）：回入口終局紀錄；outcome 不是 cancelled＝已有結果、取消不成。"""
    kid = kid_of(key)
    path = bud.p("gateway", kid + ".json")
    with locked(path):
        st, rec = fact(path)
        if st not in (OK, N) or (st == OK and not isinstance(rec, dict)):
            return {"outcome": "unknown", "why": "入口紀錄讀不到：%s" % rec}
        if st == OK and rec.get("stage") == "done":
            return rec
        digest = rec.get("digest") if st == OK else None
        if st == OK:            # intent：後端呼叫只在鎖內發生，持鎖時查不到就是沒發生（只對假後端成立）
            try:
                eff = backend_query(bud, kid)
            except bg.LedgerDown as e:
                return {"outcome": "unknown", "why": str(e)}
            if eff is not None:
                rec = done_from(eff, kid, key, digest)
                write_json(path, rec)
                return rec
        rec = {"stage": "done", "kid": kid, "key": key, "digest": digest, "outcome": "cancelled", "used": 0,
               "at": now()}
        write_json(path, rec)
        return rec


# ---------- call 包裝程式（spec §6） ----------

def finish(bud, kid, key, gw, settle, out):
    res = {"kid": kid, "key": key, "outcome": gw.get("outcome"), "used": gw.get("used"),
           "response": gw.get("response"), "settle": settle}
    if out:
        write_json(out, res)
    print(json.dumps(res, ensure_ascii=False))
    return 0 if gw.get("outcome") == "accepted" else 1


def pending(kid, key, stage, r):
    print(json.dumps({"kid": kid, "key": key, "outcome": "unknown", "stage": stage, "why": r.get("why")},
                     ensure_ascii=False))
    return 3


def io_boundary(fn, kid, key):
    """共同故障邊界（spec §6）：讀寫不到（核心 Unknown、帳／後端讀不到、OSError）＝未知，印一行 JSON、退出 3，不留 traceback。"""
    try:
        return fn()
    except (Unknown, bg.LedgerDown, OSError) as e:
        return pending(kid, key, "io", {"why": "讀寫不到：%r" % e})


def call(bud, key, amount, resource, payload_path, out, patience):
    """reserve → 入口 run → settle；拿到終局結算回條才退出。0＝受理成功、1＝已結算但不成功或被拒、3＝未知（預留留著）。"""
    return io_boundary(lambda: _call(bud, key, amount, resource, payload_path, out, patience), kid_of(key), key)


def _call(bud, key, amount, resource, payload_path, out, patience):
    payload = None
    if payload_path:
        st, payload = fact(payload_path)
        if st != OK:
            print("aos7-budget: payload 讀不到：%s" % payload, file=sys.stderr)
            return 2
    content = {"resource": resource, "gateway": GATEWAY, "amount": amount,
               "payload_sha": bg.sha(payload) if payload is not None else None}
    kid = kid_of(key)
    r = bg.ask(bud, "reserve", key, content, patience)
    res = r.get("result")
    if res in ("denied", "conflict", "bad"):
        print(json.dumps({"kid": kid, "key": key, "outcome": res, "stage": "reserve", "why": r.get("why")},
                         ensure_ascii=False))
        return 1
    if res not in ("reserved", "settled"):
        return pending(kid, key, "reserve", r)
    bg.test_crash(bud, "call-after-reserve")
    if res == "settled":                         # 重播：帳已結過，只讀入口回條
        gw, _ = bg.gateway_terminal(bud, kid)
        return finish(bud, kid, key, gw or {"outcome": r["settle"].get("outcome"), "used": r["settle"]["used"]},
                      r["settle"], out)
    gw = run(bud, key, content, payload)
    if gw.get("outcome") == "conflict":
        print(json.dumps({"kid": kid, "key": key, "outcome": "conflict", "stage": "run", "why": gw.get("why")},
                         ensure_ascii=False))
        return 1
    if gw.get("stage") != "done":
        return pending(kid, key, "run", gw)
    s = bg.ask(bud, "settle", key, patience=patience)
    if s.get("result") != "settled":
        return pending(kid, key, "settle", s)
    bg.test_crash(bud, "call-after-settle")
    return finish(bud, kid, key, gw, s["settle"], out)

