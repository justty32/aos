"""LLM 單次呼叫閘道：固定請求、預留、一次傳輸、本地證據恢復與結算（spec.md）。"""
import argparse
import json
import os
import re
import signal
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(os.path.dirname(HERE), "budget"),
                os.path.join(os.path.dirname(os.path.dirname(HERE)), "lib")]
import aos7_budget as bg  # noqa: E402
import aos7_llmcall_fake  # noqa: E402
import aos7_llmcall_litellm  # noqa: E402
from aos7_fs import N, OK, U, LockTimeout, Unknown, fact, is_int, locked, now, write_json  # noqa: E402

TRANSPORT = aos7_llmcall_fake.send
TRANSPORT_LITELLM = aos7_llmcall_litellm.send
CALL_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
METER = "fake.total_tokens/1"
GATEWAY = "llm.fake"
ENDPOINT = "fake"
MAX_DEADLINE = 86400                # 傳輸秒數上限（也擋 inf／nan：比較為假）


def test_crash(node, point):
    """測試鉤子：到點刪旗標並殺整組；測試呼叫者須 start_new_session。"""
    path = os.path.join(node, "llmcall", ".crash")
    try:
        with open(path) as f:
            want = f.read().strip()
    except FileNotFoundError:
        return
    if want == point:
        os.unlink(path)
        os.killpg(os.getpgid(0), signal.SIGKILL)


def load(path):
    """本包的證據：不存在回 None；讀不到或壞掉不當成沒有。"""
    st, obj = fact(path)
    if st == N:
        return None
    if st != OK or not isinstance(obj, dict):
        raise Unknown("%s 讀不到或不是物件：%s" % (path, obj))
    return obj


def emit(obj, out=None):
    if out:
        write_json(out, obj)
    print(json.dumps(obj, ensure_ascii=False))


def problem(outcome, stage, why):
    emit({"outcome": outcome, "stage": stage, "why": why})
    return 1 if outcome in ("conflict", "denied", "bad", "refused") else 3


def exit_of(receipt):
    if receipt["billing"] in ("pending", "overrun"):
        return 4
    return 0 if receipt["outcome"] == "answered" else 1


def io_boundary(fn):
    """讀寫故障統一回 unknown，不留 traceback。"""
    try:
        return fn()
    except LockTimeout as e:
        return problem("unknown", "busy", str(e))
    except (Unknown, bg.LedgerDown, OSError) as e:
        return problem("unknown", "io", str(e))


def paths(bud, call_id, holder):
    cd = os.path.join(bud.node, "llmcall", bud.id, call_id)
    key = bg.make_key(bud.id, holder, call_id)
    kid = bg.kid_of(key)
    return cd, key, kid, bud.p("gateway", kid + ".json")


def send(node, call_id, request, deadline):
    """傳輸在 daemon thread 執行，逾時不等它；意圖保留、重跑不送。"""
    result = {}

    def work():
        try:
            transport = TRANSPORT_LITELLM if "litellm" in request else TRANSPORT
            result["reply"] = transport(node, call_id, request, deadline)
        except Exception as e:
            result["error"] = e
    thread = threading.Thread(target=work, daemon=True)
    thread.start()
    thread.join(deadline)
    if thread.is_alive():
        raise Unknown("傳輸逾時，intent 留著")
    if "error" in result:
        e = result["error"]
        if isinstance(e, (Unknown, bg.LedgerDown, OSError)):
            raise e
        raise Unknown("傳輸例外：%r；intent 留著" % e)
    return result["reply"]


def done_from(raw, key, kid, digest, reserve, gateway_name=GATEWAY):
    """由已存 raw 算終局；未知 usage 不寫 used，拒絕不看 usage。"""
    reply = raw["reply"] if isinstance(raw.get("reply"), dict) else {}
    status = reply.get("status")
    rejected = status == "reject" and reply.get("billed") is False
    outcome = "failed"
    if status == "ok":
        outcome = "answered"
    elif rejected:
        outcome = "rejected"
    usage = reply.get("usage") if isinstance(reply.get("usage"), dict) else None
    u = usage.get("total_tokens") if usage else None
    known = status in ("ok", "error") if isinstance(status, str) else False
    known = known and is_int(u) and u >= 0
    done = {"stage": "done", "kid": kid, "key": key, "digest": digest, "gateway": gateway_name,
            "call_id": raw["call_id"], "outcome": outcome}
    if rejected or known:
        done["used"] = 0 if rejected else min(u, reserve)
    overrun = max(0, u - reserve) if known and not rejected else 0
    billing = "pending"
    if rejected or known:
        billing = "overrun" if overrun else "final"
    done.update(usage=usage, overrun=overrun, billing=billing, raw_sha=bg.sha(raw), at=raw["at"])
    return done


def gateway(bud, cd, req, key, kid, path, content, deadline):
    """持 K 鎖恢復本地證據，只有無入口紀錄時可首次傳輸。"""
    gateway_name = content["gateway"]
    digest = bg.digest_of(key, content)
    with locked(path):
        raw = load(os.path.join(cd, "raw.json"))
        rec = load(path)
        if rec is not None and rec.get("digest") != digest \
                and not (rec.get("stage") == "done" and rec.get("outcome") == "cancelled"):
            return {"outcome": "conflict", "why": "同 K 的准入內容不同"}, None
        if raw is not None:
            if rec is None or rec.get("stage") != "done":
                rec = done_from(raw, key, kid, digest, req["reserve"], gateway_name)
                write_json(path, rec)
            return rec, raw
        if rec is not None:
            if rec.get("stage") == "done":
                return rec, None
            if rec.get("stage") == "intent":
                return {"outcome": "unknown", "stage": "intent", "why": "intent 後無回覆，不重送、預留留著"}, None
            raise Unknown("入口紀錄階段不明")
        ledger, why = bg.read_ledger(bud)
        if ledger is None:
            raise bg.LedgerDown(why)
        verdict, why, c = bg.judge(bud, key["holder"], "llm.tokens", gateway_name, ledger)
        if verdict == "denied":
            rec = {"stage": "done", "kid": kid, "key": key, "digest": digest, "gateway": gateway_name,
                   "call_id": req["call_id"], "outcome": "denied", "used": 0, "usage": None,
                   "overrun": 0, "billing": "final", "raw_sha": None, "at": now(), "why": why}
            write_json(path, rec)
            return rec, None
        if verdict != "ok":
            return {"outcome": "unknown", "why": why}, None
        reserved = ledger["ops"].get(kid)
        if reserved is None or reserved.get("stage") != "reserved":
            return {"outcome": "unknown", "why": "帳上沒有 K 的在途預留"}, None
        if reserved.get("digest") != digest:
            return {"outcome": "conflict", "why": "帳上預留內容不同"}, None
        write_json(path, {"stage": "intent", "kid": kid, "key": key, "digest": digest, "gateway": gateway_name,
                          "call_id": req["call_id"], "admitted_tock": c, "at": now()})
        test_crash(bud.node, "after-intent")
        reply = send(bud.node, req["call_id"], req["request"], deadline)
        test_crash(bud.node, "after-send")
        raw = {"v": 1, "call_id": req["call_id"], "req_sha": req["req_sha"], "source": "transport",
               "reply": reply, "at": now()}
        write_json(os.path.join(cd, "raw.json"), raw)
        test_crash(bud.node, "after-raw")
        rec = done_from(raw, key, kid, digest, req["reserve"], gateway_name)
        write_json(path, rec)
        test_crash(bud.node, "after-done")
        return rec, raw


def receipt_from(req, key, kid, done, raw, settle):
    reply = raw.get("reply") if raw else None
    text = reply.get("body") if isinstance(reply, dict) else None
    return {"v": 1, "call_id": req["call_id"], "logical": req["logical"], "kid": kid, "key": key,
            "req_sha": req["req_sha"], "meter": req["meter"], "bound": "soft", "reserve": req["reserve"],
            "outcome": done["outcome"], "usage": done.get("usage"), "used": done.get("used"),
            "overrun": done.get("overrun", 0), "billing": done.get("billing", "final"),
            "raw_sha": done.get("raw_sha"), "text": text if isinstance(text, str) else None, "settle": settle}


def call(bud, a):
    """先驗輸入，之後整次持 call 鎖；有回條就直接重印。"""
    st, request = fact(a.request)
    if st == U:
        raise Unknown(request)
    if st != OK or not isinstance(request, dict):
        print("aos7-llmcall: request 不存在、不是 JSON 或不是物件", file=sys.stderr)
        return 2
    gateway_name, meter, endpoint = GATEWAY, METER, ENDPOINT
    if "litellm" in request:
        body = request["litellm"]
        if "fake" in request or not isinstance(body, dict) or not isinstance(body.get("model"), str) \
                or not isinstance(body.get("messages"), list) or body.get("stream") is True:
            print("aos7-llmcall: litellm 請求不合", file=sys.stderr)
            return 2
        gateway_name, meter = aos7_llmcall_litellm.GATEWAY, aos7_llmcall_litellm.METER
        endpoint = aos7_llmcall_litellm.base_url()
    deadline = a.deadline if a.deadline is not None else (MAX_DEADLINE if "litellm" in request else 60)
    cd, key, kid, path = paths(bud, a.call, a.holder)
    rp = os.path.join(cd, "request.json")
    with locked(rp, timeout=0):
        want = {"v": 1, "call_id": a.call, "logical": a.logical, "budget": bud.id, "holder": a.holder,
                "req_sha": bg.sha(request), "reserve": a.reserve, "meter": meter, "endpoint": endpoint, "request": request}
        req = load(rp)
        if req is None:
            write_json(rp, want)
            req = want
        elif any(req.get(k) != want[k] for k in ("req_sha", "reserve", "holder", "budget")):
            return problem("conflict", "request", "同 call 的請求內容不同")
        receipt = load(os.path.join(cd, "receipt.json"))
        if receipt is not None:
            emit(receipt, a.out)
            return exit_of(receipt)
        test_crash(bud.node, "after-request")
        content = {"resource": "llm.tokens", "gateway": gateway_name, "amount": req["reserve"], "payload_sha": req["req_sha"]}
        r = bg.ask(bud, "reserve", key, content, a.patience)
        if r.get("result") in ("denied", "conflict", "bad"):
            return problem(r["result"], "reserve", r.get("why"))
        if r.get("result") not in ("reserved", "settled"):
            return problem("unknown", "reserve", r.get("why"))
        test_crash(bud.node, "after-reserve")
        done, raw = gateway(bud, cd, req, key, kid, path, content, deadline)
        if done.get("stage") != "done":
            return problem(done["outcome"], done.get("stage", "gateway"), done.get("why"))
        settle = None
        if done.get("billing", "final") != "pending":
            s = bg.ask(bud, "settle", key, patience=a.patience)
            if s.get("result") != "settled":
                return problem("unknown", "settle", s.get("why"))
            settle = s["settle"]
            test_crash(bud.node, "after-settle")
        receipt = receipt_from(req, key, kid, done, raw, settle)
        if receipt["billing"] != "pending":
            write_json(os.path.join(cd, "receipt.json"), receipt)
            test_crash(bud.node, "after-receipt")
        emit(receipt, a.out)
        return exit_of(receipt)


def status(bud, a):
    """唯讀顯示本地證據與 budget 的 K 摘要。"""
    cd, key, kid, path = paths(bud, a.call, a.holder)
    raw = load(os.path.join(cd, "raw.json"))
    obj = {"request": load(os.path.join(cd, "request.json")), "raw_exists": raw is not None,
           "raw_sha": bg.sha(raw) if raw is not None else None, "gateway": load(path),
           "ledger": bg.status(bud, key), "receipt": load(os.path.join(cd, "receipt.json"))}
    print(json.dumps(obj, ensure_ascii=False, indent=1))
    return 0


def adopt(bud, a):
    """只把人工帶來的遲到回覆接成 raw；不算 done、不結算。"""
    st, supplied = fact(a.raw)
    if st != OK or not isinstance(supplied, dict):
        print("aos7-llmcall: raw 讀不到或不是物件", file=sys.stderr)
        return 2
    cd, key, kid, path = paths(bud, a.call, a.holder)
    with locked(os.path.join(cd, "request.json"), timeout=0):
        with locked(path):
            req = load(os.path.join(cd, "request.json"))
            rec = load(path)
            raw = load(os.path.join(cd, "raw.json"))
            if req is None or rec is None or rec.get("stage") != "intent" or raw is not None:
                return problem("refused", "adopt", "只收 request 已存、入口 intent 且沒有 raw 的回覆")
            if supplied.get("call_id") != a.call or supplied.get("req_sha") != req["req_sha"] \
                    or not isinstance(supplied.get("reply"), dict):
                return problem("refused", "adopt", "call_id／req_sha 不符或 reply 不是物件")
            write_json(os.path.join(cd, "raw.json"), {"v": 1, "call_id": a.call, "req_sha": req["req_sha"],
                                                     "source": "adopted", "reply": supplied["reply"], "at": now()})
    emit({"outcome": "adopted", "call_id": a.call})
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="aos7-llmcall", description="LLM 單次呼叫閘道（fake／LiteLLM 傳輸）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for cmd in ("call", "status", "adopt"):
        p = sub.add_parser(cmd)
        p.add_argument("bud")
        p.add_argument("--holder", required=True)
        p.add_argument("--call", required=True)
        if cmd == "call":
            p.add_argument("--request", required=True)
            p.add_argument("--reserve", required=True, type=int)
            p.add_argument("--logical")
            p.add_argument("--deadline", type=float, default=None)
            p.add_argument("--patience", type=int, default=5)
            p.add_argument("--out")
        if cmd == "adopt":
            p.add_argument("--raw", required=True)
    a = ap.parse_args(argv)
    if not CALL_RE.fullmatch(a.call) or not a.holder or (a.cmd == "call" and (
            a.reserve <= 0 or (a.deadline is not None and not 0 < a.deadline <= MAX_DEADLINE) or a.patience < 0)):
        print("aos7-llmcall: call_id、holder 或 reserve 不合", file=sys.stderr)
        return 2
    bud = bg.Bud(a.bud)
    return io_boundary(lambda: {"call": call, "status": status, "adopt": adopt}[a.cmd](bud, a))
