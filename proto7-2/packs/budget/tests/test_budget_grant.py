"""budget 帳與 grant 測試。"""
from _budget_ledger import *  # noqa: F403

class TestGrant(BudgetCase):
    """〔budget〕grant 判定、時鐘與開帳（不起程序的部分）。"""

    def setUp(self):
        super().setUp()
        self.node = os.path.join(self.root, "a")
        self.bd = self.setup_budget(self.node)
        self.b = bg.Bud(self.bd)

    def judge(self, holder="api", resource="fakeapi.calls", gateway="fakeapi"):
        return bg.judge(self.b, holder, resource, gateway, self.ledger(self.bd))[0]

    def test_ok_and_mismatch(self):
        self.assertEqual(self.judge(), "ok")
        self.assertEqual(self.judge(holder="bob"), "denied")
        self.assertEqual(self.judge(resource="cpu"), "denied")
        self.assertEqual(self.judge(gateway="other"), "denied")

    def test_window_half_open(self):
        """from ≤ c < until：until 那一回合起就到期；from 之前是 not_yet（非終局）。"""
        write_json(os.path.join(self.bd, "grant.json"), grant(**{"from": 3, "until": 7}))
        os.unlink(os.path.join(self.bd, "ledger.json"))
        self.assertTrue(bg.init(self.b)[0])
        for c, want in ((2, "not_yet"), (3, "ok"), (6, "ok"), (7, "denied"), (9, "denied")):
            set_clock(self.node, c)
            self.assertEqual(self.judge(), want, c)
        set_clock(self.node, 7, open_=True)           # 第 8 回合開著＝完成的是 7
        self.assertEqual(bg.completed_tock(self.node), 7)

    def test_clock_unknown_and_backwards(self):
        with open(os.path.join(self.node, ".aos", "round.json"), "w") as f:
            f.write("{bad")
        self.assertEqual(self.judge(), "unknown")
        os.unlink(os.path.join(self.node, ".aos", "round.json"))
        self.assertEqual(self.judge(), "unknown")             # 沒有合法值＝未知，不是 0
        L = self.ledger(self.bd)
        L["clock_hw"] = 9
        set_clock(self.node, 8)
        self.assertEqual(bg.judge(self.b, "api", "fakeapi.calls", "fakeapi", L)[0], "unknown")

    def test_grant_changed_or_missing_is_unknown(self):
        write_json(os.path.join(self.bd, "grant.json"), grant(amount=99))
        self.assertEqual(self.judge(), "unknown")             # 開帳後改 grant＝未知，不是新額度
        os.unlink(os.path.join(self.bd, "grant.json"))
        self.assertEqual(self.judge(), "unknown")             # 讀不到不當沒有限制

    def test_child_grant_refused(self):
        """子 grant（parent 或 delegate 不是 false）：開帳拒絕、判定 denied。"""
        for bad in (grant(parent="g0"), grant(delegate=True), {k: v for k, v in grant().items() if k != "delegate"}):
            with self.subTest(bad=bad):
                os.unlink(os.path.join(self.bd, "ledger.json"))
                write_json(os.path.join(self.bd, "grant.json"), bad)
                r = self.cli(self.node, "init", "budget/demo")
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertFalse(os.path.exists(os.path.join(self.bd, "ledger.json")))
                self.assertTrue(bg.is_child(bad))
                write_json(os.path.join(self.bd, "grant.json"), grant())
                self.assertTrue(bg.init(self.b)[0])

    def test_init_refuses_existing(self):
        r = self.cli(self.node, "init", "budget/demo")
        self.assertEqual(r.returncode, 1)
        self.assertIn("已存在", r.stdout)


if __name__ == "__main__":
    unittest.main()
