"""budget 帳與 grant 測試。"""
from _budget_ledger import *  # noqa: F403

class TestTime(LedgerCase):
    """〔budget〕時間與失敗：到期、未生效、壞鐘、時鐘倒退、壞帳、帳不見不自動開。"""

    def test_reserved_then_expired_first_run_denied(self):
        """到期前 reserve、到期後首次准入被擋：入口終局 denied、結算 0、額度退回。"""
        bd = self.up(grant(until=10), clock=9)
        self.crash_at(bd, "call-after-reserve")
        self.assertEqual(self.call(self.node, "t")[0], KILLED)
        set_clock(self.node, 10)
        rc, out = self.call(self.node, "t")
        self.assertEqual((rc, out["outcome"], out["used"]), (1, "denied", 0), out)
        L = self.audit(bd, final=True)
        self.assertEqual((L["available"], self.backend(bd)["effects"]), (3, {}))

    def test_reserve_after_expiry_denied(self):
        bd = self.up(grant(until=10), clock=10)
        rc, out = self.call(self.node, "t")
        self.assertEqual((rc, out["outcome"], out["stage"]), (1, "denied", "reserve"), out)
        self.assertEqual(self.audit(bd)["seq"], 0)

    def test_admitted_then_expired_still_settles(self):
        """已准入（意圖寫了）後到期：恢復不再查效期，照常受理並結算 1。"""
        bd = self.up(grant(until=10), clock=9)
        self.crash_at(bd, "gateway-after-intent")
        self.assertEqual(self.call(self.node, "t")[0], KILLED)
        set_clock(self.node, 15)
        rc, out = self.call(self.node, "t")
        self.assertEqual((rc, out["outcome"]), (0, "accepted"), out)
        self.assertEqual(self.audit(bd, final=True)["used"], 1)

    def test_not_yet_is_not_terminal(self):
        bd = self.up(grant(**{"from": 5}), clock=3)
        rc, out = self.call(self.node, "n")
        self.assertEqual((rc, out["outcome"]), (3, "unknown"), out)
        self.assertEqual(self.audit(bd)["seq"], 0)
        set_clock(self.node, 5)
        self.assertEqual(self.call(self.node, "n")[0], 0)

    def test_bad_clock(self):
        """壞鐘：新 reserve 未知（不入帳）；已有入口證據的結算照做（不看時鐘）；時鐘倒退＝未知。"""
        bd = self.up(clock=9)
        self.crash_at(bd, "gateway-after-receipt")
        self.assertEqual(self.call(self.node, "s")[0], KILLED)
        rnd = os.path.join(self.node, ".aos", "round.json")
        with open(rnd, "w") as f:
            f.write("{bad")
        rc, out = self.call(self.node, "new")
        self.assertEqual((rc, out["outcome"], out["stage"]), (3, "unknown", "reserve"), out)
        rc, out = self.call(self.node, "s")
        self.assertEqual((rc, out["outcome"]), (0, "accepted"), out)
        set_clock(self.node, 4)                            # 帳看過 9
        rc, out = self.call(self.node, "back")
        self.assertEqual((rc, out["outcome"]), (3, "unknown"), out)
        L = self.audit(bd, final=True)
        self.assertEqual((len(L["ops"]), L["used"]), (1, 1))

    def test_bad_ledger_refuses(self):
        """壞帳：帳任務不受理（記 error.json、請求留著），包裝程式等滿耐性回 3；修好後同一請求照常處理、只扣一次。"""
        bd = self.up(clock=5)
        lpath = os.path.join(bd, "ledger.json")
        with open(lpath) as f:
            good = f.read()
        with open(lpath, "w") as f:
            f.write("{bad")
        p = self.popen(self.node, *self.call_args("b", extra=("--patience", "1")))
        self.wait_for(lambda: (read_json(os.path.join(bd, "error.json")) or {}).get("kind") == "ledger", 10,
                      "帳沒記錯")
        self.assertEqual(len(os.listdir(os.path.join(bd, "inbox"))), 1)
        self.assertIsNone(p.poll())
        set_clock(self.node, 6)
        self.assertEqual(p.wait(10), 3)
        with open(lpath) as f:
            self.assertEqual(f.read(), "{bad")              # 不當空帳覆寫
        with open(lpath, "w") as f:
            f.write(good)
        self.wait_for(lambda: not os.listdir(os.path.join(bd, "inbox")), 10, "修好後沒處理留著的請求")
        self.assertEqual(self.call(self.node, "b")[0], 0)
        L = self.audit(bd, final=True)
        self.assertEqual((L["used"], len(L["log"])), (1, 2))

    def test_missing_ledger_not_reopened(self):
        bd = self.up()
        os.unlink(os.path.join(bd, "ledger.json"))
        rc, out = self.call(self.node, "m", extra=("--patience", "0"))
        self.assertEqual(rc, 3, out)
        self.wait_for(lambda: (read_json(os.path.join(bd, "error.json")) or {}).get("kind") == "ledger", 10)
        self.assertFalse(os.path.exists(os.path.join(bd, "ledger.json")))


if __name__ == "__main__":
    unittest.main()
