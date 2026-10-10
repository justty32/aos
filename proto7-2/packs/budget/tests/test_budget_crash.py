"""budget 帳與 grant 測試。"""
from _budget_ledger import *  # noqa: F403

class TestCrash(LedgerCase):
    """〔budget〕崩潰：帳與包裝程式在各持久提交前後被 SIGKILL，重開／重跑同 K 只把沒做完的做完。"""

    def test_ledger_points(self):
        for point in ("reserve-before-commit", "reserve-after-commit", "settle-before-commit", "settle-after-commit"):
            with self.subTest(point=point):
                bd = self.up()
                self.crash_at(bd, point)
                p = self.popen(self.node, *self.call_args("r1"))
                def check():
                    L = self.audit(bd)                           # 重起前核崩潰快照
                    kid = self.kid("r1")
                    seq, balances, stage = {
                        "reserve-before-commit": (0, (3, 0, 0), None),
                        "reserve-after-commit": (1, (2, 1, 0), "reserved"),
                        "settle-before-commit": (1, (2, 1, 0), "reserved"),
                        "settle-after-commit": (2, (2, 0, 1), "settled"),
                    }[point]
                    self.assertEqual(L["seq"], seq)
                    self.assertEqual((L["available"], L["inflight"], L["used"]), balances)
                    if stage is None:
                        self.assertNotIn(kid, L["ops"])
                    else:
                        self.assertEqual(L["ops"][kid]["stage"], stage)
                    if point == "settle-before-commit":
                        self.assertEqual(self.gw(bd, kid)["stage"], "done")
                self.restart_ledger(check)
                self.assertEqual(p.wait(30), 0, p.stderr.read())
                L = self.audit(bd, final=True)
                self.assertEqual((L["used"], len(L["log"]), self.backend(bd)["accepted"]), (1, 2, 1))
                self.assertFalse(os.path.exists(os.path.join(bd, ".crash")))
                self.lp.kill()
                self.lp.wait()
                shutil.rmtree(os.path.join(self.node, "budget"))

    def test_wrapper_points(self):
        """包裝程式在 reserve 後、准入意圖後、後端效果後（回條未寫）、入口回條後、結算後被殺：重跑同 K 不重扣、不重做。"""
        for point in ("call-after-reserve", "gateway-after-intent", "backend-after-effect", "gateway-after-receipt",
                      "call-after-settle"):
            with self.subTest(point=point):
                bd = self.up()
                self.crash_at(bd, point)
                rc, out = self.call(self.node, "r1")
                self.assertEqual(rc, KILLED, out)
                self.audit(bd)
                rc, out = self.call(self.node, "r1")
                self.assertEqual((rc, out["outcome"]), (0, "accepted"), out)
                self.assertEqual(self.call(self.node, "r1")[0], 0)        # 再重播一次
                L = self.audit(bd, final=True)
                self.assertEqual((L["used"], len(L["log"]), self.backend(bd)["accepted"]), (1, 2, 1))
                self.lp.kill()
                self.lp.wait()
                shutil.rmtree(os.path.join(self.node, "budget"))

    def test_unknown_then_evidence(self):
        """准入意圖寫了就被殺：settle 回 unknown、預留留著（不退）；補上證據（重跑同 K）才結算。"""
        bd = self.up()
        self.crash_at(bd, "gateway-after-intent")
        self.assertEqual(self.call(self.node, "u")[0], KILLED)
        self.assertEqual(self.gw(bd, self.kid("u"))["stage"], "intent")
        r = self.cli(self.node, "settle", "budget/demo", "--holder", "api", "--request", "u")
        self.assertEqual(r.returncode, 3, r.stdout)
        self.assertEqual(last_json(r.stdout)["result"], "unknown")
        L = self.audit(bd)
        self.assertEqual((L["available"], L["inflight"]), (2, 1))
        self.assertEqual(self.call(self.node, "u")[0], 0)
        self.assertEqual(self.audit(bd, final=True)["used"], 1)

    def test_cancel_then_late_run(self):
        """預留後取消：終局 cancelled，晚到的 run(K) 不執行、結算 0、額度退回。"""
        bd = self.up()
        self.crash_at(bd, "call-after-reserve")
        self.assertEqual(self.call(self.node, "c")[0], KILLED)
        r = self.cli(self.node, "cancel", "budget/demo", "--holder", "api", "--request", "c")
        self.assertEqual((r.returncode, last_json(r.stdout)["outcome"]), (0, "cancelled"), r.stdout)
        self.assert_cancelled(bd, "c")
        rc, out = self.call(self.node, "c")
        self.assertEqual((rc, out["outcome"], out["used"]), (1, "cancelled", 0), out)
        L = self.audit(bd, final=True)
        self.assertEqual((L["available"], L["used"], self.backend(bd)["effects"]), (3, 0, {}))

    def test_cancel_after_effect_refused(self):
        """後端已受理（入口回條未寫）時取消：查回效果、寫成 accepted，取消不成；結算 1。"""
        bd = self.up()
        self.crash_at(bd, "backend-after-effect")
        self.assertEqual(self.call(self.node, "e")[0], KILLED)
        r = self.cli(self.node, "cancel", "budget/demo", "--holder", "api", "--request", "e")
        self.assertEqual((r.returncode, last_json(r.stdout)["outcome"]), (1, "accepted"), r.stdout)
        self.assertEqual(self.call(self.node, "e")[0], 0)
        self.assertEqual(self.audit(bd, final=True)["used"], 1)

    def test_cancel_run_race(self):
        """十個 K 各自同時跑 call 與 cancel：每個 K 恰為「後端受理」或「已取消」之一，不雙花；途中每份帳快照都守恆。"""
        bd = self.up(grant(amount=10))
        snaps, stop = [], threading.Event()

        def sampler():
            while not stop.is_set():
                L = read_json(os.path.join(bd, "ledger.json"))
                if isinstance(L, dict):
                    snaps.append(L)
                time.sleep(0.005)
        t = threading.Thread(target=sampler)
        t.start()
        try:
            ps = []
            for i in range(10):
                ps.append(self.popen(self.node, *self.call_args("q%d" % i)))
                ps.append(self.popen(self.node, "cancel", "budget/demo", "--holder", "api", "--request", "q%d" % i))
            for p in ps:
                p.wait(30)
            for i in range(10):                        # 取消贏了的，call 可能停在 settle 前：重跑同 K 收尾
                self.assertIn(self.call(self.node, "q%d" % i)[0], (0, 1))
        finally:
            stop.set()
            t.join()
        L = self.audit(bd, final=True)
        b = self.backend(bd)
        for i in range(10):
            k = self.kid("q%d" % i)
            g = self.gw(bd, k)
            self.assertIn(g["outcome"], ("accepted", "cancelled"))
            self.assertEqual(g["outcome"] == "accepted", k in b["effects"], k)
        self.assertEqual(L["used"], b["accepted"])
        final_log = L["log"]
        for s in snaps:
            self.assertEqual(s["available"] + s["inflight"] + s["used"], s["initial"])
            self.assertTrue(min(s["available"], s["inflight"], s["used"]) >= 0)
            self.assertEqual(s["log"], final_log[:len(s["log"])], "帳快照不是最後 log 的前綴")


if __name__ == "__main__":
    unittest.main()
