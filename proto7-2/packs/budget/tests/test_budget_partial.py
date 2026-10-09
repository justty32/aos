"""〔budget〕部分結算、證據綁定、pending、overrun 與最後額度競爭。"""
import json
import os
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from budgetcase import BudgetCase, grant, last_json, set_clock
import aos7_budget as bg
from aos7_fs import write_json


def audit_partial(bd):
    """獨立重放 ledger.json；不使用包的核帳／轉移程式。"""
    L = json.loads(Path(bd, "ledger.json").read_text())
    available, inflight, used, overrun = L["initial"], 0, 0, 0
    reserved, settled = {}, {}
    for seq, e in enumerate(L["log"], 1):
        assert e["seq"] == seq
        k, amount = e["kid"], e["amount"]
        assert type(amount) is int and amount > 0
        if e["op"] == "reserve":
            assert k not in reserved and "overrun" not in e
            reserved[k] = e
            available, inflight = available - amount, inflight + amount
        else:
            assert e["op"] == "settle" and k in reserved and k not in settled
            assert amount == reserved[k]["amount"]
            u, o = e["used"], e.get("overrun", 0)
            assert type(u) is int and 0 <= u <= amount
            assert type(o) is int and o >= 0
            settled[k] = e
            available, inflight, used = available + amount - u, inflight - amount, used + u
            overrun += o
        assert min(available, inflight, used) >= 0
        assert available + inflight + used == L["initial"]
        assert (available, inflight, used) == (e["available"], e["inflight"], e["used_total"])
    assert (available, inflight, used, len(L["log"])) == (L["available"], L["inflight"], L["used"], L["seq"])
    assert L.get("overrun", 0) == overrun
    assert set(L["ops"]) == set(reserved)
    for k, r in L["ops"].items():
        assert r["amount"] == reserved[k]["amount"] and r["reserve"]["seq"] == reserved[k]["seq"]
        assert r["stage"] == ("settled" if k in settled else "reserved")
        if k in settled:
            assert (r["settle"]["seq"], r["settle"]["used"], r["settle"].get("overrun", 0)) == (
                settled[k]["seq"], settled[k]["used"], settled[k].get("overrun", 0))
        else:
            assert "settle" not in r
    return L


class TestPartial(BudgetCase):
    """〔budget〕B2-1～B2-6：直接處理請求與 CLI 相容。"""

    def setUp(self):
        super().setUp()
        self.node = os.path.join(self.root, "a")
        self.bd = self.setup_budget(self.node, grant(amount=1000))
        self.b = bg.Bud(self.bd)
        self.addCleanup(audit_partial, self.bd)

    def reserve(self, request="r1", amount=300):
        key = bg.make_key("demo", "api", request)
        content = {"resource": "fakeapi.calls", "gateway": "fakeapi", "amount": amount, "payload_sha": None}
        self.assertEqual(bg.handle(self.b, {"op": "reserve", "key": key, "content": content})["result"], "reserved")
        return key

    def evidence(self, key, /, **kw):
        kid = bg.kid_of(key)
        r = {"stage": "done", "kid": kid, "key": key, "digest": self.ledger(self.bd)["ops"][kid]["digest"],
             "gateway": "llm.fake", "call_id": key["request"], "outcome": "answered", "used": 120,
             "usage": {"total_tokens": 120}, "overrun": 0, "billing": "final", "raw_sha": "raw", "at": "test"}
        r.update(kw)
        return r

    def settle(self, key, record):
        write_json(self.b.p("gateway", bg.kid_of(key) + ".json"), record)
        return bg.handle(self.b, {"op": "settle", "key": key})

    def snapshot(self):
        return {k: v for k, v in self.ledger(self.bd).items() if k != "clock_hw"}

    def unknown(self, key, record):
        before = self.snapshot()
        set_clock(self.node, 6)
        r = self.settle(key, record)
        self.assertEqual(r["result"], "unknown")
        self.assertEqual(before, self.snapshot())
        audit_partial(self.bd)
        return r

    def test_partial_and_replay(self):
        self.assertTrue(bg.PARTIAL_SETTLE)
        key = self.reserve()
        first = self.settle(key, self.evidence(key))
        self.assertEqual(first["result"], "settled")
        L = audit_partial(self.bd)
        self.assertEqual((L["available"], L["inflight"], L["used"]), (880, 0, 120))
        before = Path(self.b.p("ledger.json")).read_bytes()
        self.assertEqual(bg.handle(self.b, {"op": "settle", "key": key}), first)
        self.assertEqual(Path(self.b.p("ledger.json")).read_bytes(), before)

    def test_full_and_zero(self):
        for u in (300, 0):
            key = self.reserve(str(u))
            self.assertEqual(self.settle(key, self.evidence(key, used=u))["settle"]["used"], u)
            audit_partial(self.bd)

    def test_invalid_used(self):
        key = self.reserve()
        for u in (301, -1, 1.5, "120", True):
            with self.subTest(used=u):
                self.unknown(key, self.evidence(key, used=u))

    def test_pending_and_legacy(self):
        key = self.reserve()
        for billing in ("pending", "pending", "x"):
            r = self.evidence(key, billing=billing)
            del r["used"]
            self.assertIn("billing pending", self.unknown(key, r)["why"])
            self.assertEqual(self.ledger(self.bd)["inflight"], 300)
        r = self.evidence(key, used=300)
        del r["billing"], r["overrun"]
        self.assertEqual(self.settle(key, r)["result"], "settled")

    def test_overrun_and_old_ledger(self):
        key = self.reserve()
        L = self.ledger(self.bd)
        L.pop("overrun", None)
        write_json(self.b.p("ledger.json"), L)
        self.assertEqual(bg.status(self.b)["overrun"], 0)
        r = self.settle(key, self.evidence(key, used=300, overrun=50, billing="overrun"))
        self.assertEqual(r["settle"]["overrun"], 50)
        L = audit_partial(self.bd)
        self.assertEqual((L["used"], L["log"][-1]["overrun"], L["overrun"]), (300, 50, 50))
        key = self.reserve("after-overrun")
        self.settle(key, self.evidence(key, used=0))
        self.assertEqual(bg.status(self.b)["overrun"], 50)
        key = self.reserve("second-overrun")
        r = self.settle(key, self.evidence(key, used=300, overrun=20, billing="overrun"))
        self.assertEqual(bg.handle(self.b, {"op": "settle", "key": key}), r)
        self.assertEqual((audit_partial(self.bd)["overrun"], bg.status(self.b)["overrun"]), (70, 70))

    def test_old_ledger_zero_overrun(self):
        key = self.reserve()
        L = self.ledger(self.bd)
        L.pop("overrun", None)
        write_json(self.b.p("ledger.json"), L)
        self.settle(key, self.evidence(key))
        self.assertEqual(self.ledger(self.bd)["overrun"], 0)

    def test_invalid_overrun(self):
        key = self.reserve()
        for o in (-1, 1.5, "50", True, None):
            with self.subTest(overrun=o):
                self.unknown(key, self.evidence(key, overrun=o))

    def test_binding_and_cancel_exception(self):
        key = self.reserve()
        for kw in ({"digest": "tampered"}, {"key": dict(key, request="other")}, {"digest": None},
                   {"digest": None, "outcome": "cancelled", "used": 1},
                   {"key": dict(key, request="other"), "digest": None, "outcome": "cancelled", "used": 0},
                {"digest": "tampered", "outcome": "cancelled", "used": 0}):
            with self.subTest(kw=kw):
                self.unknown(key, self.evidence(key, **kw))
        r = self.evidence(key, outcome="cancelled", used=0)
        del r["digest"]                       # 缺欄不等於 null：不豁免
        self.unknown(key, r)
        self.assertEqual(self.settle(key, self.evidence(key, digest=None, outcome="cancelled", used=0))[
            "settle"]["used"], 0)

    def test_cli_cancel_without_record(self):
        self.reserve()
        self.start_ledger(self.node)
        args = ("budget/demo", "--holder", "api", "--request", "r1")
        p = self.cli(self.node, "cancel", *args)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        p = self.cli(self.node, "settle", *args)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(last_json(p.stdout)["settle"]["used"], 0)

    def test_cli_cancel_intents(self):
        key = self.reserve()
        r = self.evidence(key)
        r = {k: r[k] for k in ("kid", "key", "digest", "gateway", "call_id", "at")}
        r.update(stage="intent", admitted_tock=5)
        path = Path(self.b.p("gateway", bg.kid_of(key) + ".json"))
        write_json(str(path), r)
        before, ledger = path.read_bytes(), self.snapshot()
        args = ("budget/demo", "--holder", "api", "--request", "r1")
        p = self.cli(self.node, "cancel", *args)
        self.assertEqual(p.returncode, 3, p.stdout + p.stderr)
        self.assertEqual(last_json(p.stdout)["outcome"], "unknown")
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(self.snapshot(), ledger)
        self.assertFalse(os.path.exists(self.b.p("backend.json")))
        audit_partial(self.bd)
        del r["gateway"]
        write_json(str(path), r)
        p = self.cli(self.node, "cancel", *args)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(last_json(p.stdout)["outcome"], "cancelled")

    def test_last_credit_reserve_concurrent(self):
        self.start_ledger(self.node)
        barrier = threading.Barrier(2)

        def reserve(i):
            content = {"resource": "fakeapi.calls", "gateway": "fakeapi", "amount": 1000, "payload_sha": None}
            barrier.wait(timeout=5)
            path = bg.submit(self.b, "reserve", bg.make_key("demo", "api", str(i)), content)
            return bg.await_receipt(self.b, path, 5)["result"]

        with ThreadPoolExecutor(2) as pool:
            futures = [pool.submit(reserve, i) for i in range(2)]
            self.assertEqual(sorted(f.result(timeout=10) for f in futures), ["denied", "reserved"])

    def test_last_credit_call_concurrent(self):
        self.start_ledger(self.node)
        ps = [self.popen(self.node, *self.call_args(str(i), extra=("--amount", "1000"))) for i in range(2)]
        for p in ps:
            p.communicate(timeout=10)
        self.assertEqual(sorted(p.returncode for p in ps), [0, 1])

    def test_fakeapi_regression(self):
        self.start_ledger(self.node)
        for mode, code, u in (("ok", 0, 300), ("reject", 1, 0)):
            payload = self.payload(self.node, mode + ".json", mode=mode)
            got, r = self.call(self.node, mode, payload=payload, extra=("--amount", "300"))
            self.assertEqual(got, code)
            self.assertEqual((r["settle"]["used"], r["settle"]["overrun"]), (u, 0))
            audit_partial(self.bd)
        self.assertEqual((self.ledger(self.bd)["available"], self.ledger(self.bd)["used"],
                          self.ledger(self.bd)["overrun"]), (700, 300, 0))


if __name__ == "__main__":
    unittest.main()
