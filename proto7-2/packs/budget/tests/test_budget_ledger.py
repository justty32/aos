"""budget 帳與 grant 測試。"""
from _budget_ledger import *  # noqa: F403

class TestNormal(LedgerCase):
    """〔budget〕正常與競爭：消耗 1、搶最後 1、同鍵並行、異內容、不符、拒絕計 0、失敗計 1。"""

    def test_consume_one(self):
        bd = self.up()
        rc, out = self.call(self.node, "r1", payload=self.payload(self.node, "p.json", echo="hi"))
        self.assertEqual(rc, 0, out)
        self.assertEqual((out["outcome"], out["used"], out["response"]["echo"]), ("accepted", 1, "hi"))
        L = self.audit(bd, final=True)
        self.assertEqual((L["available"], L["inflight"], L["used"]), (2, 0, 1))
        self.assertEqual(self.backend(bd)["accepted"], 1)
        self.assertEqual((os.listdir(os.path.join(bd, "inbox")), os.listdir(os.path.join(bd, "receipts"))), ([], []))
        st = json.loads(self.cli(self.node, "status", "budget/demo", "--holder", "api", "--request", "r1").stdout)
        self.assertEqual((st["stage"], st["gateway"]["outcome"]), ("settled", "accepted"))

    def test_race_last_unit(self):
        """額度 1，六個不同 K 同時搶：恰一個成功，其餘 denied（不入帳）。"""
        bd = self.up(grant(amount=1))
        ps = [self.popen(self.node, *self.call_args("r%d" % i)) for i in range(6)]
        rcs = sorted(p.wait(30) for p in ps)
        self.assertEqual(rcs, [0, 1, 1, 1, 1, 1])
        L = self.audit(bd, final=True)
        self.assertEqual((L["available"], L["used"], len(L["ops"])), (0, 1, 1))

    def test_same_key_concurrent(self):
        """同 K 同內容六個並行：全部回同一個成功結果，後端只受理一次、只扣一次。"""
        bd = self.up()
        ps = [self.popen(self.node, *self.call_args("same")) for _ in range(6)]
        outs = [(p.wait(30), last_json(p.stdout.read())) for p in ps]
        self.assertEqual({rc for rc, _ in outs}, {0}, outs)
        self.assertEqual({o["settle"]["seq"] for _, o in outs}, {2})
        L = self.audit(bd, final=True)
        self.assertEqual((L["used"], len(L["log"]), self.backend(bd)["accepted"]), (1, 2, 1))

    def test_same_key_other_content_conflict(self):
        bd = self.up()
        self.assertEqual(self.call(self.node, "k")[0], 0)
        rc, out = self.call(self.node, "k", payload=self.payload(self.node, "p.json", echo="other"))
        self.assertEqual((rc, out["outcome"]), (1, "conflict"), out)
        rc, out = self.call(self.node, "k", extra=("--amount", "2"))
        self.assertEqual((rc, out["outcome"]), (1, "conflict"), out)
        self.assertEqual(self.audit(bd, final=True)["used"], 1)

    def test_mismatch_denied(self):
        """持有人、資源、入口不符：reserve 被拒、不入帳。"""
        bd = self.up()
        for kw in ({"holder": "bob"}, {"extra": ("--resource", "cpu.ms")}):
            rc, out = self.call(self.node, "x", **kw)
            self.assertEqual((rc, out["outcome"], out["stage"]), (1, "denied", "reserve"), out)
        shutil.rmtree(os.path.join(self.node, "budget"))
        self.lp.kill()
        bd = self.up(grant(gateway="other"))
        rc, out = self.call(self.node, "x")
        self.assertEqual((rc, out["outcome"]), (1, "denied"), out)
        self.assertEqual(self.audit(bd)["seq"], 0)

    def test_reject_zero_fail_one(self):
        """後端明確拒絕計 0、退回預留；已受理後處理失敗仍計 1。"""
        bd = self.up()
        rc, out = self.call(self.node, "rej", payload=self.payload(self.node, "r.json", mode="reject"))
        self.assertEqual((rc, out["outcome"], out["used"]), (1, "rejected", 0), out)
        rc, out = self.call(self.node, "fail", payload=self.payload(self.node, "f.json", mode="fail"))
        self.assertEqual((rc, out["outcome"], out["used"]), (1, "failed", 1), out)
        L = self.audit(bd, final=True)
        self.assertEqual((L["available"], L["used"], self.backend(bd)["accepted"]), (2, 1, 1))

    def test_cancel_llm_reserved_before_intent(self):
        bd = self.up(grant(gateway="llm.fake", resource="llm.tokens"))
        key = bg.make_key("demo", "api", "llm-cancel")
        content = {"gateway": "llm.fake", "resource": "llm.tokens", "amount": 2, "payload_sha": None}
        r = bg.ask(bg.Bud(bd), "reserve", key, content)
        self.assertEqual(r["result"], "reserved", r)
        self.assertEqual(self.audit(bd)["inflight"], 2)
        r = self.cli(self.node, "cancel", "budget/demo", "--holder", "api", "--request", key["request"])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assert_cancelled(bd, key["request"], "llm.fake")
        r = self.cli(self.node, "settle", "budget/demo", "--holder", "api", "--request", key["request"])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        L = self.audit(bd, final=True)
        self.assertEqual((L["used"], L["available"], L["inflight"]), (0, 3, 0))

    def test_cancel_without_reservation(self):
        bd = self.up()
        self.assertNotIn(self.kid("absent"), self.ledger(bd)["ops"])
        r = self.cli(self.node, "cancel", "budget/demo", "--holder", "api", "--request", "absent")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assert_cancelled(bd, "absent")
        self.audit(bd, final=True)

    def test_cancel_with_unreadable_ledger(self):
        bd = self.setup_budget(self.node)
        with open(os.path.join(bd, "ledger.json"), "w") as f:
            f.write("{bad")
        r = self.cli(self.node, "cancel", "budget/demo", "--holder", "api", "--request", "unreadable")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assert_cancelled(bd, "unreadable")

    def test_cancel_intent_keeps_gateway_and_digest(self):
        bd = self.up(grant(gateway="llm.fake", resource="llm.tokens"))
        key = bg.make_key("demo", "api", "intent")
        content = {"gateway": "llm.fake", "resource": "llm.tokens", "amount": 2, "payload_sha": None}
        self.assertEqual(bg.ask(bg.Bud(bd), "reserve", key, content)["result"], "reserved")
        digest = bg.digest_of(key, content)
        write_json(os.path.join(bd, "gateway", self.kid("intent") + ".json"),
                   {"stage": "intent", "gateway": "fakeapi", "digest": digest})
        r = self.cli(self.node, "cancel", "budget/demo", "--holder", "api", "--request", "intent")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assert_cancelled(bd, "intent", digest=digest)


if __name__ == "__main__":
    unittest.main()
